import json

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.views import View
from django.views.generic import ListView

import django_tables2 as tables
from django_filters import FilterSet
from django_filters.views import FilterView

from imagefilter.actions import check_file_async, filter_image_async, delete_file, generate_file
from imagefilter.forms import FileCreateForm
from imagefilter.models import File, Product, Image

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
        file = get_object_or_404(File.objects.filter(), id=file_id)
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


class ImageTable(tables.Table):
    class Meta:
        model = Image
        template_name = 'dashboard/imagefilter/image/bootstrap4.html'
        attrs = {'class': 'table table-striped bg-white'}
        fields = ('product', 'uri', 'type', 'action')
        sequence = ('product', 'type', 'uri', 'action')

    uri = tables.Column(verbose_name='이미지')
    type = tables.Column()
    product = tables.Column()
    action = tables.Column(accessor='id', verbose_name='변경')

    def render_uri(self, record):
        html = """<button type="button" class="btn btn-primary btn-sm" data-toggle="popover" data-img="{uri}" title="미리보기" onclick="window.open('{uri}', '_blank')">미리보기</button>""".format(
            uri=record.uri)
        return mark_safe(html)

    def render_product(self, record):
        html = """<a href="{url}">[{code}] {name}</a>""".format(url=reverse_lazy('dashboard:imagefilter:product_detail',
                                                                                 kwargs={
                                                                                     'file_id': record.product.file.id,
                                                                                     'product_id': record.product.id}),
                                                                code=record.product.product_code,
                                                                name=record.product.name)
        return mark_safe(html)

    def render_type(self, record):
        if record.type == 0:
            return '분류 전'
        elif record.type == 1:
            text = """<span class="text-warning font-weight-bold">분류실패</span>"""
            return mark_safe(text)
        elif record.type == 2:
            return '분류 중'
        elif record.type == 3:
            text = """<span class="text-danger font-weight-bold">제외</span>"""
            return mark_safe(text)
        elif record.type == 4:
            text = """<span class="text-primary font-weight-bold">포함</span>"""
            return mark_safe(text)

    def render_action(self, record):
        if record.type == 1:
            text = """<button type="button" class="btn btn-primary btn-sm" onclick='changeType({id}, 4);'>포함처리</button>
            <button type="button" class="btn btn-danger btn-sm" onclick='changeType({id}, 3);'>제외처리</button>""".format(id=record.id)
        elif record.type == 3:
            text = """<button type="button" class="btn btn-primary btn-sm" onclick='changeType({id}, 4);'>포함처리</button>
            <button type="button" class="btn btn-danger btn-sm" disabled onclick='changeType({id}, 3);'>제외처리</button>""".format(id=record.id)
        elif record.type == 4:
            text = """<button type="button" class="btn btn-primary btn-sm" disabled onclick='changeType({id}, 4);'>포함처리</button>
            <button type="button" class="btn btn-danger btn-sm" onclick='changeType({id}, 3);'>제외처리</button>""".format(id=record.id)
        else:
            text = """<button type="button" class="btn btn-primary btn-sm" disabled onclick='changeType({id}, 4);'>포함처리</button>
            <button type="button" class="btn btn-danger btn-sm" disabled onclick='changeType({id}, 3);'>제외처리</button>""".format(id=record.id)
        return mark_safe(text)


class ImageTypeFilter(FilterSet):
    class Meta:
        model = Image
        fields = ['type']


class ImageListView(tables.views.SingleTableMixin, FilterView):
    table_class = ImageTable
    model = Image
    template_name = 'dashboard/imagefilter/image/list.html'

    filterset_class = ImageTypeFilter

    def get_queryset(self):
        file_id = self.kwargs.get('file_id', None)
        file = get_object_or_404(File, id=file_id)
        if not file.has_permission(self.request.user):
            return HttpResponseRedirect(reverse_lazy('landing:permission_denied'))
        filter = Q(product__file=file)
        return Image.objects.filter(filter)


class ImageTypeChangeView(View):
    def post(self, request, image_id):
        image = get_object_or_404(Image, Q(id=image_id))

        if image.type in [0, 2]:
            context = {'result': False, 'message': '분류 전, 분류중 파일은 변경할 수 없습니다.'}
            return HttpResponse(json.dumps(context), content_type='application/json')

        if not image.has_permission(request.user):
            context = {'result': False, 'message': '권한이 없습니다.'}
            return HttpResponse(json.dumps(context), content_type='application/json')

        type = int(request.POST.get('type', None))
        if type not in [3, 4]:
            context = {'result': False, 'message': '잘못된 타입.'}
            return HttpResponse(json.dumps(context), content_type='application/json')
        else:
            image.type = type
            image.save()
            context = {'result': True, 'message': '성공.'}
            return HttpResponse(json.dumps(context), content_type='application/json')





