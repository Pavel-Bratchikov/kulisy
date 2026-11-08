import uuid
from decimal import Decimal
from pathlib import Path
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from events.models import Event

def receipt_path(instance, filename):
    return f"receipts/{instance.budget_item.event_id}/{uuid.uuid4()}{Path(filename).suffix.lower()}"

class BudgetItem(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="budget_items")
    name = models.CharField("Статья сметы", max_length=150)
    planned = models.DecimalField("План, ₽", max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(planned__gte=0), name="budget_plan_nonnegative")]
    def __str__(self):
        return self.name

class Expense(models.Model):
    budget_item = models.ForeignKey(BudgetItem, on_delete=models.CASCADE, related_name="expenses")
    amount = models.DecimalField("Сумма, ₽", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    description = models.CharField("Назначение расхода", max_length=250)
    receipt = models.ImageField("Фото чека", upload_to=receipt_path, blank=True)
    date = models.DateField("Дата расхода")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    class Meta:
        ordering = ["-date", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="expense_positive")]
