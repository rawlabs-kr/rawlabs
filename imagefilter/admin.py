from django.contrib import admin

from imagefilter.models import File, Product, Image


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'num_product', 'num_image', 'status', 'error', 'timestamp']
    list_filter = ['user__company', 'user', 'status']

    def get_queryset(self, request):
        queryset = super(FileAdmin, self).get_queryset(request)
        return queryset.valeus('user', 'title', 'num_product', 'num_image', 'status', 'error', 'timestamp')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    pass


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    pass