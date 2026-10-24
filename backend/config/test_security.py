import unittest

from config.security import validate_django_secret_key


class DjangoSecretKeyTests(unittest.TestCase):
    def test_missing_and_known_placeholders_are_rejected(self):
        for value in (None, "", "   ", "dev-only-change-this-key-before-deployment", "replace-with-a-secure-django-secret-key"):
            with self.subTest(value="missing or placeholder"):
                with self.assertRaises(ValueError):
                    validate_django_secret_key(value)

    def test_configured_secret_is_preserved(self):
        self.assertEqual(validate_django_secret_key("a-unique-secret-value"), "a-unique-secret-value")


if __name__ == "__main__":
    unittest.main()
