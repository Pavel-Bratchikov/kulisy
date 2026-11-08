from django.contrib import admin
from .models import Event, TeamMember, Invitation, TicketCategory, AuditLog
admin.site.register([Event, TeamMember, Invitation, TicketCategory])
@admin.register(AuditLog)
class AuditAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user", "event", "action", "entity"]
    list_filter = ["action"]
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
