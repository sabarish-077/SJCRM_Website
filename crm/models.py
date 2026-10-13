from django.contrib.auth.models import AbstractUser
from django.db import models

class Team(models.Model):
    name = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        MANAGER = "manager", "Manager"
        STAFF = "staff", "Staff"
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STAFF)
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL, related_name="members")
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

class OwnedRecord(models.Model):
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_records", db_index=True)
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_records", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: abstract = True

class Company(OwnedRecord):
    name = models.CharField(max_length=180)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    class Meta: ordering = ["name"]
    def __str__(self): return self.name

class Contact(OwnedRecord):
    name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=120, blank=True)
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL, related_name="contacts")
    class Meta: ordering = ["name"]
    def __str__(self): return self.name

class Lead(OwnedRecord):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        PROPOSAL = "proposal", "Proposal"
        WON = "won", "Won"
        LOST = "lost", "Lost"
    name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    company_name = models.CharField(max_length=180, blank=True)
    source = models.CharField(max_length=100, blank=True)
    remarks = models.CharField(max_length=2000, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW, db_index=True)
    class Meta: ordering = ["-updated_at"]
    def __str__(self): return self.name

class Deal(OwnedRecord):
    class Stage(models.TextChoices):
        NEW = "new", "New Leads"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        PROPOSAL = "proposal", "Proposal"
        WON = "won", "Won"
        LOST = "lost", "Lost"
    title = models.CharField(max_length=180)
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL, related_name="deals")
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="deals")
    amount = models.DecimalField(max_digits=13, decimal_places=2, default=0)
    stage = models.CharField(max_length=16, choices=Stage.choices, default=Stage.NEW, db_index=True)
    expected_close = models.DateField(null=True, blank=True)
    class Meta: ordering = ["-updated_at"]
    def __str__(self): return self.title

class SupportCase(OwnedRecord):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        WAITING = "waiting", "Waiting"
        RESOLVED = "resolved", "Resolved"
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"
    title = models.CharField(max_length=180)
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="cases")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True)
    priority = models.CharField(max_length=12, choices=Priority.choices, default=Priority.NORMAL)
    description = models.TextField(blank=True)
    class Meta: ordering = ["-updated_at"]
    def __str__(self): return self.title

class Task(OwnedRecord):
    class Status(models.TextChoices):
        TODO = "todo", "To do"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"
    title = models.CharField(max_length=180)
    due_date = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TODO, db_index=True)
    details = models.TextField(blank=True)
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    deal = models.ForeignKey(Deal, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    support_case = models.ForeignKey("SupportCase", null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    class Meta: ordering = ["due_date", "-updated_at"]
    def __str__(self): return self.title

class Campaign(OwnedRecord):
    class Status(models.TextChoices):
        PLANNING = "planning", "Planning"
        ACTIVE = "active", "Active"
        COMPLETE = "complete", "Complete"
        PAUSED = "paused", "Paused"
    title = models.CharField(max_length=180)
    channel = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNING, db_index=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    goal = models.CharField(max_length=240, blank=True)
    target_contacts = models.PositiveIntegerField(default=0)
    responses = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=13, decimal_places=2, default=0)
    contacts = models.ManyToManyField(Contact, blank=True, related_name="campaigns")
    class Meta: ordering = ["-updated_at"]
    def __str__(self): return self.title

class AuditEvent(models.Model):
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="audit_events")
    module = models.CharField(max_length=32)
    record_id = models.PositiveBigIntegerField(null=True)
    action = models.CharField(max_length=20)
    summary = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    class Meta: ordering = ["-created_at"]
    def __str__(self): return f"{self.actor}: {self.action} {self.module}#{self.record_id}"
