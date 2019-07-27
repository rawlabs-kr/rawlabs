from django.contrib import admin

from imagefilter.models import File, Product, Image


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    pass


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    pass


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    pass