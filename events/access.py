from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from .models import Event, TeamMember, AuditLog

def role_for(user, event):
    if event.owner_id == user.pk:
        return "organizer"
    return TeamMember.objects.filter(event=event, user=user).values_list("role", flat=True).first()

def event_access(*roles):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, event_id, *args, **kwargs):
            event = get_object_or_404(Event, pk=event_id)
            role = role_for(request.user, event)
            if role not in roles:
                raise PermissionDenied
            request.event_role = role
            return view(request, event, *args, **kwargs)
        return wrapped
    return decorator

def audit(request, event, action, entity=""):
    AuditLog.objects.create(event=event, user=request.user if request.user.is_authenticated else None, action=action, entity=str(entity), ip=request.META.get("REMOTE_ADDR"))
