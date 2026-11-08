from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import Event, TicketCategory, TeamMember

class SignupForm(UserCreationForm):
    email = forms.EmailField(label="Электронная почта", max_length=150)
    first_name = forms.CharField(label="Ваше имя", max_length=150)
    class Meta:
        model = User
        fields = ["first_name", "email", "password1", "password2"]
    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Эта почта уже зарегистрирована.")
        return email
    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ["title", "description", "location", "starts_at", "collect_phone", "privacy_contact"]
        widgets = {"starts_at": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}), "description": forms.Textarea(attrs={"rows": 3})}

class CategoryForm(forms.ModelForm):
    class Meta:
        model = TicketCategory
        fields = ["name", "limit"]

class InvitationForm(forms.Form):
    email = forms.EmailField(label="Почта участника")
    role = forms.ChoiceField(label="Роль", choices=TeamMember.ROLES)

class EmailAuthenticationForm(AuthenticationForm):
    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()
