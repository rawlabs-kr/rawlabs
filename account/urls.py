from django.urls import path, include
from django.views.generic import TemplateView

from account.views import CustomSignupWithCompanyView, CustomLoginView, logout_view

app_name = 'account'
urlpatterns = [
    path('signup/', CustomSignupWithCompanyView.as_view(), name='signup'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout')
]
