from django.contrib import admin

from imagefilter.models import File, Product, Image


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ['user__company', 'user', 'title', 'num_product', 'num_image', 'status', 'error', 'timestamp']
    list_filter = ['user__company', 'user', 'status']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    pass


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    pass