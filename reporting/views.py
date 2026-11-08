import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from events.access import event_access, audit
from scanning.models import ScanAttempt
from budget.models import Expense
from .services import summary

@event_access("organizer", "treasurer")
def report(request, event):
    return render(request, "reporting/index.html", {"event": event, "role": request.event_role, **summary(event)})

@event_access("organizer", "treasurer")
def stats(request, event):
    data = summary(event)
    return JsonResponse({k: data[k] for k in ["registered", "arrived", "attendance", "charts"]})

@event_access("organizer", "treasurer")
def export(request, event):
    data = summary(event)
    wb = Workbook()
    ws = wb.active
    ws.title = "Итоги"
    rows = [["Мероприятие", event.title], ["Зарегистрировались", data["registered"]], ["Пришли", data["arrived"]], ["Посещаемость, %", data["attendance"]], ["План, ₽", data["planned"]], ["Факт, ₽", data["spent"]], ["Остаток, ₽", data["remaining"]], ["Стоимость гостя, ₽", data["cost_per_guest"]], ["Повторные проходы", data["duplicates"]]]
    sheets = [(ws, rows), (wb.create_sheet("Категории"), [["Категория", "Регистрации", "Пришли"]] + [[c.name, c.registered, c.arrived] for c in data["categories"]]), (wb.create_sheet("Смета"), [["Статья", "План", "Факт", "Остаток"]] + [[i.name, i.planned, i.actual, i.remaining] for i in data["items"]]), (wb.create_sheet("Расходы"), [["Дата", "Статья", "Назначение", "Сумма"]] + [[e.date.isoformat(), e.budget_item.name, e.description, e.amount] for e in Expense.objects.filter(budget_item__event=event).select_related("budget_item")]), (wb.create_sheet("Конфликты"), [["Билет", "Время устройства", "Получено сервером", "Результат"]] + [[str(a.ticket_id), a.scanned_at.isoformat(), a.received_at.isoformat(), a.result] for a in ScanAttempt.objects.filter(event=event, result="duplicate")])]
    for sheet, records in sheets:
        for row in records:
            sheet.append(row)
            # Treat all user supplied strings as literal text, including formulas.
            for cell in sheet[sheet.max_row]:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="256D56")
        for col in sheet.columns:
            sheet.column_dimensions[col[0].column_letter].width = min(60, max(18, max(len(str(c.value or "")) for c in col)+2))
    buf = io.BytesIO()
    wb.save(buf)
    audit(request, event, "report.export")
    response = HttpResponse(buf.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="kulisy-{event.pk}.xlsx"'
    return response
