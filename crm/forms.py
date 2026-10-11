from django import forms
from django.db.models import Q
from .models import Campaign, Company, Contact, Deal, Lead, SupportCase, Task, Team, User

FORM_MAP = {
    "leads": (Lead, ["name", "email", "phone", "company_name", "source", "status"]),
    "contacts": (Contact, ["name", "email", "phone", "title", "company"]),
    "companies": (Company, ["name", "website", "industry", "phone"]),
    "deals": (Deal, ["title", "company", "contact", "amount", "stage", "expected_close"]),
    "support": (SupportCase, ["title", "contact", "status", "priority", "description"]),
    "tasks": (Task, ["title", "due_date", "status", "contact", "deal", "support_case", "details"]),
    "campaigns": (Campaign, ["title", "channel", "status", "budget", "starts_on", "ends_on", "target_contacts", "responses", "conversions", "revenue", "contacts", "goal"]),
}

class CRMRecordForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = []
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if "owner" in self.fields:
            owner_qs = User.objects.filter(is_active=True)
            team_qs = Team.objects.all()
            if user.role == "manager" and user.team_id:
                owner_qs = owner_qs.filter(team=user.team)
                team_qs = team_qs.filter(pk=user.team_id)
            self.fields["owner"].queryset = owner_qs
            self.fields["team"].queryset = team_qs
            if not self.instance.pk:
                self.fields["owner"].initial = user
                self.fields["team"].initial = user.team
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            if isinstance(field, forms.DateField): field.widget = forms.DateInput(attrs={"type": "date", "class": "form-control"})
            if isinstance(field, forms.DecimalField): field.widget.attrs["step"] = "0.01"
        for name in ("company", "contact", "deal", "support_case", "contacts"):
            if name in self.fields:
                qs = self.fields[name].queryset
                if user.is_superuser or user.role == "admin":
                    self.fields[name].queryset = qs
                elif user.role == "manager":
                    self.fields[name].queryset = qs.filter(team=user.team) if user.team_id else qs.filter(owner=user)
                else:
                    self.fields[name].queryset = qs.filter(Q(owner=user) | Q(team=user.team)).distinct() if user.team_id else qs.filter(owner=user)

    def clean(self):
        cleaned = super().clean()
        owner = cleaned.get("owner")
        team = cleaned.get("team")
        if owner and owner.team_id != getattr(team, "pk", None):
            self.add_error("owner", "The selected owner must belong to the selected team.")
        return cleaned

def form_for(module, user, instance=None, data=None):
    model, fields = FORM_MAP[module]
    fields = list(fields)
    declared = {}
    if user.role in ("admin", "manager") or user.is_superuser:
        fields.extend(["owner", "team"])
        declared["owner"] = forms.ModelChoiceField(queryset=User.objects.none(), required=False, label="Record owner")
        declared["team"] = forms.ModelChoiceField(queryset=Team.objects.none(), required=False, label="Team")
    Meta = type("Meta", (), {"model": model, "fields": fields})
    declared["Meta"] = Meta
    Form = type(f"{model.__name__}Form", (CRMRecordForm,), declared)
    return Form(data=data, instance=instance, user=user)
