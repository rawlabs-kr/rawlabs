from __future__ import absolute_import

import time
from time import sleep

import pandas as pd
import numpy as np
import xlrd
from bs4 import BeautifulSoup as bs
from celery import chain, group
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from imagefilter import exceptions
from imagefilter.models import Image, Product, File
from rawlabs.celery import app
from google.oauth2 import service_account
from google.cloud import vision_v1
from imagefilter.models import Image
from google.protobuf.json_format import MessageToDict


@app.task
def add(x, y):
    sleep(10)
    return x + y

@app.task
def create_product_and_image(file_id):
    from imagefilter.models import File
    from imagefilter.models import Product
    file = File.objects.get(Q(id=file_id) & Q(status=1))
    try:
        data_list = excel_to_dict(file.original.path)
    except exceptions.ExcelFormatException:
        file.status = 2
        file.error = 0
        file.save()
    else:
        with transaction.atomic():
            try:
                Product.objects.bulk_create([Product(file_id=file_id, **data) for data in data_list])
                product_list = Product.objects.values('id', 'original_description').filter(file_id=file_id)
                for product in product_list:
                    product_to_image(product)
            except exceptions.ExtractImageException:
                file.status = 2
                file.error = 1
                file.save()
            else:
                file.status = 3
                file.num_product = product_list.count()
                file.num_image = Image.objects.filter(product__file=file).count()
                file.error = None
                file.save()


@app.task
def filter_image(file_id, excluded_locales):
    from imagefilter.models import Image
    from imagefilter.models import File
    file = File.objects.get(id=file_id)
    image_list = Image.objects.values_list('id', flat=True).filter(Q(product__file_id=file_id) & Q(type=0))
    # image_result = []
    # for image_id in image_list:
    #     result = filter_single_image.delay(image_id, excluded_locales)
    #     image_result.append(result)
    #
    # is_finish = False
    # while is_finish is False:
    #     image_result = [i for i in image_result if i.state not in ['FAILURE', 'SUCCESS']]
    #     if len(image_result) == 0:
    #         file.status = 5
    #         file.save()
    #         is_finish = True
    #     else:
    #         time.sleep(5)
    #         continue
    g = group(filter_single_image.delay(image_id, excluded_locales) for image_id in image_list)
    g.apply_async()


@app.task
def filter_single_image(image_id, excluded_locales):
    try:
        image_instance = Image.objects.get(id=image_id)
    except Image.DoesNotExist:
        pass
    else:
        image_instance.type = 2
        image_instance.save()
        uri = image_instance.uri
        try:
            credentials = service_account.Credentials.from_service_account_file(settings.GOOGLE_VISION_API_CREDENTIAL_PATH)
            client = vision_v1.ImageAnnotatorClient(credentials=credentials)
            image = vision_v1.types.Image()
            image.source.image_uri = uri
            response = client.document_text_detection(image=image)
            data_dict = MessageToDict(response)
        except Exception as e:
            image_instance.type = 1  # 분류 실패
            image_instance.error = str(e)
            print(e)
        else:
            image_instance.extracted_text = data_dict
            try:
                locale = data_dict['textAnnotations'][0]['locale']
            except:
                image_instance.type = 4
            else:
                if locale in [excluded_locales] if isinstance(excluded_locales, str) else excluded_locales:
                    image_instance.type = 3
                else:
                    image_instance.type = 4
        finally:
            image_instance.filter_dt = timezone.now()
            image_instance.save()


def excel_to_dict(path, full=False, dict=True):
    if full:
        try:
            data = pd.read_excel(path)
        except Exception as e:
            raise exceptions.ExcelFormatException('{}'.format(str(e)))
        else:
            if dict:
                return data.to_dict('records')
            else:
                return data

    else:
        target_column = {'고객사상품코드': 'product_code', '상품명': 'name', '상품상세설명': 'original_description'}
        try:
            data = pd.read_excel(path, usecols=target_column.keys())
        except ValueError:
            raise exceptions.ExcelFormatException('파일에서 [{}] 항목을 확인하세요.'.format(', '.join(target_column.keys())))
        except Exception as e:
            raise exceptions.ExcelFormatException(str(e))
        else:
            data.rename(columns=target_column, inplace=True)

            if dict:
                return data.to_dict('records')
            else:
                return data


