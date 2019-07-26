from django.urls import path, include
from django.views.generic import TemplateView

from landing.views import LandingIndexView

app_name = 'landing'

urlpatterns = [
    path('', LandingIndexView.as_view(), name='index'),
    path('notapproved/', TemplateView.as_view(template_name='landing/etc/not_approved.html'), name='not_approved'),
    path('500/', TemplateView.as_view(template_name='landing/etc/permission_denied.html'), name='permission_denied'),
    path('404/', TemplateView.as_view(template_name='landing/etc/not_found.html'), name='not_found')
]

