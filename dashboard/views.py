import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count, When
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseServerError
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView, ListView, CreateView

from account.forms import CompanyViewForm, CompanyUpdateForm, CustomUserCreationForm
from imagefilter.forms import FileCreateForm
from imagefilter.models import File, Product, Image
from imagefilter.actions import check_file_async, filter_image_async, delete_file, generate_file

User = get_user_model()


class DashboardIndexView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'


class CompanyDetailView(LoginRequiredMixin, View):

    def get(self, request):
        if not request.user.company.is_approved:
            return HttpResponseRedirect(reverse_lazy('landing:not_approved'))
        company = request.user.company
        if request.user.is_company_admin:
            form = CompanyUpdateForm(instance=company)
        else:
            form = CompanyViewForm(instance=company)
        return render(request, template_name='dashboard/company/detail.html', context={'form': form})

    def post(self, request):
        if not request.user.company.is_approved:
            return HttpResponseRedirect(reverse_lazy('landing:not_approved'))
        company = request.user.company
        if request.user.is_company_admin:
            form = CompanyUpdateForm(instance=company, data=request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, '업체정보가 수정되었습니다.')
                return render(request, template_name='dashboard/company/detail.html', context={'form': form})
            else:
                messages.error(request, '업체정보 수정 실패.')
                return render(request, template_name='dashboard/company/detail.html', context={'form': form})
        else:
            return HttpResponseRedirect(reverse_lazy('dashboard:nopermission'))


class CompanyUserListView(LoginRequiredMixin, ListView):
    paginate_by = 10
    template_name = 'dashboard/users/list.html'

    def get_queryset(self):
        company = self.request.user.company
        return User.objects.values('name', 'email', 'date_joined', 'last_login', 'is_company_admin').filter(
            company=company)


class CompanyUserCreateView(LoginRequiredMixin, View):
    def get(self, request):
        if not request.user.is_company_admin:
            return HttpResponseRedirect(reverse_lazy('landing:permission_denied'))
        form = CustomUserCreationForm()
        return render(request, template_name='dashboard/users/create.html', context={'form': form})

    def post(self, request):
        form = CustomUserCreationForm(request.POST)
        if not request.user.is_company_admin:
            return HttpResponseRedirect(reverse_lazy('landing:permission_denied'))
        if form.is_valid():
            company = request.user.company
            user = form.save(commit=False)
            user.company = company
            user.save()
            messages.success(request, '사용자가 추가되었습니다.')
            return HttpResponseRedirect(reverse_lazy('dashboard:user_list'))
        else:
            return render(request, template_name='dashboard/users/create.html', context={'form': form})


