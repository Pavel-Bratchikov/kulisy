import io
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook
from events.models import Event, TeamMember, Invitation, AuditLog
from tickets.models import Ticket, MailDelivery
from tickets.services import issue_ticket
from scanning.models import CheckIn, ScanAttempt
from budget.models import BudgetItem, Expense
from reporting.services import summary

class WorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='owner@example.test', email='owner@example.test', password='SecurePass-123')
        cls.controller = User.objects.create_user(username='door@example.test', email='door@example.test')
        cls.treasurer = User.objects.create_user(username='money@example.test', email='money@example.test')
        cls.outsider = User.objects.create_user(username='other@example.test', email='other@example.test')
        cls.event = Event.objects.create(title='Тестовое событие', location='Зал', starts_at=timezone.now(), owner=cls.owner, status='published', privacy_contact=cls.owner.email)
        for user, role in [(cls.owner,'organizer'), (cls.controller,'controller'), (cls.treasurer,'treasurer')]:
            TeamMember.objects.create(event=cls.event,user=user,role=role)
        cls.category = cls.event.categories.create(name='Гости',limit=2)
        cls.other = Event.objects.create(title='Чужое событие',location='Другой зал',starts_at=timezone.now(),owner=cls.outsider,status='published',privacy_contact=cls.outsider.email)
        cls.other_category = cls.other.categories.create(name='Другое',limit=100)

    def data(self, email='guest@example.test', **kwargs):
        return {'full_name':'Анна Петрова','email':email,'category':self.category,'consent':True,**kwargs}
    def ticket(self, **kwargs):
        return issue_ticket(self.event,self.data(**kwargs))
    def scan(self,ticket,**kwargs):
        return {'id':str(uuid.uuid4()),'ticket_id':str(ticket.pk),'device_id':str(uuid.uuid4()),'scanned_at':timezone.now().isoformat(),'source':'scan',**kwargs}
    def sync(self, rows):
        return self.client.post(reverse('sync',args=[self.event.pk]),json.dumps({'attempts':rows}),content_type='application/json')

    def test_public_registration_creates_ticket_and_persistent_mail(self):
        data=self.data();data['category']=self.category.pk
        response=self.client.post(reverse('register',args=[self.event.slug]),data)
        self.assertEqual(response.status_code,302)
        ticket=Ticket.objects.get()
        self.assertEqual(ticket.email,'guest@example.test')
        self.assertIsNotNone(ticket.consent_at)
        self.assertEqual(MailDelivery.objects.count(),1)
        self.assertContains(self.client.get(response.url),'Анна Петрова')
        self.assertContains(self.client.get(reverse('ticket-qr',args=[ticket.pk])),'<svg')

    def test_consent_required(self):
        with self.assertRaises(ValidationError): issue_ticket(self.event,self.data(consent=False))
        self.assertFalse(Ticket.objects.exists())

    def test_category_limit_is_enforced(self):
        self.ticket();self.ticket(email='two@example.test')
        with self.assertRaises(ValidationError): self.ticket(email='three@example.test')
        self.assertEqual(Ticket.objects.count(),2)

    def test_event_limit_across_categories(self):
        self.event.capacity=1;self.event.save()
        self.ticket()
        other=self.event.categories.create(name='Волонтёры',limit=10)
        with self.assertRaises(ValidationError): self.ticket(email='two@example.test',category=other)

    def test_duplicate_email_case_insensitive(self):
        self.ticket()
        with self.assertRaises(ValidationError): self.ticket(email='GUEST@EXAMPLE.TEST')

    def test_closed_event_rejects_public_and_manual_issue(self):
        self.event.status='closed';self.event.save()
        for manual in [False,True]:
            with self.assertRaises(ValidationError): issue_ticket(self.event,self.data(),manual=manual)

    def test_manual_issue_in_draft(self):
        self.event.status='draft';self.event.save()
        ticket=issue_ticket(self.event,self.data(),manual=True)
        self.assertTrue(ticket.manual)

    def test_phone_not_collected_when_disabled(self):
        self.assertEqual(self.ticket(phone='+79991234567').phone,'')

    def test_foreign_category_cannot_be_posted(self):
        data=self.data(category=self.other_category.pk)
        response=self.client.post(reverse('register',args=[self.event.slug]),data)
        self.assertEqual(response.status_code,200)
        self.assertFalse(Ticket.objects.exists())

    def test_role_matrix(self):
        matrix={'event-detail':{'organizer','treasurer','controller'},'guests':{'organizer'},'categories':{'organizer'},'team':{'organizer'},'event-edit':{'organizer'},'manual-ticket':{'organizer'},'scanner':{'organizer','controller'},'snapshot':{'organizer','controller'},'budget':{'organizer','treasurer'},'report':{'organizer','treasurer'},'export':{'organizer','treasurer'},'stats':{'organizer','treasurer'}}
        for user,role in [(self.owner,'organizer'),(self.controller,'controller'),(self.treasurer,'treasurer'),(self.outsider,'outsider')]:
            self.client.force_login(user)
            for name,allowed in matrix.items():
                with self.subTest(role=role,name=name):
                    response=self.client.get(reverse(name,args=[self.event.pk]))
                    self.assertIn(response.status_code,[200,302] if role in allowed else [403])

    def test_snapshot_minimizes_personal_data(self):
        self.ticket(phone='123')
        self.client.force_login(self.controller)
        response=self.client.get(reverse('snapshot',args=[self.event.pk]))
        ticket=response.json()['tickets'][0]
        self.assertEqual(set(ticket),{'id','name','category','status','checked'})
        self.assertNotContains(response,'guest@example.test')
        self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertTrue(AuditLog.objects.filter(action='scanner.snapshot').exists())

    def test_sync_is_idempotent_and_duplicates_reported(self):
        ticket=self.ticket();self.client.force_login(self.controller)
        first=self.scan(ticket)
        self.assertEqual(self.sync([first]).json()['results'][0]['result'],'accepted')
        self.assertEqual(self.sync([first]).json()['results'][0]['result'],'accepted')
        self.assertEqual(ScanAttempt.objects.count(),1)
        self.assertEqual(self.sync([self.scan(ticket)]).json()['results'][0]['result'],'duplicate')
        self.assertEqual(CheckIn.objects.count(),1)
        self.assertEqual(summary(self.event)['duplicates'],1)

    def test_sync_rejects_foreign_ticket(self):
        ticket=issue_ticket(self.other,self.data(category=self.other_category))
        self.client.force_login(self.controller)
        self.assertEqual(self.sync([self.scan(ticket)]).json()['results'][0]['result'],'invalid')
        self.assertFalse(CheckIn.objects.exists())

    def test_cancelled_ticket_cannot_enter(self):
        ticket=self.ticket();ticket.status='cancelled';ticket.save()
        self.client.force_login(self.controller)
        self.assertEqual(self.sync([self.scan(ticket)]).json()['results'][0]['result'],'cancelled')
        self.assertFalse(CheckIn.objects.exists())

    def test_bad_sync_payload_is_atomic(self):
        ticket=self.ticket();self.client.force_login(self.controller)
        response=self.sync([self.scan(ticket),self.scan(ticket,scanned_at='not-a-date')])
        self.assertEqual(response.status_code,400)
        self.assertFalse(CheckIn.objects.exists())
        self.assertEqual(self.sync([self.scan(ticket,scanned_at=(timezone.now()+timedelta(days=1)).isoformat())]).status_code,400)

    def test_checkin_protects_ticket_from_cancellation(self):
        ticket=self.ticket();self.client.force_login(self.owner)
        self.sync([self.scan(ticket)])
        self.client.post(reverse('cancel-ticket',args=[self.event.pk,ticket.pk]))
        ticket.refresh_from_db();self.assertEqual(ticket.status,'active')

    def test_cancellation_releases_capacity(self):
        ticket=self.ticket();self.client.force_login(self.owner)
        self.client.post(reverse('cancel-ticket',args=[self.event.pk,ticket.pk]))
        self.ticket();self.assertEqual(self.event.tickets.filter(status='active').count(),1)

    def test_plan_fact_and_excel_formula_safety(self):
        item=BudgetItem.objects.create(event=self.event,name='=1+1',planned=Decimal('100.00'))
        Expense.objects.create(budget_item=item,amount=Decimal('120.10'),description='Печать',date=timezone.localdate(),author=self.treasurer)
        data=summary(self.event)
        self.assertEqual(data['remaining'],Decimal('-20.10'))
        self.assertIsNone(data['cost_per_guest'])
        self.client.force_login(self.owner)
        response=self.client.get(reverse('export',args=[self.event.pk]))
        workbook=load_workbook(io.BytesIO(response.content))
        self.assertEqual(workbook['Смета']['A2'].value,'=1+1')
        self.assertEqual(workbook['Смета']['A2'].data_type,'s')
        self.assertEqual(workbook['Смета']['C2'].value,120.10)

    def test_expense_cannot_target_other_event(self):
        item=BudgetItem.objects.create(event=self.other,name='Чужая смета',planned=100)
        self.client.force_login(self.treasurer)
        self.client.post(reverse('budget',args=[self.event.pk]),{'action':'expense','budget_item':item.pk,'amount':'10','description':'x','date':'2026-11-08'})
        self.assertFalse(Expense.objects.exists())

    def test_invalid_receipt_rejected(self):
        item=BudgetItem.objects.create(event=self.event,name='Печать',planned=100)
        self.client.force_login(self.treasurer)
        response=self.client.post(reverse('budget',args=[self.event.pk]),{'action':'expense','budget_item':item.pk,'amount':'10','description':'x','date':'2026-11-08','receipt':SimpleUploadedFile('test.png',b'not an image',content_type='image/png')})
        self.assertEqual(response.status_code,200)
        self.assertFalse(Expense.objects.exists())

    def test_negative_expense_rejected(self):
        item=BudgetItem.objects.create(event=self.event,name='Печать',planned=100)
        self.client.force_login(self.treasurer)
        self.client.post(reverse('budget',args=[self.event.pk]),{'action':'expense','budget_item':item.pk,'amount':'-10','description':'x','date':'2026-11-08'})
        self.assertFalse(Expense.objects.exists())

    def test_invitation_bound_to_email_and_single_use(self):
        self.event.team_limit=5;self.event.save()
        invite=Invitation.objects.create(event=self.event,email=self.outsider.email,role='controller',expires_at=timezone.now()+timedelta(days=1))
        url=reverse('invite',args=[invite.token])
        self.client.force_login(self.treasurer);self.client.post(url)
        invite.refresh_from_db();self.assertIsNone(invite.accepted_at)
        self.client.force_login(self.outsider);self.assertEqual(self.client.post(url).status_code,302)
        self.assertTrue(TeamMember.objects.filter(event=self.event,user=self.outsider,role='controller').exists())
        self.assertEqual(self.client.post(url).status_code,200)

    def test_invitation_expiry_and_revocation(self):
        self.client.force_login(self.outsider)
        for revoked,delta in [(True,1),(False,-1)]:
            invite=Invitation.objects.create(event=self.event,email=self.outsider.email,role='controller',revoked=revoked,expires_at=timezone.now()+timedelta(days=delta))
            self.client.post(reverse('invite',args=[invite.token]))
        self.assertFalse(TeamMember.objects.filter(event=self.event,user=self.outsider).exists())

    def test_team_limit_includes_pending_invites(self):
        self.client.force_login(self.owner)
        self.client.post(reverse('team',args=[self.event.pk]),{'email':'new@example.test','role':'controller'})
        self.assertFalse(Invitation.objects.exists())

    def test_mail_failure_retries_without_losing_ticket(self):
        ticket=self.ticket()
        with patch('tickets.management.commands.send_ticket_emails.EmailMessage.send',side_effect=OSError('smtp down')):
            call_command('send_ticket_emails')
        delivery=MailDelivery.objects.get()
        self.assertEqual(delivery.attempts,1)
        self.assertIsNone(delivery.sent_at)
        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())
        delivery.next_attempt_at=timezone.now();delivery.save()
        with patch('tickets.management.commands.send_ticket_emails.EmailMessage.send',return_value=1) as send:
            call_command('send_ticket_emails');call_command('send_ticket_emails')
            self.assertEqual(send.call_count,1)
        delivery.refresh_from_db();self.assertIsNotNone(delivery.sent_at)

    def test_post_requires_csrf(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner)
        self.assertEqual(client.post(reverse('event-status',args=[self.event.pk]),{'status':'closed'}).status_code,403)

    def test_event_creation_and_free_limit(self):
        self.client.force_login(self.owner)
        data={'title':'Новый','location':'Зал','starts_at':'2026-11-10T18:00','privacy_contact':self.owner.email}
        response=self.client.post(reverse('event-create'),data)
        self.assertEqual(response.status_code,200)
        self.assertEqual(Event.objects.filter(owner=self.owner).count(),1)
        self.event.status='archived';self.event.save()
        self.assertEqual(self.client.post(reverse('event-create'),data).status_code,302)
        self.assertEqual(Event.objects.filter(owner=self.owner).count(),2)

    def test_signup_email_login(self):
        response=self.client.post(reverse('signup'),{'first_name':'Тест','email':'New@Example.Test','password1':'SecurePass-2026-new','password2':'SecurePass-2026-new'})
        self.assertEqual(response.status_code,302)
        self.client.logout()
        self.assertTrue(self.client.login(username='new@example.test',password='SecurePass-2026-new'))

    def test_event_deletion_cascades_but_category_is_protected(self):
        from django.db.models import RestrictedError
        self.ticket()
        with self.assertRaises(RestrictedError): self.category.delete()
        self.event.delete()
        self.assertFalse(Ticket.objects.exists())
        self.assertFalse(MailDelivery.objects.exists())

    def test_private_receipt_download(self):
        import tempfile
        from PIL import Image
        from django.test import override_settings
        image = io.BytesIO()
        Image.new('RGB', (10, 10), 'white').save(image, format='PNG')
        item = BudgetItem.objects.create(event=self.event, name='Чеки', planned=100)
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            self.client.force_login(self.treasurer)
            response = self.client.post(reverse('budget', args=[self.event.pk]), {'action':'expense', 'budget_item':item.pk, 'amount':'10', 'description':'Чек', 'date':'2026-11-08', 'receipt':SimpleUploadedFile('receipt.png', image.getvalue(), content_type='image/png')})
            self.assertEqual(response.status_code, 302)
            expense = Expense.objects.get()
            url = reverse('receipt', args=[self.event.pk, expense.pk])
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), image.getvalue())
            self.client.force_login(self.controller)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.client.force_login(self.outsider)
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_all_public_pages_render(self):
        for name in ['login','signup']:
            self.assertEqual(self.client.get(reverse(name)).status_code,200)
        self.client.force_login(self.owner)
        for name in ['event-list','event-create']:
            self.assertEqual(self.client.get(reverse(name)).status_code,200)

class PostgreSQLConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_concurrent_last_seat(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections
        user=User.objects.create_user(username='concurrent')
        event=Event.objects.create(title='Последнее место',location='Зал',starts_at=timezone.now(),owner=user,status='published',capacity=1,privacy_contact='x@example.test')
        category=event.categories.create(name='Гости',limit=1)
        def register(index):
            close_old_connections()
            try:
                issue_ticket(event,{'full_name':'Гость','email':f'{index}@example.test','category':category,'consent':True})
                return True
            except ValidationError:
                return False
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(register,range(4)))
        self.assertEqual(results.count(True),1)
        self.assertEqual(Ticket.objects.count(),1)

    @skipUnlessDBFeature('has_select_for_update')
    def test_concurrent_scans_count_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections
        from django.test import RequestFactory
        from scanning.views import sync
        user = User.objects.create_user(username='controller-concurrent')
        event = Event.objects.create(title='Вход', location='Зал', starts_at=timezone.now(), owner=user, status='published', privacy_contact='x@example.test')
        category = event.categories.create(name='Гости', limit=10)
        ticket = issue_ticket(event, {'full_name':'Гость', 'email':'guest@example.test', 'category':category, 'consent':True})
        def enter(index):
            close_old_connections()
            try:
                row = {'id':str(uuid.uuid4()), 'ticket_id':str(ticket.pk), 'device_id':str(uuid.uuid4()), 'scanned_at':timezone.now().isoformat(), 'source':'scan'}
                request = RequestFactory().post('/sync/', json.dumps({'attempts':[row]}), content_type='application/json')
                request.user = user
                response = sync(request, event.pk)
                return json.loads(response.content)['results'][0]['result']
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(enter, range(3)))
        self.assertEqual(results.count('accepted'), 1)
        self.assertEqual(results.count('duplicate'), 2)
        self.assertEqual(CheckIn.objects.count(), 1)
        self.assertEqual(ScanAttempt.objects.count(), 3)
