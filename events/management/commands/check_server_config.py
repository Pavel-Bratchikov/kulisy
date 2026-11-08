import os
from urllib.parse import urlsplit
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Fail early on incomplete production configuration; never print secrets.'

    def handle(self, *args, **options):
        errors = []
        domain = os.getenv('DOMAIN', '')
        if settings.DEBUG:
            errors.append('DEBUG должен быть 0.')
        if not domain or domain == 'events.example.ru':
            errors.append('Укажите реальный DOMAIN.')
        if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
            errors.append('Для сервера требуется PostgreSQL (POSTGRES_HOST).')
        password = settings.DATABASES['default'].get('PASSWORD', '')
        if len(password) < 20 or password.startswith('replace-'):
            errors.append('Задайте уникальный POSTGRES_PASSWORD длиной от 20 символов.')
        if domain not in settings.ALLOWED_HOSTS or 'localhost' not in settings.ALLOWED_HOSTS:
            errors.append('ALLOWED_HOSTS должен содержать DOMAIN и localhost для healthcheck.')
        if f'https://{domain}' not in settings.CSRF_TRUSTED_ORIGINS:
            errors.append('Добавьте https://DOMAIN в CSRF_TRUSTED_ORIGINS.')
        if settings.PUBLIC_BASE_URL != f'https://{domain}':
            errors.append('PUBLIC_BASE_URL должен быть https://DOMAIN.')
        if settings.EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend':
            errors.append('На сервере включите SMTP backend для писем с билетами.')
        if settings.EMAIL_HOST in {'localhost', 'smtp.example.ru', ''}:
            errors.append('Заполните EMAIL_HOST реального SMTP-сервера.')
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            errors.append('Заполните EMAIL_HOST_USER и EMAIL_HOST_PASSWORD.')
        if not settings.EMAIL_USE_TLS and not settings.EMAIL_USE_SSL:
            errors.append('Включите EMAIL_USE_TLS=1 (обычно 587) или EMAIL_USE_SSL=1 (обычно 465).')
        if 'localhost' in settings.DEFAULT_FROM_EMAIL or 'example.ru' in settings.DEFAULT_FROM_EMAIL:
            errors.append('Укажите подтверждённый адрес отправителя DEFAULT_FROM_EMAIL.')
        if os.getenv('S3_ENDPOINT_URL') and urlsplit(os.environ['S3_ENDPOINT_URL']).scheme != 'https':
            errors.append('S3_ENDPOINT_URL должен использовать https.')
        if errors:
            raise CommandError('\n'.join(errors))
        self.stdout.write(self.style.SUCCESS('Настройки заполнены. Доступность SMTP, DNS и S3 проверяется отдельно.'))
