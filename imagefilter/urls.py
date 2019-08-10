from django.urls import path

from imagefilter.views import ImageFileListView, ImageFileCreateView, ImageFileActionView, ProductListView, \
    ProductDetailView, ImageListView, ImageTypeChangeView

app_name = 'imagefilter'

urlpatterns = [
    path('file/', ImageFileListView.as_view(), name='list'),
    path('file/create/', ImageFileCreateView.as_view(), name='create'),
    path('file/action/', ImageFileActionView.as_view(), name='action'),
    path('file/<int:file_id>/product/', ProductListView.as_view(), name='product_list'),
    path('file/<int:file_id>/product/<int:product_id>/', ProductDetailView.as_view(), name='product_detail'),
    path('file/<int:file_id>/image/', ImageListView.as_view(), name='image_list'),
    path('image/<int:image_id>/', ImageTypeChangeView.as_view(), name='image_type_change'),
]