from decimal import Decimal
from django import forms
from django.utils import timezone
from .models import BudgetItem, Expense

class BudgetItemForm(forms.ModelForm):
    class Meta:
        model = BudgetItem
        fields = ["name", "planned"]

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["budget_item", "amount", "description", "date", "receipt"]
        labels = {"budget_item": "Статья сметы"}
        widgets = {"date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
    def __init__(self, *args, event, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["budget_item"].queryset = event.budget_items.all()
        self.fields["date"].initial = timezone.localdate()
    def clean_receipt(self):
        receipt = self.cleaned_data.get("receipt")
        if receipt and (receipt.size > 10 * 1024 * 1024 or receipt.image.format not in {"JPEG", "PNG", "WEBP"}):
            raise forms.ValidationError("Загрузите JPG, PNG или WebP размером до 10 МБ.")
        return receipt
