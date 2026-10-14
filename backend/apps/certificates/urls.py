
from django.urls import path

from .views import (
    CertificateDetailView,
    CertificateListCreateView,
    CertificateReviewView,
    CertificateVerifyView,
    CertificatePDFUploadView,
    CertificatePDFDownloadView,
    CourseListCreateView,
    CourseDetailView,
    CertificateTemplateListCreateView,
    CertificateTemplateDetailView,
    CSVTemplateDownloadView,
    ValidateCSVView,
    BulkGenerateView,
    SingleGenerateView,
    PreviewCertificateView,
    BatchListView,
    BatchDetailView,
    RetryEmailView,
    CertificateImageView,
)

urlpatterns = [
    # Certificate CRUD
    path(
        "",
        CertificateListCreateView.as_view(),
        name="certificate-list-create",
    ),
    path(
        "verify/<str:certificate_number>/",
        CertificateVerifyView.as_view(),
        name="certificate-verify",
    ),
    path(
        "<int:pk>/",
        CertificateDetailView.as_view(),
        name="certificate-detail",
    ),
    path(
        "<int:pk>/review/",
        CertificateReviewView.as_view(),
        name="certificate-review",
    ),

    # Course management
    path(
        "courses/",
        CourseListCreateView.as_view(),
        name="course-list-create",
    ),
    path(
        "courses/<int:pk>/",
        CourseDetailView.as_view(),
        name="course-detail",
    ),

    # Certificate Templates
    path(
        "templates/",
        CertificateTemplateListCreateView.as_view(),
        name="template-list-create",
    ),
    path(
        "templates/<int:pk>/",
        CertificateTemplateDetailView.as_view(),
        name="template-detail",
    ),

    # Certificate Generation & Distribution
    path(
        "generate/csv-template/",
        CSVTemplateDownloadView.as_view(),
        name="csv-template-download",
    ),
    path(
        "generate/validate-csv/",
        ValidateCSVView.as_view(),
        name="validate-csv",
    ),
    path(
        "generate/bulk/",
        BulkGenerateView.as_view(),
        name="bulk-generate",
    ),
    path(
        "generate/single/",
        SingleGenerateView.as_view(),
        name="single-generate",
    ),
    path(
        "generate/preview/",
        PreviewCertificateView.as_view(),
        name="preview-certificate",
    ),
    path(
        "generate/batches/",
        BatchListView.as_view(),
        name="batch-list",
    ),
    path(
        "generate/batches/<int:pk>/",
        BatchDetailView.as_view(),
        name="batch-detail",
    ),

    # PostgreSQL-backed PDF management
    path(
        "<int:pk>/pdf/",
        CertificatePDFUploadView.as_view(),
        name="certificate-pdf-upload",
    ),
    path(
        "<int:pk>/pdf/download/",
        CertificatePDFDownloadView.as_view(),
        name="certificate-pdf-download",
    ),

    # Image streaming and Email retry
    path(
        "<int:pk>/image/",
        CertificateImageView.as_view(),
        name="certificate-image",
    ),
    path(
        "<int:pk>/retry-email/",
        RetryEmailView.as_view(),
        name="retry-email",
    ),
]
