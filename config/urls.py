from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path
from .health import health
from events import views as e
from events.forms import EmailAuthenticationForm
from tickets import views as t
from scanning import views as s
from budget import views as b
from reporting import views as r

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health),
    path("accounts/login/", auth.LoginView.as_view(authentication_form=EmailAuthenticationForm), name="login"),
    path("accounts/logout/", auth.LogoutView.as_view(), name="logout"),
    path("accounts/signup/", e.signup, name="signup"),
    path("", e.event_list, name="event-list"),
    path("events/new/", e.event_create, name="event-create"),
    path("events/<int:event_id>/", e.event_detail, name="event-detail"),
    path("events/<int:event_id>/edit/", e.event_edit, name="event-edit"),
    path("events/<int:event_id>/status/", e.event_status, name="event-status"),
    path("events/<int:event_id>/categories/", e.categories, name="categories"),
    path("events/<int:event_id>/team/", e.team, name="team"),
    path("events/<int:event_id>/team/<int:member_id>/remove/", e.team_remove, name="team-remove"),
    path("events/<int:event_id>/invitations/<int:invite_id>/revoke/", e.invite_revoke, name="invite-revoke"),
    path("invite/<uuid:token>/", e.invite, name="invite"),
    path("r/<slug:slug>/", t.register, name="register"),
    path("ticket/<uuid:ticket_id>/", t.ticket_detail, name="ticket"),
    path("ticket/<uuid:ticket_id>/qr.svg", t.ticket_qr, name="ticket-qr"),
    path("events/<int:event_id>/guests/", t.guest_list, name="guests"),
    path("events/<int:event_id>/guests/new/", t.manual_ticket, name="manual-ticket"),
    path("events/<int:event_id>/guests/<uuid:ticket_id>/cancel/", t.cancel_ticket, name="cancel-ticket"),
    path("events/<int:event_id>/scanner/", s.scanner, name="scanner"),
    path("events/<int:event_id>/scanner/snapshot/", s.snapshot, name="snapshot"),
    path("events/<int:event_id>/scanner/sync/", s.sync, name="sync"),
    path("sw.js", s.service_worker, name="service-worker"),
    path("events/<int:event_id>/budget/", b.budget, name="budget"),
    path("events/<int:event_id>/budget/receipt/<int:expense_id>/", b.receipt, name="receipt"),
    path("events/<int:event_id>/report/", r.report, name="report"),
    path("events/<int:event_id>/report.xlsx", r.export, name="export"),
    path("events/<int:event_id>/stats/", r.stats, name="stats"),
]
