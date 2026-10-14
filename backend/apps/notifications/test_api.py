
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.notifications.models import Notification


User = get_user_model()


class NotificationAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="notification_test_user",
            password="TestPass123!",
        )
        self.other_user = User.objects.create_user(
            username="notification_other_user",
            password="TestPass123!",
        )

        self.notification = Notification.objects.create(
            recipient=self.user,
            notification_type=Notification.NotificationType.GENERAL,
            title="Test notification",
            message="Notification API test",
        )

        self.other_notification = Notification.objects.create(
            recipient=self.other_user,
            notification_type=Notification.NotificationType.GENERAL,
            title="Private notification",
            message="This belongs to another user",
        )

    def test_notifications_require_authentication(self):
        response = self.client.get("/api/notifications/")
        self.assertEqual(response.status_code, 401)

    def test_user_sees_only_own_notifications(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/notifications/")

        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.data]
        self.assertIn(self.notification.id, ids)
        self.assertNotIn(self.other_notification.id, ids)

    def test_unread_count(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/notifications/unread-count/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 1)

    def test_mark_notification_as_read(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/api/notifications/{self.notification.id}/read/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_read"])

        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_user_cannot_mark_another_users_notification_read(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/api/notifications/{self.other_notification.id}/read/"
        )

        self.assertEqual(response.status_code, 404)

    def test_mark_all_as_read(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/notifications/read-all/"
        )

        self.assertEqual(response.status_code, 200)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

        # The other user's notification must remain unread.
        self.other_notification.refresh_from_db()
        self.assertFalse(self.other_notification.is_read)
