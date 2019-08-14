from __future__ import absolute_import

import json
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
from google.cloud.vision_v1.proto.image_annotator_pb2 import AnnotateImageRequest

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


def chunker(seq, size):
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))


@app.task
def filter_image(file_id, excluded_locales):
    from imagefilter.models import Image
    from imagefilter.models import File
    image_list = list(Image.objects.values('id', 'uri').filter(Q(product__file_id=file_id) & Q(type=0)))
    image_chunk = chunker(image_list, 5)
    with open(settings.GOOGLE_VISION_API_CREDENTIAL_PATH, 'r') as json_credential:
        google_credential_info = json.loads(json_credential.read())

    credentials = service_account.Credentials.from_service_account_info(google_credential_info)
    client = vision_v1.ImageAnnotatorClient(credentials=credentials)
    features = [vision_v1.types.Feature(type=vision_v1.enums.Feature.Type.TEXT_DETECTION)]
    for chunk in image_chunk:
        requests = []
        for image_instance in chunk:
            # result = filter_single_image.delay(image_id, excluded_locales, google_client=client)
            uri = image_instance.get('uri')
            image = vision_v1.types.Image()
            image.source.image_uri = uri
            image_request = vision_v1.types.AnnotateImageRequest(image=image, features=features)
            requests.append(image_request)

            response = client.batch_annotate_images(requests)

            for idx, annotate_response in enumerate(response.responses):
                image_id = chunk[idx]['id']
                try:
                    data_dict = MessageToDict(annotate_response)
                    error = None
                except Exception as e:
                    data_dict = None
                    error = e
                filter_image_callback.delay(image_id, excluded_locales, data_dict, error)


