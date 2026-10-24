
from django.urls import path

from .views import VerificationCheckView, VerificationHistoryView

urlpatterns = [
    path(
        "check/",
        VerificationCheckView.as_view(),
        name="verification-check",
    ),
    path(
        "history/",
        VerificationHistoryView.as_view(),
        name="verification-history",
    ),
]
