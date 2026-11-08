import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

class Event(models.Model):
    STATUS = [("draft", "Черновик"), ("published", "Регистрация открыта"), ("closed", "Регистрация закрыта"), ("archived", "Архив")]
    title = models.CharField("Название", max_length=200)
    description = models.TextField("Описание", blank=True)
    location = models.CharField("Место проведения", max_length=250)
    starts_at = models.DateTimeField("Дата и время")
    slug = models.SlugField(unique=True, default=uuid.uuid4)
    status = models.CharField("Статус", max_length=12, choices=STATUS, default="draft")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_events")
    capacity = models.PositiveIntegerField(default=100)
    team_limit = models.PositiveIntegerField(default=3)
    collect_phone = models.BooleanField("Запрашивать телефон", default=False)
    privacy_contact = models.EmailField("Почта организатора для обращений")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-starts_at"]
    def __str__(self):
        return self.title

class TeamMember(models.Model):
    ROLES = [("organizer", "Организатор"), ("treasurer", "Казначей"), ("controller", "Контролёр")]
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=12, choices=ROLES)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["event", "user"], name="unique_event_member")]

class Invitation(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=12, choices=TeamMember.ROLES)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False)

class TicketCategory(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField("Название категории", max_length=100)
    limit = models.PositiveIntegerField("Лимит мест", default=100)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(limit__gt=0), name="positive_category_limit")]
    def __str__(self):
        return self.name

class AuditLog(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=80)
    entity = models.CharField(max_length=100, blank=True)
    ip = models.GenericIPAddressField(null=True)
    created_at = models.DateTimeField(default=timezone.now)
