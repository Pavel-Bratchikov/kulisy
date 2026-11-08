from datetime import timedelta
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Event, TeamMember, Invitation
from .forms import SignupForm, EventForm, CategoryForm, InvitationForm
from .access import event_access, role_for, audit
from reporting.services import summary


def signup(request):
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("event-list")
    return render(request, "registration/signup.html", {"form": form})

@login_required
def event_list(request):
    events = Event.objects.filter(Q(owner=request.user) | Q(members__user=request.user)).distinct()
    return render(request, "events/list.html", {"events": events})

@login_required
def event_create(request):
    form = EventForm(request.POST or None, initial={"privacy_contact": request.user.email})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            User.objects.select_for_update().get(pk=request.user.pk)
            if Event.objects.filter(owner=request.user).exclude(status="archived").exists():
                form.add_error(None, "В тарифе «Старт» доступно одно активное мероприятие. Архивируйте предыдущее.")
            else:
                event = form.save(commit=False)
                event.owner = request.user
                event.save()
                TeamMember.objects.create(event=event, user=request.user, role="organizer")
                event.categories.create(name="Основной билет", limit=100)
                audit(request, event, "event.create")
                return redirect("event-detail", event.pk)
    return render(request, "events/form.html", {"form": form, "title": "Новое мероприятие"})

@event_access("organizer", "treasurer", "controller")
def event_detail(request, event):
    if request.event_role == "controller":
        return redirect("scanner", event.pk)
    return render(request, "events/detail.html", {"event": event, "role": request.event_role, **summary(event)})

@event_access("organizer")
def event_edit(request, event):
    form = EventForm(request.POST or None, instance=event)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request, event, "event.update")
        return redirect("event-detail", event.pk)
    return render(request, "events/form.html", {"form": form, "event": event, "role": "organizer", "title": "Настройки мероприятия"})

@event_access("organizer")
@require_POST
def event_status(request, event):
    status = request.POST.get("status")
    if status not in dict(Event.STATUS):
        raise PermissionDenied
    with transaction.atomic():
        User.objects.select_for_update().get(pk=event.owner_id)
        event = Event.objects.select_for_update().get(pk=event.pk)
        if event.status == "archived" and status != "archived" and Event.objects.filter(owner=event.owner).exclude(pk=event.pk).exclude(status="archived").exists():
            messages.error(request, "Сначала архивируйте другое активное мероприятие.")
        else:
            event.status = status
            event.save(update_fields=["status"])
            audit(request, event, "event.status", status)
    return redirect("event-detail", event.pk)

@event_access("organizer")
def categories(request, event):
    form = CategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["limit"] > event.capacity:
            form.add_error("limit", f"Общий лимит мероприятия — {event.capacity}.")
        else:
            category = form.save(commit=False)
            category.event = event
            category.save()
            audit(request, event, "category.create", category.pk)
            return redirect("categories", event.pk)
    return render(request, "events/categories.html", {"event": event, "role": "organizer", "form": form})

@event_access("organizer")
def team(request, event):
    form = InvitationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            Event.objects.select_for_update().get(pk=event.pk)
            pending = event.invitations.filter(accepted_at__isnull=True, revoked=False, expires_at__gt=timezone.now()).count()
            if event.members.count() + pending >= event.team_limit:
                form.add_error(None, "Достигнут лимит команды с учётом активных приглашений.")
            else:
                Invitation.objects.create(event=event, email=form.cleaned_data["email"].lower(), role=form.cleaned_data["role"], expires_at=timezone.now()+timedelta(days=7))
                audit(request, event, "team.invite")
                return redirect("team", event.pk)
    invitations = event.invitations.filter(accepted_at__isnull=True, revoked=False, expires_at__gt=timezone.now())
    for invite in invitations:
        invite.link = request.build_absolute_uri(reverse("invite", args=[invite.token]))
    return render(request, "events/team.html", {"event": event, "role": "organizer", "form": form, "invitations": invitations})

@event_access("organizer")
@require_POST
def team_remove(request, event, member_id):
    member = get_object_or_404(TeamMember, event=event, pk=member_id)
    if member.user_id == event.owner_id:
        raise PermissionDenied
    audit(request, event, "team.remove", member.pk)
    member.delete()
    return redirect("team", event.pk)

@event_access("organizer")
@require_POST
def invite_revoke(request, event, invite_id):
    invite = get_object_or_404(Invitation, event=event, pk=invite_id)
    invite.revoked = True
    invite.save(update_fields=["revoked"])
    return redirect("team", event.pk)

@login_required
def invite(request, token):
    invitation = get_object_or_404(Invitation, token=token)
    if request.method == "POST":
        with transaction.atomic():
            Event.objects.select_for_update().get(pk=invitation.event_id)
            invitation = Invitation.objects.select_for_update().get(pk=invitation.pk)
            if invitation.revoked or invitation.accepted_at or invitation.expires_at <= timezone.now():
                messages.error(request, "Приглашение истекло или уже использовано.")
            elif request.user.email.lower() != invitation.email.lower():
                messages.error(request, "Войдите с почтой, на которую выдано приглашение.")
            elif invitation.event.members.count() >= invitation.event.team_limit and not invitation.event.members.filter(user=request.user).exists():
                messages.error(request, "В команде больше нет мест.")
            else:
                if request.user.pk != invitation.event.owner_id:
                    TeamMember.objects.update_or_create(event=invitation.event, user=request.user, defaults={"role": invitation.role})
                invitation.accepted_at = timezone.now()
                invitation.save(update_fields=["accepted_at"])
                audit(request, invitation.event, "team.accept")
                return redirect("event-detail", invitation.event_id)
    return render(request, "events/invite.html", {"invitation": invitation})
