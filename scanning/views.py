import json
import uuid
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST, require_GET
from events.access import event_access, audit
from tickets.models import Ticket
from .models import CheckIn, ScanAttempt

@event_access("organizer", "controller")
def scanner(request, event):
    response = render(request, "scanning/scanner.html", {"event": event, "role": request.event_role})
    response["X-Scanner-User"] = str(request.user.pk)
    response["X-Scanner-Cached-At"] = timezone.now().isoformat()
    return response

@event_access("organizer", "controller")
@require_GET
def snapshot(request, event):
    audit(request, event, "scanner.snapshot")
    data = [{"id": str(t.pk), "name": t.full_name, "category": t.category.name, "status": t.status, "checked": hasattr(t, "checkin")} for t in event.tickets.select_related("category", "checkin")]
    return JsonResponse({"tickets": data, "generated_at": timezone.now().isoformat(), "event_status": event.status})

@event_access("organizer", "controller")
@require_POST
def sync(request, event):
    try:
        payload = json.loads(request.body)
        rows = payload["attempts"]
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError()
        cleaned = []
        for row in rows:
            when = parse_datetime(row["scanned_at"])
            if when is None or timezone.is_naive(when) or when > timezone.now()+timedelta(minutes=5) or when < timezone.now()-timedelta(days=7):
                raise ValueError()
            if row["source"] not in {"scan", "search"}:
                raise ValueError()
            cleaned.append((uuid.UUID(row["id"]), uuid.UUID(row["ticket_id"]), uuid.UUID(row["device_id"]), when, row["source"]))
    except (ValueError, TypeError, KeyError, AttributeError):
        return JsonResponse({"error": "Некорректная очередь. Допустимы отметки за последние 7 дней."}, status=400)
    results = []
    for attempt_id, ticket_id, device_id, when, source in cleaned:
        with transaction.atomic():
            ticket = Ticket.objects.select_for_update().filter(pk=ticket_id, event=event).first()
            if not ticket:
                results.append({"id": str(attempt_id), "result": "invalid"})
                continue
            previous = ScanAttempt.objects.filter(pk=attempt_id).first()
            if previous:
                result = previous.result if previous.ticket_id == ticket_id and previous.controller_id == request.user.pk else "invalid"
            else:
                if ticket.status != "active" or event.status == "archived":
                    result = "cancelled"
                elif CheckIn.objects.filter(ticket=ticket).exists():
                    result = "duplicate"
                else:
                    CheckIn.objects.create(ticket=ticket, controller=request.user, scanned_at=when, source=source, device_id=device_id)
                    result = "accepted"
                ScanAttempt.objects.create(id=attempt_id, event=event, ticket=ticket, controller=request.user, scanned_at=when, device_id=device_id, result=result)
            results.append({"id": str(attempt_id), "result": result})
    audit(request, event, "scanner.sync", len(results))
    return JsonResponse({"results": results})

def service_worker(request):
    response = HttpResponse((settings.BASE_DIR / "static/js/sw.js").read_text(), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    return response
