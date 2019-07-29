from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include


admin.sites.site_title = 'rawlabs'
admin.sites.site_header = 'rawlabs'
admin.sites.index_title = 'rawlabs'

urlpatterns = [
    path('', include('landing.urls', namespace='landing')),
    path('admin/', admin.site.urls),
    path('account/', include('account.urls', namespace='account')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard'))
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
