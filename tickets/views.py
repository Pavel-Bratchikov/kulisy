import io
import segno
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from events.models import Event
from events.access import event_access, audit
from .models import Ticket
from .forms import RegistrationForm
from .services import issue_ticket


def register(request, slug):
    event = get_object_or_404(Event, slug=slug, status__in=["published", "closed"])
    form = RegistrationForm(request.POST or None, event=event)
    if request.method == "POST" and form.is_valid():
        try:
            ticket = issue_ticket(event, form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            audit(request, event, "ticket.register", ticket.pk)
            return redirect("ticket", ticket.pk)
    return render(request, "tickets/register.html", {"event": event, "form": form})


def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket.objects.select_related("event", "category"), pk=ticket_id)
    audit(request, ticket.event, "ticket.view", ticket.pk)
    return render(request, "tickets/detail.html", {"ticket": ticket})


def ticket_qr(request, ticket_id):
    ticket = get_object_or_404(Ticket, pk=ticket_id)
    buf = io.BytesIO()
    segno.make(str(ticket.pk), micro=False).save(buf, kind="svg", scale=8, border=4)
    return HttpResponse(buf.getvalue(), content_type="image/svg+xml")

@event_access("organizer")
def guest_list(request, event):
    guests = event.tickets.select_related("category", "checkin")
    query = request.GET.get("q", "").strip()
    if query:
        guests = guests.filter(full_name__icontains=query)
    audit(request, event, "guests.view")
    return render(request, "tickets/guests.html", {"event": event, "role": "organizer", "guests": guests, "q": query})

@event_access("organizer")
def manual_ticket(request, event):
    form = RegistrationForm(request.POST or None, event=event)
    if request.method == "POST" and form.is_valid():
        try:
            ticket = issue_ticket(event, form.cleaned_data, manual=True)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            audit(request, event, "ticket.manual", ticket.pk)
            return redirect("ticket", ticket.pk)
    return render(request, "events/form.html", {"event": event, "role": "organizer", "form": form, "title": "Выдать билет вручную", "note": "Подтверждайте согласие только если получили его от участника."})

@event_access("organizer")
@require_POST
def cancel_ticket(request, event, ticket_id):
    with transaction.atomic():
        ticket = get_object_or_404(Ticket.objects.select_for_update(), event=event, pk=ticket_id)
        if hasattr(ticket, "checkin"):
            messages.error(request, "Нельзя аннулировать билет после прохода.")
        else:
            ticket.status = "cancelled"
            ticket.save(update_fields=["status"])
            audit(request, event, "ticket.cancel", ticket.pk)
    return redirect("guests", event.pk)
