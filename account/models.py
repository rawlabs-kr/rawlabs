import uuid

from django.contrib.auth.base_user import BaseUserManager, AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models


def generate_uuid():
    return uuid.uuid4().hex


class Company(models.Model):
    hex = models.CharField(primary_key=True, null=False, blank=False, unique=True,
                           default=generate_uuid, max_length=64)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='등록일')
    company_name = models.CharField(max_length=100, null=False, blank=False, verbose_name='업체명', unique=True)
    contact = models.CharField(max_length=30, null=False, blank=False, verbose_name='연락처')
    is_approved = models.BooleanField(default=False, verbose_name='사용승인')


class CustomUserManager(BaseUserManager):
    def create_user(self, email, name, password=None):
        if not email:
            raise ValueError('이메일 주소는 필수 항목입니다.')

        user = self.model(email=self.normalize_email(email), name=name)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password):
        user = self.create_user(
            email=email,
            name=name,
            password=password
        )
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)
        return user


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(
        verbose_name='이메일',
        max_length=255,
        unique=True
    )
    name = models.CharField(max_length=10, null=False, blank=False, verbose_name='성명')
    company = models.ForeignKey(Company,
                                verbose_name='소속업체',
                                on_delete=models.PROTECT,
                                null=True, blank=True)
    is_company_admin = models.BooleanField(default=False,
                                           verbose_name='소속업체 관리자')
    is_active = models.BooleanField(default=True, verbose_name='활성화')
    is_staff = models.BooleanField(default=False, verbose_name='서비스 관리자')
    date_joined = models.DateTimeField(
        verbose_name='가입일',
        auto_now_add=True
    )
    objects = CustomUserManager()

    USERNAME_FIELD = 'email'

    def __str__(self):
        return self.email
