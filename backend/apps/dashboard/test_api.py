
from datetime import date

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.certificates.models import Certificate


User = get_user_model()


class DashboardAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dashboard_test_user",
            password="TestPass123!",
        )
        self.other_user = User.objects.create_user(
            username="dashboard_other_user",
            password="TestPass123!",
        )
        self.admin = User.objects.create_superuser(
            username="dashboard_test_admin",
            email="dashboard-admin@example.com",
            password="TestPass123!",
        )

        Certificate.objects.create(
            owner=self.user,
            title="Verified Certificate",
            issuer="OneSmarter Inc.",
            certificate_number="DASH-TEST-001",
            recipient_name="Test User",
            issue_date=date(2026, 10, 11),
            status=Certificate.Status.VERIFIED,
        )
        Certificate.objects.create(
            owner=self.user,
            title="Pending Certificate",
            issuer="OneSmarter Inc.",
            certificate_number="DASH-TEST-002",
            recipient_name="Test User",
            issue_date=date(2026, 10, 11),
            status=Certificate.Status.PENDING,
        )
        Certificate.objects.create(
            owner=self.other_user,
            title="Other User Certificate",
            issuer="OneSmarter Inc.",
            certificate_number="DASH-TEST-003",
            recipient_name="Other User",
            issue_date=date(2026, 10, 11),
            status=Certificate.Status.REJECTED,
        )

    def test_dashboard_requires_authentication(self):
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, 401)

    def test_user_sees_only_own_statistics(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], "USER")
        self.assertEqual(response.data["statistics"]["total"], 2)
        self.assertEqual(response.data["statistics"]["verified"], 1)
        self.assertEqual(response.data["statistics"]["pending"], 1)
        self.assertEqual(response.data["statistics"]["rejected"], 0)

        numbers = [
            item["certificate_number"]
            for item in response.data["recent_certificates"]
        ]
        self.assertNotIn("DASH-TEST-003", numbers)

    def test_admin_sees_project_wide_statistics(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], "ADMIN")
        self.assertEqual(response.data["statistics"]["total"], 3)
        self.assertEqual(response.data["statistics"]["verified"], 1)
        self.assertEqual(response.data["statistics"]["pending"], 1)
        self.assertEqual(response.data["statistics"]["rejected"], 1)
