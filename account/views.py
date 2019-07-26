from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.views import LoginView
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView

from account.forms import CustomUserCreationForm, CustomLoginForm, CustomUserCreationWithCompanyForm
from account.models import Company


class CustomSignupWithCompanyView(View):
    def get(self, request):
        form = CustomUserCreationWithCompanyForm()
        return render(request, template_name='landing/account/signup.html', context={'form': form})

    def post(self, request):
        form = CustomUserCreationWithCompanyForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return HttpResponseRedirect(reverse_lazy('dashboard:index'))
        else:
            return render(request, template_name='landing/account/signup.html', context={'form': form})


class CustomLoginView(View):
    def get(self, request):
        form = CustomLoginForm()
        return render(request, template_name = 'landing/account/login.html', context={'form': form})

    def post(self, request):
        form = CustomLoginForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            user = authenticate(email=data['email'], password=data['password'])
            login(request, user)
            return HttpResponseRedirect(reverse_lazy('dashboard:index'))
        else:
            return render(request, template_name='landing/account/login.html', context={'form': form})


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse_lazy('landing:index'))
