import io
import os
from unittest.mock import patch
from django.core.management import call_command, CommandError
from django.conf import settings
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings


class HealthTests(TestCase):
    def test_database_available(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_database_failure_returns_unavailable_without_details(self):
        with patch('config.health.connection.cursor', side_effect=OperationalError('private connection details')):
            response = self.client.get('/health/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
        self.assertNotContains(response, 'private', status_code=503)


class DeploymentConfigTests(SimpleTestCase):
    def test_incomplete_config_fails_without_printing_password(self):
        with override_settings(DEBUG=True, EMAIL_HOST='smtp.example.ru', EMAIL_HOST_PASSWORD='private-password'):
            with self.assertRaises(CommandError) as error:
                call_command('check_server_config', stdout=io.StringIO())
        self.assertIn('DEBUG', str(error.exception))
        self.assertNotIn('private-password', str(error.exception))

    def test_valid_config_passes(self):
        with patch.dict(os.environ, {'DOMAIN': 'events.host.test'}, clear=False):
            with patch.dict(settings.DATABASES['default'], {'ENGINE':'django.db.backends.postgresql', 'PASSWORD':'test-only-password-long-enough'}), override_settings(DEBUG=False, ALLOWED_HOSTS=['events.host.test', 'localhost'], CSRF_TRUSTED_ORIGINS=['https://events.host.test'], PUBLIC_BASE_URL='https://events.host.test', EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST='smtp.host.test', EMAIL_HOST_USER='sender@host.test', EMAIL_HOST_PASSWORD='test-password', EMAIL_USE_TLS=True, EMAIL_USE_SSL=False, DEFAULT_FROM_EMAIL='sender@host.test'):
                call_command('check_server_config', stdout=io.StringIO())
