from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import JSONField
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Count, Case, Sum, When

User = get_user_model()

FILE_STATUS_CHOICES = ((0, '파일업로드'),
                       (1, '파일 검증중'), (2, '파일 검증 실패'), (3, '상품/이미지 등록 완료'),
                       (4, '이미지 분류중'), (5, '이미지 분류 완료'),
                       (6, '파일 생성중'), (7, '파일 생성 완료'))

FILE_ERROR_CHOICES = ((0, '파일 읽기 에러'), (1, '상품/이미지 추출 에러'), (2, '알 수 없는 오류'))


class File(models.Model):
    class Meta:
        verbose_name = '파일'
        verbose_name_plural = verbose_name
        ordering = ('-timestamp',)

    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    title = models.CharField(max_length=100, null=False, blank=False, verbose_name='작업명')
    user = models.ForeignKey(User, null=False, blank=True, on_delete=models.PROTECT, verbose_name='사용자',
                             editable=False, db_index=True)
    original = models.FileField(max_length=500, null=False, blank=False, verbose_name='원본파일', upload_to='imagefilter/file/%Y/%m/%d',
                                validators=[FileExtensionValidator(allowed_extensions=['xlsx', 'xls'])])
    filtered = models.FileField(max_length=500, null=True, blank=True, verbose_name='필터링된 파일', editable=False)
    num_product = models.IntegerField(null=True, blank=True, verbose_name='상품 수')
    num_image = models.IntegerField(null=True, blank=True, verbose_name='이미지 수')

    status = models.IntegerField(choices=FILE_STATUS_CHOICES, default=0, null=False, blank=False, verbose_name='상태',
                                 editable=False)
    error = models.IntegerField(choices=FILE_ERROR_CHOICES, null=True, blank=True, verbose_name='에러', editable=False)

    def __str__(self):
        return self.original.path.split('/')[-1]

    def has_permission(self, user):
        if user.is_company_admin:
            if self.user.company == user.company:
                return True
        else:
            if self.user == user:
                return True
        return False


class Product(models.Model):
    class Meta:
        verbose_name = '상품'
        verbose_name_plural = verbose_name
        unique_together = (('file', 'product_code'),)
        ordering = ('-id',)

    file = models.ForeignKey(File, null=False, blank=False, verbose_name='파일', on_delete=models.PROTECT,
                             editable=False, db_index=True)
    product_code = models.CharField(max_length=500, db_index=True, verbose_name='고객사코드', editable=False)
    name = models.CharField(max_length=500, db_index=True, verbose_name='상품명', editable=False)
    original_description = models.TextField(null=True, blank=True, verbose_name='원본 상세설명')
    filtered_description = models.TextField(null=True, blank=True, verbose_name='필터링후 상세설명')
    change = models.NullBooleanField(default=None, verbose_name='필터링 후 변동')

    def __str__(self):
        return self.name

IMAGE_TYPE_CHOICES = ((0, '분류 전'), (1, '분류 실패'), (2, '분류중'), (3, '제외'), (4, '포함'),)


class Image(models.Model):
    class Meta:
        verbose_name = '이미지'
        verbose_name_plural = verbose_name
        ordering = ('-product', '-id',)

    filter_dt = models.DateTimeField(null=True, blank=True, verbose_name='분류일시', editable=False)
    product = models.ForeignKey(Product, null=False, blank=False, verbose_name='상품', on_delete=models.PROTECT, db_index=True)
    uri = models.TextField(null=False, blank=False, verbose_name='이미지 uri')
    extracted_text = JSONField(null=True, blank=True, verbose_name='이미지 분석 결과')
    type = models.IntegerField(choices=IMAGE_TYPE_CHOICES, default=0, verbose_name='분류결과')
    error = models.TextField(null=True, blank=True, verbose_name='에러')
    google_api_error_code = models.IntegerField(null=True, blank=True, verbose_name='구글 에러 코드')
    google_api_error_msg = models.TextField(null=True, blank=True, verbose_name='구글 에러 메시지')
