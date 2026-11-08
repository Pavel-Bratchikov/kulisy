import uuid
from django.db import models
from django.utils import timezone
from events.models import Event, TicketCategory

class Ticket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tickets")
    category = models.ForeignKey(TicketCategory, on_delete=models.RESTRICT, related_name="tickets")
    full_name = models.CharField("Фамилия и имя", max_length=200)
    email = models.EmailField("Электронная почта")
    phone = models.CharField("Телефон", max_length=30, blank=True)
    status = models.CharField(max_length=10, choices=[("active", "Действителен"), ("cancelled", "Аннулирован")], default="active")
    manual = models.BooleanField(default=False)
    consent_at = models.DateTimeField()
    consent_version = models.CharField(max_length=32, default="2026-11-v1")
    created_at = models.DateTimeField(default=timezone.now)
    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["event", "email"], condition=models.Q(status="active"), name="one_active_ticket_per_email")]

class MailDelivery(models.Model):
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="delivery")
    sent_at = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=250, blank=True)
    next_attempt_at = models.DateTimeField(default=timezone.now)
