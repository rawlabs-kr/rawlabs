from django.urls import path

from dashboard.views import DashboardIndexView, CompanyDetailView, CompanyUserListView, \
    CompanyUserCreateView, ImageFileListView, ImageFileCreateView, ImageFileActionView, ProductListView, ImageListView, \
    ProductDetailView

app_name = 'dashboard'

urlpatterns = [
    path('', DashboardIndexView.as_view(), name='index'),
    path('company', CompanyDetailView.as_view(), name='company'),
    path('company/user/', CompanyUserListView.as_view(), name='user_list'),
    path('company/user/create/', CompanyUserCreateView.as_view(), name='user_create'),
    path('imagefilter/', ImageFileListView.as_view(), name='imagefilter_list'),
    path('imagefilter/create/', ImageFileCreateView.as_view(), name='imagefilter_create'),
    path('imagefilter/action/', ImageFileActionView.as_view(), name='imagefilter_action'),
    path('imagefilter/<int:file_id>/product/', ProductListView.as_view(), name='imagefilter_product_list'),
    path('imagefilter/<int:file_id>/product/<int:product_id>/', ProductDetailView.as_view(), name='imagefilter_product_detail'),
    path('imagefilter/<int:file_id>/image/', ImageListView.as_view(), name='imagefilter_image_list'),
]