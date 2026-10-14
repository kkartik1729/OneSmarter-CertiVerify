
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.audit.models import AuditLog
from apps.audit.services import log_action


User = get_user_model()


class AuditAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="audit_test_user",
            password="TestPass123!",
        )
        self.admin = User.objects.create_superuser(
            username="audit_test_admin",
            email="audit-admin@example.com",
            password="TestPass123!",
        )

        log_action(
            action=AuditLog.Action.OTHER,
            actor=self.admin,
            target_type="Test",
            target_id="audit-test-001",
            description="Audit API test record",
            metadata={"test": True},
        )

    def test_audit_requires_authentication(self):
        response = self.client.get("/api/audit/")
        self.assertEqual(response.status_code, 401)

    def test_regular_user_cannot_view_audit_logs(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/audit/")

        self.assertEqual(response.status_code, 403)

    def test_admin_can_view_audit_logs(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get("/api/audit/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.data) >= 1)

    def test_admin_can_filter_audit_logs(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            "/api/audit/?action=OTHER"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.data) >= 1)
        for item in response.data:
            self.assertEqual(item["action"], "OTHER")

    def test_log_action_creates_record(self):
        before = AuditLog.objects.count()

        record = log_action(
            action=AuditLog.Action.OTHER,
            actor=self.admin,
            target_type="Test",
            target_id="audit-test-002",
            description="Service function test",
            metadata={"source": "automated_test"},
        )

        self.assertEqual(AuditLog.objects.count(), before + 1)
        self.assertEqual(record.actor, self.admin)
        self.assertEqual(record.target_id, "audit-test-002")
