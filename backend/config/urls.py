from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/certificates/", include("apps.certificates.urls")),
    path("api/verification/", include("apps.verification.urls")),
    path("api/dashboard/", include("apps.dashboard.urls")),
    path("api/audit/", include("apps.audit.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
