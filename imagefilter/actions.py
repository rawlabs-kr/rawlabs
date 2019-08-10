from django.db import transaction

from imagefilter.models import File, Image, Product
from imagefilter.tasks import create_product_and_image, filter_image, generate_product_description


def check_file_async(file_id):
    with transaction.atomic():
        try:
            file = File.objects.select_for_update().get(id=file_id)
        except File.DoesNotExist:
            return {'result': False, 'message': '존재하지 않는 파일입니다.'}
        except Exception as e:
            return {'result': False, 'message': '알 수 없는 오류 : {}'.format(str(e))}
        else:
            if file.status != 0:
                return {'result': False, 'message': '[파일업로드] 상태의 파일만 검증할 수 있습니다.'}
            file.status = 1
            file.error = None
            file.save()
            create_product_and_image.delay(file_id)
            return {'result': True, 'message': '요청되었습니다.'}


def filter_image_async(file_id):
    with transaction.atomic():
        try:
            file = File.objects.select_for_update().get(id=file_id)
        except File.DoesNotExist:
            return {'result': False, 'message': '존재하지 않는 파일입니다.'}
        except Exception as e:
            return {'result': False, 'message': '알 수 없는 오류 : {}'.format(str(e))}
        else:
            if file.status != 3:
                return {'result': False, 'message': '[상품/이미지 등록 완료] 상태의 파일만 분류할 수 있습니다.'}
            file.status = 4
            file.error = None
            file.save()
            filter_image.delay(file_id, 'zh')
            # filter_image.delay(file_id, 'zh')
            return {'result': True, 'message': '요청되었습니다.'}


def delete_file(file_id):
    with transaction.atomic():
        file = File.objects.select_for_update().get(id=file_id)
        file_status = file.status
        if file_status not in [0, 2, 3]:
            return {'result': False, 'message': '파일업로드, 파일 검증 실패, 상품/이미지 등록 완료 건만 삭제할 수 있습니다.'}

        # 삭제 순서 주의
        Image.objects.filter(product__file_id=file_id).delete()
        Product.objects.filter(file_id=file_id).delete()
        file.delete()
        return {'result': True, 'message': '파일 삭제 완료.'}


def generate_file(file_id):
    with transaction.atomic():
        try:
            file = File.objects.select_for_update().get(id=file_id)
        except File.DoesNotExist:
            return {'result': False, 'message': '해당 파일을 찾을 수 없습니다.'}
        else:
            file_status = file.status
            if file_status != 5:
                return {'result': False, 'message': '이미지 분류 완료건만 생성할 수 있습니다.'}
            file.status = 6
            file.save()
            generate_product_description.delay(file_id)
            return {'result': True, 'message': '요청되었습니다.'}