def product_to_image(product):
    from bs4 import BeautifulSoup as bs
    from imagefilter.models import Image
    try:
        soup = bs(product['original_description'], 'html.parser')
        image_soup_list = soup.find_all('img')
    except Exception as e:
        # TODO product_id : n 의 이미지 추출 실패 로깅
        raise exceptions.ExtractImageException('이미지 추출 실패')
    else:
        Image.objects.bulk_create([Image(product_id=product['id'], uri=soup.attrs['src']) for soup in image_soup_list])


@app.task
def generate_single_product_description(product_id):
    product = Product.objects.get(id=product_id)
    original = bs(product.original_description, 'html.parser')
    image_list = Image.objects.values('uri').filter(Q(product=product) & Q(type=3))
    if image_list.exists():
        product.change = True
    else:
        product.change = False
    for image in image_list:
        element = original.find('img', attrs={'src': image['uri']})
        if element:
            element.decompose()
    product.filtered_description = str(original)
    product.save()


@app.task
def generate_product_description(file_id):
    file = File.objects.get(id=file_id)
    product_list = Product.objects.values('id').filter(file_id=file_id)
    product_result = []
    for product in product_list:
        result = generate_single_product_description.delay(product_id=product['id'])
        product_result.append(result)

    is_finish = False

    while is_finish is False:
        product_result = [p for p in product_result if p.state not in ['FAILURE', 'SUCCESS']]
        if len(product_result) == 0:
            type_dict = {'샵링커상품코드': np.str, '고객사상품코드': np.str, '상품명': np.str, '상품약어': np.str,
                         '샵링커카테고리': np.str, '모델명': np.str, '모델명No': np.str, '시작가격': np.int32, '공급가격': np.int32,
                         '판매가격': np.int32, '시중가격': np.int32, '공급가능수량': np.int32, '과세': np.str, '거래처아이디': np.str,
                         '제조사': np.str, '원산지': np.str, '판매지역': np.str, '남여구분': np.str, '판매상태': np.str,
                         '옵션명1': np.str, '옵션항목1': np.str, '옵션명2': np.str, '옵션항목2': np.str, '옵션명3': np.str,
                         '옵션항목3': np.str, '상품이미지': np.str, '배송비부과여부': np.str, '배송비': np.str,
                         '상품요약설명': np.str, '상품상세설명': np.str, '브랜드명': np.str, '고객사분류코드(대)': np.str,
                         '고객사분류코드(중)': np.str, '고객사분류코드(소)': np.str, '고객사분류코드(세)': np.str,
                         '자체 공급가': np.int32, '자체 판매가': np.int32, '자체 시중가': np.int32, '옥션&지마켓 이미지': np.str,
                         '쿠팡 이미지': np.str, '11번가 목록용': np.str, '종합몰용이미지': np.str, '카운터사용여부': np.str,
                         '배송정보': np.str, 'A/S정보': np.str, '등록일자': None, '최종수정일자': np.str, '상품이미지.1': np.str}
            data_list = pd.read_excel(file.original.path, dtype=type_dict)
            # data_list = excel_to_dict(file.original.path, full=True, dict=False)
            new_product_list = Product.objects.values('product_code', 'filtered_description').filter(Q(file_id=file_id) & Q(change=True))
            for new_product in new_product_list:
                data_list.loc[data_list['고객사상품코드'] == int(new_product['product_code']), '상품상세설명'] = new_product['filtered_description']
            new_file_name = file.original.path.split('.xlsx')[0] + '_filtered.xls'
            data_list.to_excel(new_file_name, index=False, columns=['샵링커상품코드', '고객사상품코드', '상품명', '상품약어', '샵링커카테고리', '모델명', '모델명No', '시작가격', '공급가격', '판매가격', '시중가격', '공급가능수량', '과세', '거래처아이디', '제조사', '원산지', '판매지역', '남여구분', '판매상태', '옵션명1', '옵션항목1', '옵션명2', '옵션항목2', '옵션명3', '옵션항목3', '상품이미지', '배송비부과여부', '배송비', '상품요약설명', '상품상세설명', '브랜드명', '고객사분류코드(대)', '고객사분류코드(중)', '고객사분류코드(소)', '고객사분류코드(세)', '자체 공급가', '자체 판매가', '자체 시중가', '옥션&지마켓 이미지', '쿠팡 이미지', '11번가 목록용', '종합몰용이미지', '카운터사용여부', '배송정보', 'A/S정보', '등록일자', '최종수정일자', '상품이미지'])

            # 파일 정리
            file.filtered = new_file_name.split('/media/')[1]
            file.status = 7
            file.save()
            is_finish = True
        else:
            time.sleep(5)
            continue