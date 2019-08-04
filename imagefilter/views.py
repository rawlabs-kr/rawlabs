import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView

from account.models import Company
from imagefilter.forms import FileCreateForm
from imagefilter.models import File, Product, Image
from imagefilter.tasks import create_product_and_image, filter_image, generate_product_description


def check_file_async(file_id):
    with transaction.atomic():
        try:
            file = File.objects.select_for_update().get(id=file_id)
        except File.DoesNotExist:
            return {'result': False, 'message': '존재하지 않는 파일입니다.'}
        except Exception as e:
            return {'result': False, 'message': '알 수 없는 오류 : {}'.format(str(e))}
        else:
            if file.status != 0:
                return {'result': False, 'message': '[파일업로드] 상태의 파일만 검증할 수 있습니다.'}
            file.status = 1
            file.error = None
            file.save()
            create_product_and_image.delay(file_id)
            return {'result': True, 'message': '요청되었습니다.'}


def filter_image_async(file_id):
    with transaction.atomic():
        try:
            file = File.objects.select_for_update().get(id=file_id)
        except File.DoesNotExist:
            return {'result': False, 'message': '존재하지 않는 파일입니다.'}
        except Exception as e:
            return {'result': False, 'message': '알 수 없는 오류 : {}'.format(str(e))}
        else:
            if file.status != 3:
                return {'result': False, 'message': '[상품/이미지 등록 완료] 상태의 파일만 분류할 수 있습니다.'}
            file.status = 4
            file.error = None
            file.save()
            filter_image.delay(file_id, 'zh')
            # filter_image.delay(file_id, 'zh')
            return {'result': True, 'message': '요청되었습니다.'}


def delete_file(file_id):
    with transaction.atomic():
        file = File.objects.select_for_update().get(id=file_id)
        file_status = file.status
        if file_status not in [0, 2, 3]:
            return {'result': False, 'message': '파일업로드, 파일 검증 실패, 상품/이미지 등록 완료 건만 삭제할 수 있습니다.'}

        # 삭제 순서 주의
        Image.objects.filter(product__file_id=file_id).delete()
        Product.objects.filter(file_id=file_id).delete()
        file.delete()
        return {'result': True, 'message': '파일 삭제 완료.'}


def generate_file(file_id):
    with transaction.atomic():
        try:
            file = File.objects.select_for_update().get(id=file_id)
        except File.DoesNotExist:
            return {'result': False, 'message': '해당 파일을 찾을 수 없습니다.'}
        else:
            file_status = file.status
            if file_status != 5:
                return {'result': False, 'message': '이미지 분류 완료건만 생성할 수 있습니다.'}
            file.status = 6
            file.save()
            generate_product_description.delay(file_id)
            return {'result': True, 'message': '요청되었습니다.'}


User = get_user_model()


class ImageFileListView(LoginRequiredMixin, ListView):
    paginate_by = 10
    template_name = 'dashboard/imagefilter/file/list.html'

    def get_queryset(self):
        user = self.request.user
        if user.is_company_admin:
            company_user_list = User.objects.filter(company=user.company)
            filter = Q(user__in=company_user_list)
        else:
            filter = Q(user=user)
        return File.objects.filter(filter).annotate(
            num_include=Count('product__image', filter=Q(product__image__type=4)),
            num_exclude=Count('product__image', filter=Q(product__image__type=3)),
            num_error=Count('product__image', filter=Q(product__image__type=1)),
            num_processed=Count('product__image', filter=Q(product__image__type__in=[1, 3, 4]))).select_related('user')


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
            return HttpResponseRedirect(reverse_lazy('dashboard:imagefilter:list'))
        else:
            return render(request, template_name='dashboard/imagefilter/file/create.html', context={'form': form})


class ImageFileActionView(LoginRequiredMixin, View):
    def post(self, request):
        if not request.user.company.is_approved:
            return HttpResponseRedirect(reverse_lazy('landing:not_approved'))
        data = request.POST
        file_id = data.get('file_id', None)
        file = get_object_or_404(File, id=file_id)
        if not file.has_permission(request.user):
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
        file_id = self.kwargs.get('file_id', None)
        file = get_object_or_404(File, id=file_id)
        if not file.has_permission(self.request.user):
            return HttpResponseRedirect(reverse_lazy('landing:permission_denied'))

        return Product.objects.values('product_code', 'name', 'id', 'file_id', 'change').filter(file=file). \
            annotate(num_image=Count('image'), num_exclude=Count('image', filter=Q(image__type=3)))


class ProductDetailView(LoginRequiredMixin, View):
    def get(self, request, file_id, product_id):
        file = get_object_or_404(File, id=file_id)
        if not file.has_permission(self.request.user):
            return HttpResponseRedirect(reverse_lazy('landing:permission_denied'))

        try:
            product = Product.objects.select_related('file').get(Q(id=product_id) & Q(file=file))
        except Product.DoesNotExist:
            return HttpResponseRedirect(reverse_lazy('landing:not_found'))
        else:
            if not product.file.user == request.user:
                return HttpResponseRedirect(reverse_lazy('landing:permission_denied'))
        return render(request, template_name='dashboard/imagefilter/product/detail.html', context={'product': product})


class ImageListView(LoginRequiredMixin, ListView):
    paginate_by = 30
    template_name = 'dashboard/imagefilter/image/list.html'

    def __init__(self):
        super(ImageListView, self).__init__()
        file_id = self.kwargs.get('file_id', None)
        self.file = get_object_or_404(File, id=file_id)

    def get_queryset(self):
        if not self.file.has_permission(self.request.user):
            return HttpResponseRedirect(reverse_lazy('landing:permission_denied'))
        status = self.request.GET.get('status', None)
        filter = Q(product__file=self.file)
        if status:
            filter = filter.add(Q(status=status), Q.AND)
        return Image.objects.values('id', 'type', 'uri', 'product__product_code', 'product__name', 'product_id',
                                    'product__file_id', 'error').filter(filter)

