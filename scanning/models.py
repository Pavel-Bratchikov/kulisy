import uuid
from django.conf import settings
from django.db import models
from tickets.models import Ticket
from events.models import Event

class CheckIn(models.Model):
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="checkin")
    controller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    scanned_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=10, choices=[("scan", "QR"), ("search", "Поиск")])
    device_id = models.UUIDField()

class ScanAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    controller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    scanned_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=20)
    device_id = models.UUIDField()