@app.task
def filter_image_callback(image_id, excluded_locales, data_dict, error):
    _image_instance = Image.objects.select_related('product', 'product__file').get(id=image_id)
    if data_dict == None:
        _image_instance.type = 2
        _image_instance.error = str(error)
    else:
        _image_instance.extracted_text = data_dict
        _image_instance.save()
        text_annotations = data_dict.get('textAnnotations', None)
        error = data_dict.get('error', None)
        if text_annotations:  # 텍스트 인식 성공
            locale = text_annotations[0]['locale']
            if locale in [excluded_locales] if isinstance(excluded_locales, str) else excluded_locales:
                _image_instance.type = 3
            else:
                _image_instance.type = 4
        elif error:
            error = error
            _image_instance.type = 1
            _image_instance.error = error['message']
        elif data_dict == {}:
            # vision api가 빈 dictionary를 반환하면 글자가 없다고 판단한 것
            _image_instance.type = 4
        else:
            _image_instance.type = 1
            _image_instance.error = '관리자 문의'
    _image_instance.filter_dt = timezone.now()
    _image_instance.save()
    all_image = list(set(Image.objects.values_list('type', flat=True).filter(product__file=_image_instance.product.file)))

    if all_image.count(2) == 0 and all_image.count(0) == 0:
        file = _image_instance.product.file
        file.status = 5
        file.save()

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
            type_dict = {'샵링커상품코드': np.str, '고객사상품코드': np.str, '상품명': np.str, '약어': np.str,
                         '샵링커카테고리코드': np.str, '모델명': np.str, '모델No': np.str, '쇼핑몰시작가': np.int32, '쇼핑몰공급가': np.int32,
                         '쇼핑몰판매가': np.int32, '쇼핑몰시중가': np.int32, '수량': np.int32, '과세': np.str, '매입처ID': np.str,
                         '제조사': np.str,
                         '원산지': np.str, '판매지역': np.str, '남여구분': np.str, '판매상태': np.str, '옵션명1': np.str, '옵션항목1': np.str,
                         '옵션명2': np.str, '옵션항목2': np.str, '옵션명3': np.str, '옵션항목3': np.str, '상품대표이미지': np.str,
                         '배송비형태': np.str, '배송비': np.str, '상품요약설명': np.str, '상품상세설명': np.str, '신 상세설명': np.str,
                         '추가구성 상세': np.str, '광고홍보 상세설명': np.str, '브랜드': np.str, '고객사대분류코드': np.str,
                         '고객사중분류코드': np.str, '고객사소분류코드': np.str, '고객사세분류코드': np.str, '매입처공급가': np.int,
                         '매입처판매가': np.int, '매입처시중가': np.int, '옥션&지마켓용 이미지': np.str, '쿠팡 외 이미지': np.str,
                         '11번가용 이미지': np.str, '종합몰용이미지': np.str, '카운터 사용여부': np.str, '배송정보': np.str, 'A/S정보': np.str,
                         '부가이미지6': np.str,
                         '부가이미지7': np.str, '부가이미지8': np.str, '부가이미지9': np.str, '부가이미지10': np.str, '부가이미지11': np.str,
                         '부가이미지12': np.str,
                         '옥션&지마켓 추가이미지1': np.str, '옥션&지마켓 추가이미지2': np.str, '위메프(460*460, 500*500)': np.str,
                         '위메프(580*320)': np.str,
                         '발행일/제조일': np.str, 'W컨셉용이미지': np.str, '인증번호': np.str, '롯데홈(사용안함)': np.str,
                         '롯데홈(사용안함).1': np.str,
                         '롯데홈(사용안함).2': np.str, '유효기간': None, '성인상품여부': np.str, '반품지주소': np.str, '반품지우편번호': np.str,
                         '출하지주소': np.str,
                         '출하지우편번호': np.str, '옥션 이미지 삭제': np.str, '지마켓 이미지 삭제': np.str, '11번가 이미지 삭제': np.str,
                         '종합몰 이미지 삭제': np.str,
                         '품목고시 코드': np.str, '품목 값1': np.str, '품목 값2': np.str, '품목 값3': np.str, '품목 값4': np.str,
                         '품목 값5': np.str, '품목 값6': np.str,
                         '품목 값7': np.str, '품목 값8': np.str, '품목 값9': np.str, '품목 값10': np.str, '품목 값11': np.str,
                         '품목 값12': np.str,
                         '품목 값13': np.str, '품목 값14': np.str, '품목 값15': np.str, '인증항목 코드1': np.str, '기관명1': np.str,
                         '인증번호(심의번호)1': np.str,
                         '신고번호1': np.str, '인증발급일자1': None, '유효시작일자1': None, '유효종료일자1': None, '인증정보이미지1': np.str,
                         '인증항목 코드2': np.str,
                         '기관명2': np.str, '인증번호(심의번호)2': np.str, '신고번호2': np.str, '인증발급일자2': None, '유효시작일자2': None,
                         '유효종료일자2': None,
                         '인증정보이미지2': np.str, '인증항목 코드3': np.str, '기관명3': np.str, '인증번호(심의번호)3': np.str, '신고번호3': np.str,
                         '인증발급일자3': None,
                         '유효시작일자3': None, '유효종료일자3': None, '인증정보이미지3': np.str, '인증항목 코드4': np.str, '기관명4': np.str,
                         '인증번호(심의번호)4': np.str,
                         '신고번호4': np.str, '인증발급일자4': None, '유효시작일자4': None, '유효종료일자4': None, '인증정보이미지4': np.str,
                         '인증항목 코드5': np.str,
                         '기관명5': np.str, '인증번호(심의번호)5': np.str, '신고번호5': np.str, '인증발급일자5': None, '유효시작일자5': None,
                         '유효종료일자5': None,
                         '인증정보이미지5': np.str, '하프클럽 가로배너\nGS/이지웰 모바일 이미지\nB쇼핑 MC이미지': np.str, '품질표시 TAG': np.str,
                         '무게': np.str}
            data_list = pd.read_excel(file.original.path, dtype=type_dict)
            # data_list = excel_to_dict(file.original.path, full=True, dict=False)
            new_product_list = Product.objects.values('product_code', 'filtered_description').filter(
                Q(file_id=file_id) & Q(change=True))
            for new_product in new_product_list:
                data_list.loc[data_list['고객사상품코드'] == int(new_product['product_code']), '상품상세설명'] = new_product[
                    'filtered_description']
            new_file_name = file.original.path.split('.xlsx')[0] + '_filtered.xls'
            data_list.to_excel(new_file_name, index=False, columns=list(type_dict.keys()))

            # 파일 정리
            file.filtered = new_file_name.split('/media/')[1]
            file.status = 7
            file.save()
            is_finish = True
        else:
            time.sleep(5)
            continue
