from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.utils import timezone
from events.models import Event, TicketCategory
from .models import Ticket, MailDelivery

@transaction.atomic
def issue_ticket(event, data, manual=False):
    # One lock order for all issuance: event, then category. PostgreSQL serializes capacity checks.
    event = Event.objects.select_for_update().get(pk=event.pk)
    if event.status != "published" and not (manual and event.status == "draft"):
        raise ValidationError("Регистрация на мероприятие закрыта.")
    category = TicketCategory.objects.select_for_update().get(pk=data["category"].pk, event=event)
    if Ticket.objects.filter(event=event, status="active").count() >= event.capacity:
        raise ValidationError("Достигнут лимит участников мероприятия.")
    if category.tickets.filter(status="active").count() >= category.limit:
        raise ValidationError("В этой категории больше нет мест.")
    if not data.get("consent"):
        raise ValidationError("Необходимо согласие на обработку данных.")
    try:
        with transaction.atomic():
            ticket = Ticket.objects.create(event=event, category=category, full_name=data["full_name"], email=data["email"].lower(), phone=data.get("phone", "") if event.collect_phone else "", manual=manual, consent_at=timezone.now())
    except IntegrityError:
        raise ValidationError("На эту почту уже оформлен билет на мероприятие.")
    MailDelivery.objects.create(ticket=ticket)
    return ticket
