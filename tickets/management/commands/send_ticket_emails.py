import io
import time
from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from django.urls import reverse
import segno
from tickets.models import MailDelivery

class Command(BaseCommand):
    help = "Process persistent SMTP outbox. --loop polls every 10 seconds."
    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
    def handle(self, *args, **options):
        while True:
            ids = list(MailDelivery.objects.filter(sent_at__isnull=True, next_attempt_at__lte=timezone.now(), ticket__status="active").values_list("pk", flat=True)[:100])
            for pk in ids:
                with transaction.atomic():
                    delivery = MailDelivery.objects.select_for_update().select_related("ticket__event").get(pk=pk)
                    if delivery.sent_at or delivery.next_attempt_at > timezone.now():
                        continue
                    ticket = delivery.ticket
                    url = settings.PUBLIC_BASE_URL + reverse("ticket", args=[ticket.pk])
                    message = EmailMessage(f"Ваш билет — {ticket.event.title}", f"Здравствуйте, {ticket.full_name}!\n\nВаш билет: {url}\nМесто: {ticket.event.location}\nДата: {timezone.localtime(ticket.event.starts_at):%d.%m.%Y %H:%M}\n\nQR-код приложен к письму. Сохраните его перед мероприятием.", to=[ticket.email])
                    qr = io.BytesIO()
                    segno.make(str(ticket.pk), micro=False).save(qr, kind="png", scale=8)
                    message.attach("ticket.png", qr.getvalue(), "image/png")
                    delivery.attempts += 1
                    try:
                        message.send(fail_silently=False)
                    except Exception as exc:
                        delivery.last_error = type(exc).__name__
                        delivery.next_attempt_at = timezone.now()+timedelta(seconds=min(3600, 30*2**min(delivery.attempts, 7)))
                    else:
                        delivery.sent_at = timezone.now()
                        delivery.last_error = ""
                    delivery.save()
            if not options["loop"]:
                break
            time.sleep(10)
