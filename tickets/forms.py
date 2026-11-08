from django import forms
from .models import Ticket

class RegistrationForm(forms.ModelForm):
    consent = forms.BooleanField(label="Я согласен на обработку моих данных для регистрации и прохода на мероприятие.")
    class Meta:
        model = Ticket
        fields = ["full_name", "email", "phone", "category"]
        labels = {"category": "Категория билета"}
    def __init__(self, *args, event, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = event.categories.all()
        if not event.collect_phone:
            del self.fields["phone"]
    def clean_email(self):
        return self.cleaned_data["email"].lower()
