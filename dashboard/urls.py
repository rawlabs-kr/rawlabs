from django.urls import path, include

from dashboard.views import DashboardIndexView, CompanyDetailView, CompanyUserListView, \
    CompanyUserCreateView

app_name = 'dashboard'

urlpatterns = [
    path('', DashboardIndexView.as_view(), name='index'),
    path('company', CompanyDetailView.as_view(), name='company'),
    path('company/user/', CompanyUserListView.as_view(), name='user_list'),
    path('company/user/create/', CompanyUserCreateView.as_view(), name='user_create'),
    path('imagefilter/', include('imagefilter.urls', namespace='imagefilter')),
]