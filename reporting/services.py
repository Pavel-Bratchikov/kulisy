from collections import Counter
from decimal import Decimal
from django.db.models import Count, Sum, Q
from django.utils import timezone
from scanning.models import CheckIn, ScanAttempt
from budget.models import Expense

def summary(event):
    registered = event.tickets.filter(status="active").count()
    arrived = CheckIn.objects.filter(ticket__event=event).count()
    items = list(event.budget_items.annotate(actual=Sum("expenses__amount", default=Decimal("0"))))
    for item in items:
        item.remaining = item.planned - item.actual
    planned = sum((i.planned for i in items), Decimal("0"))
    spent = sum((i.actual for i in items), Decimal("0"))
    categories = list(event.categories.annotate(registered=Count("tickets", filter=Q(tickets__status="active")), arrived=Count("tickets__checkin")))
    registrations = Counter(timezone.localtime(t).strftime("%d.%m.%Y") for t in event.tickets.filter(status="active").order_by("created_at").values_list("created_at", flat=True))
    arrivals = Counter()
    for t in CheckIn.objects.filter(ticket__event=event).order_by("scanned_at").values_list("scanned_at", flat=True):
        local = timezone.localtime(t)
        arrivals[local.replace(minute=local.minute//15*15, second=0, microsecond=0).strftime("%d.%m %H:%M")] += 1
    return {"registered": registered, "arrived": arrived, "attendance": round(arrived / registered * 100) if registered else 0, "planned": planned, "spent": spent, "remaining": planned-spent, "cost_per_guest": spent / arrived if arrived else None, "items": items, "categories": categories, "duplicates": ScanAttempt.objects.filter(event=event, result="duplicate").count(), "charts": {"registrations": {"labels": list(registrations), "values": list(registrations.values())}, "arrivals": {"labels": list(arrivals), "values": list(arrivals.values())}}}
