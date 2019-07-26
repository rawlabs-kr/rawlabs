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
from imagefilter.views import check_file_async, filter_image_async, delete_file, generate_file

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


class ImageFileListView(LoginRequiredMixin, ListView):
    paginate_by = 10
    template_name = 'dashboard/imagefilter/file/list.html'

    def get_queryset(self):
        user = self.request.user
        return File.objects.filter(user=user).annotate(num_include=Count('product__image', filter=Q(product__image__type=4)),
                                                       num_exclude=Count('product__image', filter=Q(product__image__type=3)),
                                                       num_processed=Count('product__image', filter=Q(product__image__type__in=[1,3,4])))


class ImageFileCreateView(LoginRequiredMixin, View):
    def get(self, request):
        if not request.user.company.is_approved:
            return HttpResponseRedirect(reverse_lazy('landing:not_approved'))
        form = FileCreateForm()
        return render(request, template_name='dashboard/imagefilter/file/create.html', context={'form': form})

    def post(self, request):
        if not request.user.company.is_approved:
            return HttpResponseRedirect(reverse_lazy('landing:not_approved'))
        form = FileCreateForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.save(commit=False)
            file.user = request.user
            file.save()
            return HttpResponseRedirect(reverse_lazy('dashboard:imagefilter_list'))
        else:
            return render(request, template_name='dashboard/imagefilter/file/create.html', context={'form': form})


class ImageFileActionView(LoginRequiredMixin, View):
    def post(self, request):
        if not request.user.company.is_approved:
            return HttpResponseRedirect(reverse_lazy('landing:not_approved'))
        data = request.POST
        file_id = data.get('file_id')
        try:
            file = File.objects.get(id=file_id)
        except File.DoesNotExist:
            return HttpResponseRedirect(reverse_lazy('landing:not_found'))
        else:
            if not file.user == request.user:
                return HttpResponseRedirect(reverse_lazy('landing:permission_denied'))
        action = data.get('action')
        if action == 'checkFile':
            context = check_file_async(file_id)
        elif action == 'filterImage':
            context = filter_image_async(file_id)
        elif action == 'generateFile':
            context = generate_file(file_id)
        elif action == 'delete':
            context = delete_file(file_id)
        else:
            context = {'result': False, 'message': '잘못된 요청'}
        return HttpResponse(json.dumps(context), content_type='application/json')


class ProductListView(LoginRequiredMixin, ListView):
    paginate_by = 30
    template_name = 'dashboard/imagefilter/product/list.html'

    def get_queryset(self):
        return Product.objects.values('product_code', 'name', 'id', 'file_id', 'change').filter(file_id=self.kwargs['file_id']).\
            annotate(num_image=Count('image'), num_exclude=Count('image', filter=Q(image__type=3)))


class ProductDetailView(LoginRequiredMixin, View):
    def get(self, request, file_id, product_id):
        try:
            product = Product.objects.select_related('file').get(Q(id=product_id) & Q(file_id=file_id))
        except Product.DoesNotExist:
            return HttpResponseRedirect(reverse_lazy('landing:not_found'))
        else:
            if not product.file.user == request.user:
                return HttpResponseRedirect(reverse_lazy('landing:permission_denied'))
        return render(request, template_name='dashboard/imagefilter/product/detail.html', context={'product': product})


class ImageListView(LoginRequiredMixin, ListView):
    paginate_by = 30
    template_name = 'dashboard/imagefilter/image/list.html'

    def get_queryset(self):
        return Image.objects.values('type', 'uri', 'product__product_code', 'product__name', 'product_id', 'product__file_id').filter(product__file_id=self.kwargs['file_id'])