import csv
import os
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.db.models import Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.views.decorators.http import require_POST
from .forms import FORM_MAP, form_for
from .models import AuditEvent, Campaign, Company, Contact, Deal, Lead, SupportCase, Task
from .models import Team

MODULES = {
    "leads": ("Leads", Lead, ["name", "company_name", "email", "status", "owner"]),
    "contacts": ("Contacts", Contact, ["name", "company", "email", "phone", "owner"]),
    "companies": ("Companies", Company, ["name", "industry", "website", "owner"]),
    "deals": ("Deals", Deal, ["title", "company", "stage", "amount", "expected_close", "owner"]),
    "support": ("Support", SupportCase, ["title", "contact", "status", "priority", "owner"]),
    "tasks": ("Tasks", Task, ["title", "status", "due_date", "owner"]),
    "campaigns": ("Campaigns", Campaign, ["title", "channel", "status", "budget", "target_contacts", "responses", "conversions", "revenue", "owner"]),
}

def scoped(queryset, user):
    if user.is_superuser or user.role == "admin": return queryset
    if user.role == "manager": return queryset.filter(team=user.team) if user.team_id else queryset.filter(owner=user)
    return queryset.filter(Q(owner=user) | Q(team=user.team)).distinct() if user.team_id else queryset.filter(owner=user)

def audit(user, module, obj, action):
    AuditEvent.objects.create(actor=user, module=module, record_id=obj.pk, action=action, summary=f"{action.title()} {obj}")

def home(request):
    return redirect("dashboard" if request.user.is_authenticated else "login")

