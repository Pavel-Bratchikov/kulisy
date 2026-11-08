from django.http import FileResponse
from django.shortcuts import render, redirect, get_object_or_404
from events.access import event_access, audit
from .forms import BudgetItemForm, ExpenseForm
from .models import Expense
from reporting.services import summary

@event_access("organizer", "treasurer")
def budget(request, event):
    item_form = BudgetItemForm(request.POST if request.POST.get("action") == "item" else None)
    expense_form = ExpenseForm(request.POST if request.POST.get("action") == "expense" else None, request.FILES or None, event=event)
    if request.method == "POST":
        if request.POST.get("action") == "item" and item_form.is_valid():
            item = item_form.save(commit=False)
            item.event = event
            item.save()
            audit(request, event, "budget.item", item.pk)
            return redirect("budget", event.pk)
        if request.POST.get("action") == "expense" and expense_form.is_valid():
            expense = expense_form.save(commit=False)
            expense.author = request.user
            expense.save()
            audit(request, event, "budget.expense", expense.pk)
            return redirect("budget", event.pk)
    return render(request, "budget/index.html", {"event": event, "role": request.event_role, "item_form": item_form, "expense_form": expense_form, "expenses": Expense.objects.filter(budget_item__event=event).select_related("budget_item", "author"), **summary(event)})

@event_access("organizer", "treasurer")
def receipt(request, event, expense_id):
    expense = get_object_or_404(Expense, pk=expense_id, budget_item__event=event)
    if not expense.receipt:
        from django.http import Http404
        raise Http404
    audit(request, event, "receipt.view", expense.pk)
    return FileResponse(expense.receipt.open("rb"), as_attachment=True, filename=expense.receipt.name.split("/")[-1])
