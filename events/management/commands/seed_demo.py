import os
import random
import uuid
from decimal import Decimal
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from events.models import Event, TeamMember
from tickets.models import Ticket
from scanning.models import CheckIn
from budget.models import BudgetItem, Expense

class Command(BaseCommand):
    help = "Create local-only demo event (idempotent). Password is supplied through DEMO_PASSWORD."
    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo data is available only with DEBUG=1")
        password = os.getenv("DEMO_PASSWORD")
        if not password:
            raise CommandError("Set DEMO_PASSWORD")
        users = {}
        for role, name in [("organizer", "Александра"), ("controller", "Михаил"), ("treasurer", "Дарья")]:
            email = f"{role}@kulisy.test"
            user, created = User.objects.get_or_create(username=email, defaults={"email": email, "first_name": name})
            if created:
                user.set_password(password)
                user.save()
            users[role] = user
        event, created = Event.objects.get_or_create(slug="demo-campus", defaults={"title": "Вечер кампуса", "description": "Знакомства, музыка и идеи, которые объединяют. Встречаемся в пространстве кампуса, чтобы провести этот вечер вместе.", "location": "Студенческий центр · Большой зал", "starts_at": timezone.now()+timedelta(days=7), "status": "published", "owner": users["organizer"], "privacy_contact": "organizer@kulisy.test"})
        if not created:
            self.stdout.write("Demo already exists; no data changed.")
            return
        for role, user in users.items():
            TeamMember.objects.create(event=event, user=user, role=role)
        category = event.categories.create(name="Основной билет", limit=80)
        volunteers = event.categories.create(name="Волонтёры", limit=20)
        names = ["Анна Смирнова", "Иван Петров", "Мария Кузнецова", "Дмитрий Соколов", "Елена Новикова", "Артём Морозов", "Ольга Волкова", "Никита Павлов", "Дарья Орлова", "Михаил Попов"]
        now = timezone.now()
        for index in range(30):
            ticket = Ticket.objects.create(event=event, category=volunteers if index>=25 else category, full_name=names[index%10]+(f" {index//10+1}" if index>=10 else ""), email=f"guest{index+1}@example.test", consent_at=now, created_at=now-timedelta(days=6-index//5))
            if index < 18:
                CheckIn.objects.create(ticket=ticket, controller=users["controller"], scanned_at=now-timedelta(minutes=(18-index)*3), source="scan", device_id=uuid.uuid4())
        for name, planned, actual in [("Площадка", "15000", "15000"), ("Оборудование", "8000", "6500"), ("Кофе и угощения", "6000", "7200"), ("Печать и оформление", "3000", "1800")]:
            item = BudgetItem.objects.create(event=event, name=name, planned=Decimal(planned))
            Expense.objects.create(budget_item=item, amount=Decimal(actual), description="Демонстрационный расход", date=now.date(), author=users["treasurer"])
        self.stdout.write(self.style.SUCCESS("Created demo: 30 tickets, 18 check-ins, 4 budget items. Accounts: organizer/controller/treasurer@kulisy.test"))
