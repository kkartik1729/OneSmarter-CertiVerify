from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.certificates.models import Certificate

User = get_user_model()


class CertificateModelTests(TestCase):
    """Test certificate model behavior."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="certificate_user",
            password="TestPass123!",
        )

    def create_certificate(self, **overrides):
        data = {
            "owner": self.user,
            "title": "Python Programming",
            "issuer": "OneSmarter Inc.",
            "certificate_number": "CERT-TEST-001",
            "recipient_name": "Test Recipient",
            "issue_date": date(2026, 10, 9),
        }
        data.update(overrides)
        return Certificate.objects.create(**data)

    def test_certificate_number_is_normalized(self):
        certificate = self.create_certificate(
            certificate_number=" cert-test-abc "
        )
        self.assertEqual(
            certificate.certificate_number,
            "CERT-TEST-ABC",
        )

    def test_certificate_defaults_to_pending(self):
        certificate = self.create_certificate()
        self.assertEqual(
            certificate.status,
            Certificate.Status.PENDING,
        )

    def test_certificate_file_is_optional(self):
        certificate = self.create_certificate()
        self.assertFalse(certificate.file)


class CertificateAPITests(TestCase):
    """Test certificate API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="certificate_api_user",
            password="TestPass123!",
        )
        self.other_user = User.objects.create_user(
            username="other_certificate_user",
            password="TestPass123!",
        )
        self.client = APIClient()

        self.certificate = Certificate.objects.create(
            owner=self.user,
            title="Python Programming",
            issuer="OneSmarter Inc.",
            certificate_number="CERT-API-001",
            recipient_name="Test Recipient",
            issue_date=date(2026, 10, 9),
            status=Certificate.Status.VERIFIED,
        )

    def test_existing_certificate_is_verified(self):
        response = self.client.get(
            "/api/certificates/verify/CERT-API-001/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["found"])
        self.assertEqual(
            response.data["verification_result"],
            "VERIFIED",
        )
        self.assertEqual(
            response.data["message"],
            "This certificate number matches a record issued by OneSmarter-CertiVerify. The presence of this record confirms the certificate was issued through this system.",
        )

    def test_verification_is_case_insensitive(self):
        response = self.client.get(
            "/api/certificates/verify/cert-api-001/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["found"])
        self.assertEqual(
            response.data["verification_result"],
            "VERIFIED",
        )

    def test_pending_certificate_is_verified_if_found(self):
        self.certificate.status = Certificate.Status.PENDING
        self.certificate.save()

        response = self.client.get(
            "/api/certificates/verify/CERT-API-001/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["found"])
        self.assertEqual(
            response.data["verification_result"],
            "VERIFIED",
        )

    def test_rejected_certificate_is_verified_if_found(self):
        self.certificate.status = Certificate.Status.REJECTED
        self.certificate.rejection_reason = "Invalid certificate"
        self.certificate.save()

        response = self.client.get(
            "/api/certificates/verify/CERT-API-001/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["found"])
        self.assertEqual(
            response.data["verification_result"],
            "VERIFIED",
        )

    def test_unknown_certificate_returns_not_verified(self):
        response = self.client.get(
            "/api/certificates/verify/UNKNOWN-CERT/"
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data["found"])
        self.assertEqual(
            response.data["verification_result"],
            "NOT_VERIFIED",
        )

    def test_verification_is_public_without_authentication(self):
        response = self.client.get(
            "/api/certificates/verify/CERT-API-001/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["found"])

    def test_certificate_list_requires_authentication(self):
        response = self.client.get("/api/certificates/")

        self.assertEqual(response.status_code, 401)

    def test_user_sees_only_own_certificates(self):
        Certificate.objects.create(
            owner=self.other_user,
            title="Java Programming",
            issuer="Another Issuer",
            certificate_number="CERT-OTHER-001",
            recipient_name="Other Recipient",
            issue_date=date(2026, 10, 9),
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/certificates/")

        self.assertEqual(response.status_code, 200)

        if isinstance(response.data, dict):
            results = response.data.get("results", [])
        else:
            results = response.data

        certificate_numbers = [
            item["certificate_number"] for item in results
        ]

        self.assertIn("CERT-API-001", certificate_numbers)
        self.assertNotIn("CERT-OTHER-001", certificate_numbers)

    def test_user_can_create_certificate_without_file(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/certificates/",
            {
                "title": "Django Development",
                "issuer": "OneSmarter Inc.",
                "certificate_number": "cert-new-001",
                "recipient_name": "Test Recipient",
                "issue_date": "2026-10-10",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["certificate_number"],
            "CERT-NEW-001",
        )
        self.assertEqual(
            response.data["status"],
            Certificate.Status.PENDING,
        )
        self.assertTrue(
            Certificate.objects.filter(
                owner=self.user,
                certificate_number="CERT-NEW-001",
            ).exists()
        )

    def test_admin_can_retrieve_user_selection_list(self):
        admin_user = User.objects.create_superuser(
            username="admin_selector_user",
            password="TestPass123!",
            email="admin_selector@example.com",
        )
        self.client.force_authenticate(user=admin_user)
        response = self.client.get("/api/accounts/admin/users/")

        self.assertEqual(response.status_code, 200)
        data = response.data if isinstance(response.data, list) else response.data.get("results", [])
        usernames = [u["username"] for u in data]
        self.assertIn(self.user.username, usernames)
        # Ensure no sensitive fields are present
        for u in data:
            self.assertNotIn("password", u)
            self.assertNotIn("mfa_secret", u)
            self.assertNotIn("totp_secret", u)

    def test_normal_user_cannot_retrieve_user_selection_list(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/accounts/admin/users/")
        self.assertEqual(response.status_code, 403)

    def test_admin_creates_certificate_assigned_to_selected_user(self):
        admin_user = User.objects.create_superuser(
            username="admin_creator_user",
            password="TestPass123!",
            email="admin_creator@example.com",
        )
        self.client.force_authenticate(user=admin_user)

        response = self.client.post(
            "/api/certificates/",
            {
                "title": "Cloud Architecture",
                "issuer": "OneSmarter Inc.",
                "certificate_number": "CERT-OWNER-001",
                "recipient_name": "Kartik Hande",
                "issue_date": "2026-10-12",
                "owner_id": self.user.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["certificate_number"], "CERT-OWNER-001")
        self.assertEqual(response.data["owner_username"], self.user.username)

        # Verify PostgreSQL database owner
        cert = Certificate.objects.get(certificate_number="CERT-OWNER-001")
        self.assertEqual(cert.owner_id, self.user.id)
        self.assertEqual(cert.owner.username, self.user.username)

    def test_admin_creation_requires_valid_owner(self):
        admin_user = User.objects.create_superuser(
            username="admin_req_owner_user",
            password="TestPass123!",
            email="admin_req@example.com",
        )
        self.client.force_authenticate(user=admin_user)

        # Creating without owner_id
        response = self.client.post(
            "/api/certificates/",
            {
                "title": "Cloud Architecture",
                "issuer": "OneSmarter Inc.",
                "certificate_number": "CERT-NO-OWNER-001",
                "recipient_name": "Kartik Hande",
                "issue_date": "2026-10-12",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("owner_id", response.data)

    def test_normal_user_cannot_assign_certificate_to_another_account(self):
        self.client.force_authenticate(user=self.user)

        # Normal user attempts to pass another user's ID as owner
        response = self.client.post(
            "/api/certificates/",
            {
                "title": "Security Specialist",
                "issuer": "OneSmarter Inc.",
                "certificate_number": "CERT-SPOOF-001",
                "recipient_name": "Spoofed Recipient",
                "issue_date": "2026-10-12",
                "owner_id": self.other_user.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("owner", response.data)

    def test_assigned_user_sees_certificate_in_my_certificates(self):
        # Create certificate owned by self.user
        Certificate.objects.create(
            owner=self.user,
            title="Assigned Certificate",
            issuer="OneSmarter Inc.",
            certificate_number="CERT-ASSIGNED-001",
            recipient_name="Assigned User",
            issue_date=date(2026, 10, 12),
        )

        # Authenticate as self.user
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/certificates/")
        self.assertEqual(response.status_code, 200)

        data = response.data if isinstance(response.data, list) else response.data.get("results", [])
        cert_nums = [c["certificate_number"] for c in data]
        self.assertIn("CERT-ASSIGNED-001", cert_nums)

        # Authenticate as other_user -> must NOT see it
        self.client.force_authenticate(user=self.other_user)
        response2 = self.client.get("/api/certificates/")
        self.assertEqual(response2.status_code, 200)
        data2 = response2.data if isinstance(response2.data, list) else response2.data.get("results", [])
        cert_nums2 = [c["certificate_number"] for c in data2]
        self.assertNotIn("CERT-ASSIGNED-001", cert_nums2)

    def test_other_user_cannot_access_private_certificate_detail(self):
        # Certificate belongs to self.user
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(f"/api/certificates/{self.certificate.id}/")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_reassign_certificate_owner(self):
        admin_user = User.objects.create_superuser(
            username="admin_reassigner",
            password="TestPass123!",
            email="reassign@example.com",
        )
        self.client.force_authenticate(user=admin_user)

        response = self.client.patch(
            f"/api/certificates/{self.certificate.id}/",
            {"owner_id": self.other_user.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        self.certificate.refresh_from_db()
        self.assertEqual(self.certificate.owner_id, self.other_user.id)

    def test_normal_user_cannot_reassign_certificate_owner(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/api/certificates/{self.certificate.id}/",
            {"owner_id": self.other_user.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class CertificateGenerationTests(TestCase):
    """Test the complete certificate generation and distribution suite."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_gen",
            password="TestPassword123!",
            email="admin_gen@onesmarter.com",
        )
        if hasattr(self.admin, "profile"):
            self.admin.profile.role = "ADMIN"
            self.admin.profile.save()

        self.student = User.objects.create_user(
            username="student_kartik",
            password="TestPassword123!",
            email="kartik@example.com",
            first_name="Kartik",
            last_name="Hande",
        )
        self.other_student = User.objects.create_user(
            username="other_student",
            password="TestPassword123!",
            email="other@example.com",
        )

        # Create dummy template image
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.certificates.models import CertificateTemplate, Course

        img = Image.new("RGB", (1000, 750), color=(250, 248, 240))
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        uploaded = SimpleUploadedFile("template.png", buf.read(), content_type="image/png")

        self.template = CertificateTemplate.objects.create(
            name="OneSmarter Official Template",
            image=uploaded,
            uploaded_by=self.admin,
        )

        self.course = Course.objects.create(
            name="Full Stack Python",
            title="Certificate of Completion",
            issuer="OneSmarter, Inc.",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 10, 1),
            created_by=self.admin,
        )

    def test_csv_template_download(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/certificates/generate/csv-template/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/csv")
        content = res.content.decode("utf-8")
        self.assertIn("student_name,student_email", content)
        self.assertNotIn("course_name", content)

    def test_validate_simplified_two_column_csv(self):
        self.client.force_authenticate(user=self.admin)
        csv_content = (
            "student_name,student_email\n"
            "Kartik Hande,kartik@example.com\n"
        )
        from django.core.files.uploadedfile import SimpleUploadedFile
        csv_file = SimpleUploadedFile("two_column.csv", csv_content.encode("utf-8"), content_type="text/csv")

        res = self.client.post("/api/certificates/generate/validate-csv/", {
            "file": csv_file,
            "course_id": self.course.id,
            "batch_course_name": "Overridden Batch Course",
            "batch_start_date": "2026-07-01",
            "batch_end_date": "2026-10-01",
            "batch_issue_date": "2026-10-14",
        }, format="multipart")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["total_rows"], 1)
        self.assertEqual(res.data["valid_rows_count"], 1)
        row = res.data["rows"][0]
        self.assertTrue(row["is_valid"])
        self.assertEqual(row["student_name"], "Kartik Hande")
        self.assertEqual(row["course_name"], "Overridden Batch Course")
        self.assertEqual(row["start_date"], "01/07/2026")


    def test_course_validation(self):
        self.client.force_authenticate(user=self.admin)
        # Invalid date: end_date < start_date
        res = self.client.post("/api/certificates/courses/", {
            "name": "Invalid Course",
            "title": "Cert",
            "issuer": "Issuer",
            "start_date": "2026-10-01",
            "end_date": "2026-09-01",
        }, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("end_date", res.data)

    def test_validate_csv_with_registered_and_unregistered_users(self):
        self.client.force_authenticate(user=self.admin)
        csv_content = (
            "student_name,student_email,course_name,start_date,end_date,issue_date\n"
            "Kartik Hande,kartik@example.com,Full Stack Python,2026-07-01,2026-10-01,2026-10-13\n"
            "Unknown Student,unknown@example.com,Full Stack Python,2026-07-01,2026-10-01,2026-10-13\n"
        )
        from django.core.files.uploadedfile import SimpleUploadedFile
        csv_file = SimpleUploadedFile("roster.csv", csv_content.encode("utf-8"), content_type="text/csv")

        res = self.client.post("/api/certificates/generate/validate-csv/", {
            "file": csv_file,
            "course_id": self.course.id,
        }, format="multipart")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["total_rows"], 2)
        self.assertEqual(res.data["valid_rows_count"], 2)
        self.assertEqual(res.data["invalid_rows_count"], 0)
        self.assertTrue(res.data["is_valid"])

        rows = res.data["rows"]
        self.assertTrue(rows[0]["is_valid"])
        self.assertEqual(rows[0]["user_id"], self.student.id)
        self.assertTrue(rows[0]["has_account"])

        self.assertTrue(rows[1]["is_valid"])
        self.assertIsNone(rows[1]["user_id"])
        self.assertFalse(rows[1]["has_account"])

    def test_single_certificate_generation_and_verification(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.post("/api/certificates/generate/single/", {
            "course_id": self.course.id,
            "template_id": self.template.id,
            "user_id": self.student.id,
            "student_name": "Kartik Hande",
            "start_date": "2026-07-01",
            "end_date": "2026-10-01",
            "issue_date": "2026-10-13",
        }, format="json")

        self.assertEqual(res.status_code, 201)
        cert_num = res.data["certificate_number"]
        self.assertTrue(cert_num.startswith("OSCV-"))

        # Verify database record
        cert = Certificate.objects.get(certificate_number=cert_num)
        self.assertEqual(cert.owner, self.student)
        self.assertEqual(cert.recipient_name, "Kartik Hande")
        self.assertTrue(cert.file)
        self.assertTrue(cert.file_sha256)

        # Verify in-app notification created
        from apps.notifications.models import Notification
        notif = Notification.objects.filter(recipient=self.student, certificate=cert).first()
        self.assertIsNotNone(notif)

        # Public verification works
        verify_client = APIClient()
        verify_res = verify_client.get(f"/api/certificates/verify/{cert_num}/")
        self.assertEqual(verify_res.status_code, 200)
        self.assertEqual(verify_res.data["verification_result"], "VERIFIED")

        # Owner can view image
        self.client.force_authenticate(user=self.student)
        # Verify PDF document is stored and can be downloaded by owner
        self.assertTrue(cert.has_pdf)
        pdf_res = self.client.get(f"/api/certificates/{cert.id}/pdf/download/")
        self.assertEqual(pdf_res.status_code, 200)
        self.assertIn("application/pdf", pdf_res["Content-Type"])

        # Another student cannot view image
        self.client.force_authenticate(user=self.other_student)
        forbidden_res = self.client.get(f"/api/certificates/{cert.id}/image/")
        self.assertEqual(forbidden_res.status_code, 403)

    def test_template_deletion_protection(self):
        from apps.certificates.models import GenerationBatch
        self.client.force_authenticate(user=self.admin)
        # Template in use by batch cannot be deleted
        GenerationBatch.objects.create(
            course=self.course,
            template=self.template,
            created_by=self.admin,
        )
        del_res = self.client.delete(f"/api/certificates/templates/{self.template.id}/")
        self.assertEqual(del_res.status_code, 400)
        self.assertIn("Cannot delete template", str(del_res.data))

        # Unused template can be safely deleted
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.certificates.models import CertificateTemplate
        unused_img = SimpleUploadedFile("unused.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 50, content_type="image/png")
        unused_tpl = CertificateTemplate.objects.create(name="Unused Template", image=unused_img)
        del_res2 = self.client.delete(f"/api/certificates/templates/{unused_tpl.id}/")
        self.assertEqual(del_res2.status_code, 204)
        self.assertFalse(CertificateTemplate.objects.filter(id=unused_tpl.id).exists())

    def test_bulk_generation_and_duplicate_skipping(self):
        self.client.force_authenticate(user=self.admin)
        rows = [
            {
                "row_number": 2,
                "student_name": "Kartik Hande",
                "student_email": "kartik@example.com",
                "course_name": self.course.name,
                "start_date": "2026-07-01",
                "end_date": "2026-10-01",
                "issue_date": "2026-10-13",
            }
        ]

        # First run: creates certificate
        res1 = self.client.post("/api/certificates/generate/bulk/", {
            "course_id": self.course.id,
            "template_id": self.template.id,
            "rows": rows,
        }, format="json")
        self.assertEqual(res1.status_code, 201)
        self.assertEqual(res1.data["successful"], 1)
        self.assertEqual(res1.data["skipped_duplicates"], 0)

        # Second run: duplicate certificate skipped
        res2 = self.client.post("/api/certificates/generate/bulk/", {
            "course_id": self.course.id,
            "template_id": self.template.id,
            "rows": rows,
        }, format="json")
        self.assertEqual(res2.status_code, 201)
        self.assertEqual(res2.data["successful"], 0)
        self.assertEqual(res2.data["skipped_duplicates"], 1)

    def test_retry_email_endpoint(self):
        self.client.force_authenticate(user=self.admin)
        cert = Certificate.objects.create(
            owner=self.student,
            title="Cert",
            issuer="OneSmarter, Inc.",
            certificate_number="OSCV-RETRY-001",
            recipient_name="Kartik Hande",
            issue_date=date(2026, 10, 13),
            course=self.course,
            email_sent=False,
            email_error="SMTP server temporarily unreachable",
        )

        res = self.client.post(f"/api/certificates/{cert.id}/retry-email/")
        self.assertEqual(res.status_code, 200)
        cert.refresh_from_db()
        # Either succeeded or recorded safe error, never crashes
        self.assertIn("success", res.data)

    def test_dd_mm_yyyy_date_parsing_and_name_validation(self):
        """Test strict DD/MM/YYYY dates and 1-29 char student name constraints."""
        from apps.certificates.views import parse_date_flexible, validate_student_name

        # 1. 24/07/2026 -> 24 July 2026
        d1, err1 = parse_date_flexible("24/07/2026")
        self.assertIsNone(err1)
        self.assertEqual(d1, date(2026, 7, 24))

        # 2. 24/08/2026 -> 24 August 2026
        d2, err2 = parse_date_flexible("24/08/2026")
        self.assertIsNone(err2)
        self.assertEqual(d2, date(2026, 8, 24))

        # 3. 13/10/2026 -> 13 October 2026
        d3, err3 = parse_date_flexible("13/10/2026")
        self.assertIsNone(err3)
        self.assertEqual(d3, date(2026, 10, 13))

        # 4. Strict Day/Month order (04/05/2026 -> 4 May 2026, NOT April 5)
        d4, err4 = parse_date_flexible("04/05/2026")
        self.assertIsNone(err4)
        self.assertEqual(d4.day, 4)
        self.assertEqual(d4.month, 5)

        # 5. Invalid date
        d_inv, err_inv = parse_date_flexible("31/02/2026")
        self.assertIsNone(d_inv)
        self.assertIn("invalid", err_inv.lower())

        # 6. Student name length: 1–29 chars accepted
        valid_name, n_err = validate_student_name("  Kartik Hande  ")
        self.assertIsNone(n_err)
        self.assertEqual(valid_name, "Kartik Hande")
        self.assertEqual(len(valid_name), 12)

        # 7. Student name length: 30+ chars rejected
        long_name = "Alexander Bartholomew Christopher"  # 33 chars
        inv_name, long_err = validate_student_name(long_name)
        self.assertIsNone(inv_name)
        self.assertIn("1–29 characters", long_err)

        # 8. Empty student name rejected
        empty_name, empty_err = validate_student_name("   ")
        self.assertIsNone(empty_name)
        self.assertIn("required", empty_err.lower())

    def test_csv_validation_with_dd_mm_yyyy_format(self):
        """Test that CSV with DD/MM/YYYY dates validates correctly."""
        self.client.force_authenticate(user=self.admin)
        from django.core.files.uploadedfile import SimpleUploadedFile

        csv_content = (
            "student_name,student_email,course_name,start_date,end_date,issue_date\n"
            "Kartik Hande,kartik@example.com,Full Stack Python,24/07/2026,24/08/2026,13/10/2026\n"
        )
        csv_file = SimpleUploadedFile("dd_mm_yyyy.csv", csv_content.encode("utf-8"), content_type="text/csv")
        res = self.client.post("/api/certificates/generate/validate-csv/", {
            "file": csv_file,
            "course_id": self.course.id,
        }, format="multipart")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["valid_rows_count"], 1)
        self.assertEqual(res.data["invalid_rows_count"], 0)
        row = res.data["rows"][0]
        self.assertTrue(row["is_valid"])
        self.assertEqual(row["start_date"], "24/07/2026")
        self.assertEqual(row["end_date"], "24/08/2026")
        self.assertEqual(row["issue_date"], "13/10/2026")

    def test_manual_generation_rejects_names_with_30_plus_chars(self):
        """Test that manual generation rejects student names of 30 or more characters."""
        self.client.force_authenticate(user=self.admin)
        res = self.client.post("/api/certificates/generate/single/", {
            "course_id": self.course.id,
            "template_id": self.template.id,
            "user_id": self.student.id,
            "student_name": "This is a name with thirty or more chars",
            "start_date": "24/07/2026",
            "end_date": "24/08/2026",
            "issue_date": "13/10/2026",
        }, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn("1–29 characters", res.data.get("detail", ""))

    def test_image_access_with_token_query_parameter(self):
        """Test that certificate image can be accessed using ?token= query parameter."""
        # Generate certificate for student
        self.client.force_authenticate(user=self.admin)
        res = self.client.post("/api/certificates/generate/single/", {
            "course_id": self.course.id,
            "template_id": self.template.id,
            "user_id": self.student.id,
            "student_name": "Kartik Hande",
            "start_date": "24/07/2026",
            "end_date": "24/08/2026",
            "issue_date": "13/10/2026",
        }, format="json")
        self.assertEqual(res.status_code, 201)
        cert_id = res.data["id"]
        cert_num = res.data["certificate_number"]

        # Generate JWT access token for student
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(self.student).access_token)

        # Unauthenticated client requesting with ?token= query parameter
        unauth_client = APIClient()
        img_res = unauth_client.get(f"/api/certificates/{cert_id}/image/?token={token}")
        self.assertEqual(img_res.status_code, 200)
        self.assertIn("image/png", img_res["Content-Type"])

        # Download flag sets Content-Disposition
        dl_res = unauth_client.get(f"/api/certificates/{cert_id}/image/?token={token}&download=true")
        self.assertEqual(dl_res.status_code, 200)
        self.assertIn("attachment", dl_res["Content-Disposition"])
        self.assertIn(cert_num, dl_res["Content-Disposition"])

    def test_date_validation_scenarios(self):
        """Test end_date < start_date rejected, == accepted, > accepted."""
        from django.core.exceptions import ValidationError
        # 1. Earlier end date rejected
        cert_invalid = Certificate(
            recipient_name="Student One",
            recipient_email="student1@example.com",
            title="Course Title",
            issuer="OneSmarter",
            certificate_number="OSCV-DATE-001",
            issue_date="2026-10-14",
            start_date="2026-08-01",
            end_date="2026-07-01",
        )
        with self.assertRaises(ValidationError) as ctx:
            cert_invalid.clean()
        self.assertIn("End date cannot be earlier than start date.", str(ctx.exception))

        # 2. Equal end date accepted
        cert_equal = Certificate(
            recipient_name="Student Two",
            recipient_email="student2@example.com",
            title="Course Title",
            issuer="OneSmarter",
            certificate_number="OSCV-DATE-002",
            issue_date="2026-10-14",
            start_date="2026-08-01",
            end_date="2026-08-01",
        )
        cert_equal.clean()  # should not raise

        # 3. Later end date accepted
        cert_later = Certificate(
            recipient_name="Student Three",
            recipient_email="student3@example.com",
            title="Course Title",
            issuer="OneSmarter",
            certificate_number="OSCV-DATE-003",
            issue_date="2026-10-14",
            start_date="2026-08-01",
            end_date="2026-09-01",
        )
        cert_later.clean()  # should not raise

    def test_single_certificate_to_unregistered_email(self):
        """Admin can issue certificate directly to an unregistered email address."""
        from django.core import mail
        mail.outbox = []
        self.client.force_authenticate(user=self.admin)
        unreg_email = "unregistered.student@example.com"
        res = self.client.post("/api/certificates/generate/single/", {
            "course_id": self.course.id,
            "template_id": self.template.id,
            "student_email": unreg_email,
            "student_name": "Unregistered Student",
            "start_date": "2026-07-01",
            "end_date": "2026-10-01",
            "issue_date": "2026-10-14",
        }, format="json")
        self.assertEqual(res.status_code, 201)
        cert_number = res.data["certificate_number"]
        
        # Verify in DB
        cert = Certificate.objects.get(certificate_number=cert_number)
        self.assertIsNone(cert.owner)
        self.assertEqual(cert.recipient_email, unreg_email)
        self.assertFalse(cert.is_claimed)
        self.assertTrue(cert.email_sent)
        
        # Verify PDF attachment in sent email
        self.assertTrue(len(mail.outbox) >= 1)
        sent_email = mail.outbox[-1]
        self.assertIn(unreg_email, sent_email.to)
        self.assertTrue(any(att[0].endswith(".pdf") for att in sent_email.attachments))

        # Verify public verification without login
        self.client.logout()
        verify_res = self.client.get(f"/api/certificates/verify/{cert_number}/")
        self.assertEqual(verify_res.status_code, 200)
        self.assertEqual(verify_res.data["certificate_number"], cert_number)
        self.assertEqual(verify_res.data["verification_result"], "VERIFIED")
        self.assertTrue(verify_res.data["found"])

    def test_unregistered_recipient_account_claiming_lifecycle(self):
        """Lifecycle: Unregistered cert issued -> user registers -> email verified -> auto-claimed."""
        from apps.certificates.services import claim_unclaimed_certificates_for_user
        from apps.notifications.models import Notification
        from apps.audit.models import AuditLog

        # 1. Issue cert to unregistered email
        unreg_email = "lifecycle.student@example.com"
        cert = Certificate.objects.create(
            owner=None,
            recipient_email=unreg_email,
            recipient_name="Lifecycle Student",
            title="Course of Excellence",
            course_name="Full Stack Python",
            issuer="OneSmarter, Inc.",
            certificate_number="OSCV-2026-LIFE001",
            issue_date="2026-10-14",
            start_date="2026-07-01",
            end_date="2026-10-01",
        )
        self.assertFalse(cert.is_claimed)

        # 2. Student registers with the same email
        reg_res = self.client.post("/api/accounts/register/", {
            "username": "lifecyclestudent",
            "email": unreg_email,
            "password": "StrongPassword@123",
            "password_confirm": "StrongPassword@123",
        }, format="json")
        self.assertEqual(reg_res.status_code, 201)

        user = get_user_model().objects.get(username="lifecyclestudent")
        self.assertFalse(user.profile.email_verified)

        # Attempt claiming before email is verified: should NOT claim
        claimed_before = claim_unclaimed_certificates_for_user(user)
        self.assertEqual(len(claimed_before), 0)
        cert.refresh_from_db()
        self.assertIsNone(cert.owner)

        # 3. Verify email directly via profile and service to test claiming logic
        user.profile.email_verified = True
        user.profile.save()

        claimed = claim_unclaimed_certificates_for_user(user)
        self.assertEqual(len(claimed), 1)

        cert.refresh_from_db()
        self.assertEqual(cert.owner, user)
        self.assertTrue(cert.is_claimed)

        # Verify in-app notification created
        notif = Notification.objects.filter(recipient=user, certificate=cert).first()
        self.assertIsNotNone(notif)
        self.assertIn("Certificate Linked", notif.title)

        # Verify audit log recorded
        audit = AuditLog.objects.filter(target_id=cert.id, action=AuditLog.Action.CERTIFICATE_CLAIMED).first()
        self.assertIsNotNone(audit)

        # 4. Different email cannot claim already claimed certificate
        diff_user = get_user_model().objects.create_user(
            username="diffuser",
            email="different@example.com",
            password="StrongPassword@123",
        )
        diff_user.profile.email_verified = True
        diff_user.profile.save()
        claimed_diff = claim_unclaimed_certificates_for_user(diff_user)
        self.assertEqual(len(claimed_diff), 0)
        cert.refresh_from_db()
        self.assertEqual(cert.owner, user)





class PublicCredentialUrlTests(TestCase):
    def test_url_validation_rejects_localhost_and_private_ips(self):
        from apps.certificates.helpers import is_valid_public_https_url
        self.assertFalse(is_valid_public_https_url('http://localhost:5173'))
        self.assertFalse(is_valid_public_https_url('https://localhost:5173'))
        self.assertFalse(is_valid_public_https_url('http://127.0.0.1:8000'))
        self.assertFalse(is_valid_public_https_url('https://127.0.0.1'))
        self.assertFalse(is_valid_public_https_url('https://192.168.1.100'))
        self.assertFalse(is_valid_public_https_url('https://10.0.0.1'))
        self.assertFalse(is_valid_public_https_url('http://onesmarter.com'))
        self.assertFalse(is_valid_public_https_url('https://YOUR-DEPLOYED-DOMAIN'))
        self.assertFalse(is_valid_public_https_url('https://example.com'))

    def test_url_validation_accepts_valid_public_https(self):
        from apps.certificates.helpers import is_valid_public_https_url
        self.assertTrue(is_valid_public_https_url('https://certiverify.onesmarter.com'))
        self.assertTrue(is_valid_public_https_url('https://onesmarter.com/'))

    def test_build_public_credential_url_with_configured_domain(self):
        from apps.certificates.helpers import build_public_credential_url
        with self.settings(PUBLIC_FRONTEND_URL='https://certiverify.onesmarter.com'):
            url, is_public = build_public_credential_url('OSCV-2026-36966FF4')
            self.assertTrue(is_public)
            self.assertEqual(url, 'https://certiverify.onesmarter.com/verify-certificate/OSCV-2026-36966FF4')

    def test_build_public_credential_url_without_configured_domain(self):
        from apps.certificates.helpers import build_public_credential_url
        with self.settings(PUBLIC_FRONTEND_URL='', FRONTEND_URL='http://localhost:5173'):
            url, is_public = build_public_credential_url('OSCV-2026-36966FF4')
            self.assertFalse(is_public)
            self.assertIsNone(url)

    def test_serializer_outputs_credential_url_fields(self):
        from apps.certificates.serializers import CertificateSerializer
        user = get_user_model().objects.create_user(
            username='cred_student',
            email='cred_student@example.com',
            password='StrongPassword@123',
            )
        cert = Certificate.objects.create(
            owner=user,
            title='Full Stack React Development',
            issuer='OneSmarter, Inc.',
            certificate_number='OSCV-2026-TESTURL1',
            recipient_name='Test Student',
            issue_date='2026-10-14',
        )
        with self.settings(PUBLIC_FRONTEND_URL='https://certiverify.onesmarter.com'):
            serializer = CertificateSerializer(cert)
            self.assertTrue(serializer.data['is_credential_url_public'])
            self.assertEqual(
                serializer.data['credential_url'],
                'https://certiverify.onesmarter.com/verify-certificate/OSCV-2026-TESTURL1',
            )


class CertificateAccountLinkingTestSuite(TestCase):
    """
    Comprehensive automated tests covering:
    Test 1 — Anshuman's case (full unregistered issuance -> register -> verify -> claim -> My Certificates -> Dashboard)
    Test 2 — Different email does not claim
    Test 3 — Multiple certificates linked to verified email
    Test 4 — Duplicate processing is idempotent
    Test 5 — Existing owner conflict protection
    Test 6 — Certificate files preserved and accessible after claiming
    Test 7 — Dashboard consistency and verified metrics calculation
    """

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="admin_user",
            email="admin@onesmarter.com",
            password="AdminPassword@123",
            is_staff=True,
            is_superuser=True,
        )

    def test_1_anshumans_case_end_to_end_linking(self):
        """
        Test 1 — Anshuman's case:
        1. Create an unregistered certificate recipient with a valid email.
        2. Generate and save a certificate.
        3. Register a user using the same email.
        4. Verify that email using the existing application flow.
        5. Confirm the existing certificate's owner is updated to that user.
        6. Log in as the user.
        7. Confirm My Certificates returns the certificate.
        8. Confirm the dashboard count and Recent Certificates reflect it.
        """
        import hashlib
        from apps.accounts.models import EmailVerificationToken

        email = "anshumanagrawal87@gmail.com"
        student_name = "Anshuman Agrawal"

        # 1 & 2. Create unregistered certificate record
        cert = Certificate.objects.create(
            owner=None,
            recipient_email=email,
            recipient_name=student_name,
            title="C Programming Masterclass",
            course_name="C Programming",
            issuer="OneSmarter, Inc.",
            certificate_number="OSCV-2026-ANSHUMAN01",
            issue_date="2026-10-14",
            start_date="2026-07-01",
            end_date="2026-10-01",
            status=Certificate.Status.VERIFIED,
        )
        self.assertIsNone(cert.owner)
        self.assertFalse(cert.is_claimed)

        # 3. Register user with the exact same email
        reg_res = self.client.post("/api/accounts/register/", {
            "username": email,
            "email": email,
            "first_name": "Anshuman",
            "last_name": "Agrawal",
            "password": "Password@12345",
            "password_confirm": "Password@12345",
        }, format="json")
        self.assertEqual(reg_res.status_code, 201)

        user = User.objects.get(email=email)
        self.assertFalse(user.profile.email_verified)

        # 4. Verify email using the existing application flow (using verification token / OTP)
        token_record = EmailVerificationToken.objects.filter(user=user, is_used=False).first()
        self.assertIsNotNone(token_record)

        # Generate a known OTP and set on token_record to test OTP verification endpoint
        test_otp = "849201"
        token_record.otp_hash = hashlib.sha256(test_otp.encode("utf-8")).hexdigest()
        token_record.save(update_fields=["otp_hash"])

        verify_res = self.client.post("/api/accounts/verify-email/", {
            "email": email,
            "otp": test_otp,
        }, format="json")
        self.assertEqual(verify_res.status_code, 200)
        self.assertTrue(verify_res.data["email_verified"])
        self.assertEqual(verify_res.data["claimed_count"], 1)
        self.assertIn(cert.certificate_number, verify_res.data["claimed_certificate_numbers"])

        # 5. Confirm certificate's owner is updated to Anshuman
        cert.refresh_from_db()
        self.assertEqual(cert.owner, user)
        self.assertTrue(cert.is_claimed)
        self.assertEqual(cert.status, Certificate.Status.VERIFIED)

        # 6. Log in as Anshuman
        self.client.force_authenticate(user=user)

        # 7. Confirm My Certificates returns the certificate
        certs_res = self.client.get("/api/certificates/")
        self.assertEqual(certs_res.status_code, 200)
        cert_numbers = [c["certificate_number"] for c in certs_res.data]
        self.assertIn("OSCV-2026-ANSHUMAN01", cert_numbers)

        # 8. Confirm the dashboard count and Recent Certificates reflect it
        dash_res = self.client.get("/api/dashboard/")
        self.assertEqual(dash_res.status_code, 200)
        self.assertEqual(dash_res.data["my_certificates"], 1)
        recent_numbers = [c["certificate_number"] for c in dash_res.data["recent_certificates"]]
        self.assertIn("OSCV-2026-ANSHUMAN01", recent_numbers)

    def test_2_different_email_does_not_claim(self):
        """Test 2 — Issue to one email and register with a different email. Cert must not be claimed."""
        cert = Certificate.objects.create(
            owner=None,
            recipient_email="studentA@example.com",
            recipient_name="Student A",
            title="Python Course",
            issuer="OneSmarter, Inc.",
            certificate_number="OSCV-2026-DIFF001",
            issue_date="2026-10-14",
            start_date="2026-07-01",
            end_date="2026-10-01",
        )

        userB = User.objects.create_user(
            username="studentB",
            email="studentB@example.com",
            password="Password@123",
        )
        userB.profile.email_verified = True
        userB.profile.save()

        from apps.certificates.services import claim_unclaimed_certificates_for_user
        claimed = claim_unclaimed_certificates_for_user(userB)
        self.assertEqual(len(claimed), 0)

        cert.refresh_from_db()
        self.assertIsNone(cert.owner)
        self.assertFalse(cert.is_claimed)

    def test_3_multiple_certificates_linked_to_verified_email(self):
        """Test 3 — If multiple eligible certificates exist for the same verified email, link all of them."""
        email = "multicert.student@example.com"
        c1 = Certificate.objects.create(
            owner=None,
            recipient_email=email,
            recipient_name="Multi Student",
            title="Course 1",
            issuer="OneSmarter, Inc.",
            certificate_number="OSCV-2026-MULTI01",
            issue_date="2026-10-14",
            start_date="2026-07-01",
            end_date="2026-08-01",
        )
        c2 = Certificate.objects.create(
            owner=None,
            recipient_email=email,
            recipient_name="Multi Student",
            title="Course 2",
            issuer="OneSmarter, Inc.",
            certificate_number="OSCV-2026-MULTI02",
            issue_date="2026-10-14",
            start_date="2026-08-01",
            end_date="2026-09-01",
        )

        user = User.objects.create_user(
            username="multistudent",
            email=email,
            password="Password@123",
        )
        user.profile.email_verified = True
        user.profile.save()

        from apps.certificates.services import claim_unclaimed_certificates_for_user
        claimed = claim_unclaimed_certificates_for_user(user)
        self.assertEqual(len(claimed), 2)

        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertEqual(c1.owner, user)
        self.assertEqual(c2.owner, user)

        # Check My Certificates endpoint returns both
        self.client.force_authenticate(user=user)
        res = self.client.get("/api/certificates/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)

    def test_4_duplicate_processing_is_idempotent(self):
        """Test 4 — Running the claiming service repeatedly must not duplicate certs or change numbers."""
        email = "idempotent.student@example.com"
        cert = Certificate.objects.create(
            owner=None,
            recipient_email=email,
            recipient_name="Idempotent Student",
            title="Course Python",
            issuer="OneSmarter, Inc.",
            certificate_number="OSCV-2026-IDEMP01",
            issue_date="2026-10-14",
            start_date="2026-07-01",
            end_date="2026-09-01",
        )
        user = User.objects.create_user(
            username="idempstudent",
            email=email,
            password="Password@123",
        )
        user.profile.email_verified = True
        user.profile.save()

        from apps.certificates.services import claim_unclaimed_certificates_for_user

        # Run 1
        run1 = claim_unclaimed_certificates_for_user(user)
        self.assertEqual(len(run1), 1)
        cert.refresh_from_db()
        self.assertEqual(cert.owner, user)
        self.assertEqual(cert.certificate_number, "OSCV-2026-IDEMP01")

        # Run 2
        run2 = claim_unclaimed_certificates_for_user(user)
        self.assertEqual(len(run2), 0)
        cert.refresh_from_db()
        self.assertEqual(cert.owner, user)
        self.assertEqual(cert.certificate_number, "OSCV-2026-IDEMP01")

        # Total count in database has not changed
        total_certs = Certificate.objects.filter(certificate_number="OSCV-2026-IDEMP01").count()
        self.assertEqual(total_certs, 1)

    def test_5_existing_owner_conflict_not_overwritten(self):
        """Test 5 — Do not automatically transfer a certificate already linked to another account."""
        owner1 = User.objects.create_user(
            username="owner1",
            email="shared@example.com",
            password="Password@123",
        )
        cert = Certificate.objects.create(
            owner=owner1,
            recipient_email="shared@example.com",
            recipient_name="Original Recipient",
            title="Protected Course",
            issuer="OneSmarter, Inc.",
            certificate_number="OSCV-2026-PROTECT01",
            issue_date="2026-10-14",
            start_date="2026-07-01",
            end_date="2026-09-01",
        )

        owner2 = User.objects.create_user(
            username="owner2",
            email="shared@example.com",
            password="Password@123",
        )
        owner2.profile.email_verified = True
        owner2.profile.save()

        from apps.certificates.services import claim_unclaimed_certificates_for_user
        claimed = claim_unclaimed_certificates_for_user(owner2)
        self.assertEqual(len(claimed), 0)

        cert.refresh_from_db()
        self.assertEqual(cert.owner, owner1)

    def test_6_certificate_files_accessible_after_claiming(self):
        """Test 6 — After claiming, certificate image, PDF, and details open correctly."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.certificates.models import CertificatePDF

        email = "filetest@example.com"
        dummy_png = SimpleUploadedFile("cert.png", b"fake-png-bytes", content_type="image/png")
        cert = Certificate.objects.create(
            owner=None,
            recipient_email=email,
            recipient_name="File Student",
            title="File Preserved Course",
            issuer="OneSmarter, Inc.",
            certificate_number="OSCV-2026-FILE001",
            issue_date="2026-10-14",
            start_date="2026-07-01",
            end_date="2026-09-01",
            file=dummy_png,
            file_sha256="fakehash123",
        )
        CertificatePDF.store(
            certificate=cert,
            raw_bytes=b"%PDF-1.4 test valid pdf bytes",
            filename="cert.pdf",
        )

        user = User.objects.create_user(
            username="filestudent",
            email=email,
            password="Password@123",
        )
        user.profile.email_verified = True
        user.profile.save()

        from apps.certificates.services import claim_unclaimed_certificates_for_user
        claim_unclaimed_certificates_for_user(user)

        cert.refresh_from_db()
        self.assertEqual(cert.owner, user)
        self.assertTrue(bool(cert.file))
        self.assertEqual(cert.file_sha256, "fakehash123")
        self.assertTrue(cert.has_pdf)

        # Authenticate as user and verify My Certificates returns valid data
        self.client.force_authenticate(user=user)
        res = self.client.get("/api/certificates/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["certificate_number"], "OSCV-2026-FILE001")

    def test_7_dashboard_consistency(self):
        """Test 7 — Verify My Certificates count, Recent Certificates, and metrics are calculated from real DB data."""
        email = "dashboard.student@example.com"
        user = User.objects.create_user(
            username="dashstudent",
            email=email,
            password="Password@123",
        )
        user.profile.email_verified = True
        user.profile.save()

        for i in range(3):
            Certificate.objects.create(
                owner=user,
                recipient_email=email,
                recipient_name="Dash Student",
                title=f"Course {i+1}",
                issuer="OneSmarter, Inc.",
                certificate_number=f"OSCV-2026-DASH00{i+1}",
                issue_date="2026-10-14",
                start_date="2026-07-01",
                end_date="2026-09-01",
                status=Certificate.Status.VERIFIED,
            )

        self.client.force_authenticate(user=user)
        dash_res = self.client.get("/api/dashboard/")
        self.assertEqual(dash_res.status_code, 200)
        self.assertEqual(dash_res.data["my_certificates"], 3)
        self.assertEqual(len(dash_res.data["recent_certificates"]), 3)
        self.assertEqual(dash_res.data["statistics"]["verified"], 3)