def login_view(request):
    if request.user.is_authenticated: return redirect("dashboard")
    form = AuthenticationForm(request, data=request.POST or None)
    form.fields["username"].label = "Work email"
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        next_url = request.POST.get("next") or request.GET.get("next") or ""
        if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return redirect(next_url)
        return redirect("dashboard")
    return render(request, "account/login.html", {"form": form, "google_enabled": bool(os.environ.get("GOOGLE_OAUTH_CLIENT_ID") and os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET"))})

@login_required
def dashboard(request):
    ctx = {
        "page_title": "Dashboard",
        "metrics": [
            ("Open leads", scoped(Lead.objects.all(), request.user).exclude(status__in=["won", "lost"]).count(), "leads"),
            ("Active deals", scoped(Deal.objects.all(), request.user).exclude(stage__in=["won", "lost"]).count(), "deals"),
            ("Open support", scoped(SupportCase.objects.all(), request.user).exclude(status="resolved").count(), "support"),
            ("Tasks to do", scoped(Task.objects.all(), request.user).exclude(status="done").count(), "tasks"),
        ],
        "pipeline": [],
        "recent_leads": scoped(Lead.objects.select_related("owner", "team"), request.user)[:6],
        "recent_tasks": scoped(Task.objects.select_related("owner", "team"), request.user)[:5],
        "pipeline_total": scoped(Deal.objects.all(), request.user).exclude(stage__in=["won", "lost"]).aggregate(total=Sum("amount"))["total"] or Decimal("0"),
    }
    for value, label in Deal.Stage.choices[:5]:
        qs = scoped(Deal.objects.filter(stage=value), request.user)
        ctx["pipeline"].append({"label": label, "count": qs.count(), "value": qs.aggregate(total=Sum("amount"))["total"] or Decimal("0"), "key": value})
    ctx["max_stage"] = max((stage["count"] for stage in ctx["pipeline"]), default=1) or 1
    return render(request, "crm/dashboard.html", ctx)

@login_required
def record_list(request, module):
    if module not in MODULES: raise Http404
    title, model, columns = MODULES[module]
    qs = scoped(model.objects.select_related("owner", "team"), request.user)
    q = request.GET.get("q", "").strip()[:100]
    if q:
        fields = {
            "leads": ["name", "email", "company_name"], "contacts": ["name", "email", "phone"],
            "companies": ["name", "industry", "website"], "deals": ["title", "company__name"],
            "support": ["title", "contact__name"], "tasks": ["title", "details"],
            "campaigns": ["title", "channel"],
        }[module]
        condition = Q()
        for field in fields: condition |= Q(**{f"{field}__icontains": q})
        qs = qs.filter(condition)
    status = request.GET.get("status", "")
    status_field = "status" if any(f.name == "status" for f in model._meta.fields) else "stage" if any(f.name == "stage" for f in model._meta.fields) else None
    if status and status_field: qs = qs.filter(**{status_field: status})
    rows = [{"obj": obj, "edit_url": f"/{module}/{obj.pk}/edit/"} for obj in qs[:250]]
    statuses = model._meta.get_field(status_field).choices if status_field else []
    return render(request, "crm/record_list.html", {"module": module, "title": title, "columns": columns, "rows": rows, "q": q, "statuses": statuses, "status_field": status_field, "has_status": bool(statuses)})

@login_required
def record_edit(request, module, pk=None):
    if module not in FORM_MAP: raise Http404
    model, _fields = FORM_MAP[module]
    instance = get_object_or_404(scoped(model.objects.all(), request.user), pk=pk) if pk else None
    form = form_for(module, request.user, instance=instance, data=request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if instance is None:
            obj.owner = request.user
            obj.team = request.user.team
        elif request.user.role == "staff" and obj.owner_id != request.user.pk:
            messages.error(request, "You can only update records assigned to you.")
            return redirect(f"/{module}/")
        obj.save()
        form.save_m2m()
        audit(request.user, module, obj, "updated" if instance else "created")
        messages.success(request, f"{obj} saved.")
        return redirect(f"/{module}/")
    return render(request, "crm/record_form.html", {"form": form, "module": module, "title": f"Edit {MODULES[module][0][:-1]}" if instance else f"New {MODULES[module][0][:-1]}", "is_edit": bool(instance)})

@login_required
@require_POST
def record_delete(request, module, pk):
    if module not in MODULES: raise Http404
    _title, model, _columns = MODULES[module]
    obj = get_object_or_404(scoped(model.objects.all(), request.user), pk=pk)
    if request.user.role == "staff" and obj.owner_id != request.user.pk:
        messages.error(request, "You can only delete records assigned to you.")
    else:
        audit(request.user, module, obj, "deleted")
        obj.delete()
        messages.success(request, "Record deleted.")
    return redirect(f"/{module}/")

@login_required
def record_export(request, module):
    if module not in MODULES: raise Http404
    title, model, columns = MODULES[module]
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="orbit-{module}.csv"'
    writer = csv.writer(response)
    writer.writerow([field.replace("_", " ").title() for field in columns])
    for obj in scoped(model.objects.select_related("owner", "team"), request.user).iterator(chunk_size=200):
        cells = [str(getattr(obj, field, "") or "") for field in columns]
        writer.writerow([("'" + value) if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value for value in cells])
    return response

@login_required
def reports(request):
    deals = scoped(Deal.objects.all(), request.user)
    campaigns = scoped(Campaign.objects.all(), request.user)
    tasks = scoped(Task.objects.all(), request.user)
    stages = []
    for key, label in Deal.Stage.choices:
        qs = deals.filter(stage=key)
        stages.append({"label": label, "count": qs.count(), "value": qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")})
    return render(request, "crm/reports.html", {"stages": stages, "campaigns": campaigns[:8], "tasks_total": tasks.count(), "deals_total": deals.count(), "pipeline_total": deals.exclude(stage__in=["won", "lost"]).aggregate(total=Sum("amount"))["total"] or 0})

@login_required
def audit_log(request):
    if request.user.role not in ("admin", "manager") and not request.user.is_superuser:
        return HttpResponse("Not authorized", status=403)
    events = AuditEvent.objects.select_related("actor")
    if request.user.role != "admin" and not request.user.is_superuser:
        events = events.filter(actor__team=request.user.team)
    return render(request, "crm/audit.html", {"events": events[:200]})

def is_crm_admin(user):
    return user.is_authenticated and (user.is_superuser or user.role == "admin")

@login_required
def my_account(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()[:150]
        last_name = request.POST.get("last_name", "").strip()[:150]
        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.save(update_fields=["first_name", "last_name"])
        audit(request.user, "account", request.user, "updated")
        messages.success(request, "Your profile has been updated.")
        return redirect("my_account")
    return render(request, "crm/my_account.html")

@login_required
def settings_page(request):
    if not is_crm_admin(request.user): return HttpResponse("Not authorized", status=403)
    return render(request, "crm/settings.html", {"user_count": get_user_model().objects.filter(is_active=True).count(), "team_count": Team.objects.count()})

@login_required
def manage_teams(request):
    if not is_crm_admin(request.user): return HttpResponse("Not authorized", status=403)
    if request.method == "POST":
        name = request.POST.get("name", "").strip()[:120]
        if not name:
            messages.error(request, "Enter a team name.")
        else:
            team, created = Team.objects.get_or_create(name=name)
            if created:
                AuditEvent.objects.create(actor=request.user, module="teams", record_id=team.pk, action="created", summary=f"Created team {name}")
            messages.success(request, "Team created." if created else "That team already exists.")
        return redirect("manage_teams")
    return render(request, "crm/teams.html", {"teams": Team.objects.all()})

@login_required
def edit_team(request, pk):
    if not is_crm_admin(request.user): return HttpResponse("Not authorized", status=403)
    team = get_object_or_404(Team, pk=pk)
    if request.method == "POST":
        name = request.POST.get("name", "").strip()[:120]
        if not name:
            messages.error(request, "Enter a team name.")
        elif Team.objects.exclude(pk=team.pk).filter(name__iexact=name).exists():
            messages.error(request, "That team name is already in use.")
        else:
            previous_name = team.name
            team.name = name
            team.save(update_fields=["name"])
            AuditEvent.objects.create(actor=request.user, module="teams", record_id=team.pk, action="updated", summary=f"Renamed team {previous_name} to {name}")
            messages.success(request, "Team updated.")
            return redirect("manage_teams")
    return render(request, "crm/teams.html", {"teams": Team.objects.all(), "editing_team": team})

@login_required
@require_POST
def remove_team(request, pk):
    if not is_crm_admin(request.user): return HttpResponse("Not authorized", status=403)
    team = get_object_or_404(Team, pk=pk)
    team_name, team_pk = team.name, team.pk
    team.delete()
    AuditEvent.objects.create(actor=request.user, module="teams", record_id=team_pk, action="removed", summary=f"Removed team {team_name}")
    messages.success(request, "Team removed. Members and records were kept, but are no longer assigned to that team.")
    return redirect("manage_teams")

@login_required
def manage_users(request):
    if not is_crm_admin(request.user): return HttpResponse("Not authorized", status=403)
    UserModel = get_user_model()
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        role = request.POST.get("role", "staff")
        team_id = request.POST.get("team")
        team = Team.objects.filter(pk=team_id).first() if team_id else None
        try:
            validate_email(email)
            valid_email = True
        except ValidationError:
            valid_email = False
        if not valid_email or role not in ("admin", "manager", "staff"):
            messages.error(request, "Enter a valid email address and role.")
        elif UserModel.objects.filter(email__iexact=email).exists():
            messages.error(request, "An account already uses that email.")
        else:
            import secrets
            username = f"u{secrets.token_hex(16)}"
            new_user = UserModel.objects.create_user(username=username, email=email, role=role, team=team, is_active=True)
            new_user.set_password(secrets.token_urlsafe(48))
            new_user.save(update_fields=["password"])
            reset = PasswordResetForm({"email": email})
            if reset.is_valid() and (os.environ.get("EMAIL_HOST") or os.environ.get("DJANGO_DEBUG", "false").lower() == "true"):
                try:
                    current_site = Site.objects.get_current()
                    current_site.domain = request.get_host()
                    current_site.name = "SJCRM"
                    current_site.save(update_fields=["domain", "name"])
                    reset.save(request=request, use_https=request.is_secure(), email_template_name="account/password_reset_email.txt")
                except Exception:
                    messages.warning(request, "Account created, but the setup email could not be sent. Check email settings.")
            AuditEvent.objects.create(actor=request.user, module="users", record_id=new_user.pk, action="invited", summary=f"Invited {email} as {role}")
            messages.success(request, "Account created. A password setup link was sent if email delivery is configured.")
        return redirect("manage_users")
    return render(request, "crm/users.html", {"users": UserModel.objects.select_related("team").order_by("email"), "teams": Team.objects.all()})

@login_required
def edit_user(request, pk):
    if not is_crm_admin(request.user): return HttpResponse("Not authorized", status=403)
    UserModel = get_user_model()
    member = get_object_or_404(UserModel.objects.select_related("team"), pk=pk)
    if member.is_superuser:
        messages.error(request, "Superuser accounts can only be changed in Django administration.")
        return redirect("manage_users")
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        role = request.POST.get("role", "staff")
        team_id = request.POST.get("team")
        team = Team.objects.filter(pk=team_id).first() if team_id else None
        try:
            validate_email(email)
            valid_email = True
        except ValidationError:
            valid_email = False
        if not valid_email or role not in ("admin", "manager", "staff"):
            messages.error(request, "Enter a valid email address and role.")
        elif UserModel.objects.exclude(pk=member.pk).filter(email__iexact=email).exists():
            messages.error(request, "An account already uses that email.")
        else:
            member.email, member.role, member.team = email, role, team
            member.save(update_fields=["email", "role", "team"])
            AuditEvent.objects.create(actor=request.user, module="users", record_id=member.pk, action="updated", summary=f"Updated member {email}")
            messages.success(request, "Member updated.")
            return redirect("manage_users")
    return render(request, "crm/users.html", {"users": UserModel.objects.select_related("team").order_by("email"), "teams": Team.objects.all(), "editing_member": member})

@login_required
@require_POST
def remove_user(request, pk):
    if not is_crm_admin(request.user): return HttpResponse("Not authorized", status=403)
    UserModel = get_user_model()
    member = get_object_or_404(UserModel, pk=pk)
    if member.pk == request.user.pk:
        messages.error(request, "You cannot remove your own access.")
    elif member.is_superuser:
        messages.error(request, "Superuser accounts can only be changed in Django administration.")
    elif not member.is_active:
        messages.info(request, "That member already has no access.")
    else:
        member.is_active = False
        member.save(update_fields=["is_active"])
        AuditEvent.objects.create(actor=request.user, module="users", record_id=member.pk, action="removed", summary=f"Removed access for {member.email}")
        messages.success(request, "Member access removed. Their CRM history was retained.")
    return redirect("manage_users")

@login_required
def global_search(request):
    q = request.GET.get("q", "").strip()[:100]
    results = []
    if q:
        for module, fields in {
            "leads": (Lead, ("name", "email", "company_name")), "contacts": (Contact, ("name", "email")),
            "companies": (Company, ("name", "industry")), "deals": (Deal, ("title",)),
            "support": (SupportCase, ("title",)), "tasks": (Task, ("title",)), "campaigns": (Campaign, ("title",)),
        }.items():
            model, search_fields = fields
            condition = Q()
            for field in search_fields: condition |= Q(**{f"{field}__icontains": q})
            results.extend({"module": module, "object": obj} for obj in scoped(model.objects.filter(condition), request.user)[:20])
    return render(request, "crm/search.html", {"q": q, "results": results})
