from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import AuditEvent, Campaign, Company, Contact, Deal, Lead, SupportCase, Task, Team, User

@admin.register(User)
class CRMUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("CRM access", {"fields": ("role", "team")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("CRM access", {"fields": ("email", "role", "team")}),)
    list_display = ("username", "email", "role", "team", "is_active", "is_superuser")
    list_filter = ("role", "team", "is_active")

admin.site.register([Team, Company, Contact, Lead, Deal, SupportCase, Task, Campaign])
@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "module", "record_id", "summary")
    list_filter = ("action", "module")
    readonly_fields = ("actor", "module", "record_id", "action", "summary", "created_at")
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
