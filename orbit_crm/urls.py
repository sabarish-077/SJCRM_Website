from django.contrib.auth import views as auth_views
from django.urls import include, path
from crm.admin import crm_admin_site
from crm import views

urlpatterns = [
    path("admin/", crm_admin_site.urls),
    path("accounts/", include("allauth.urls")),
    path("login/", views.login_view, name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password-reset/", auth_views.PasswordResetView.as_view(template_name="account/password_reset.html", email_template_name="account/password_reset_email.txt", success_url="/login/?reset=sent"), name="password_reset"),
    path("password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(template_name="account/password_reset_confirm.html", success_url="/password-reset/complete/"), name="password_reset_confirm"),
    path("password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(template_name="account/password_reset_complete.html"), name="password_reset_complete"),
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("reports/", views.reports, name="reports"),
    path("settings/", views.settings_page, name="settings"),
    path("settings/backup/", views.download_backup, name="download_backup"),
    path("account/", views.my_account, name="my_account"),
    path("audit/", views.audit_log, name="audit_log"),
    path("search/", views.global_search, name="global_search"),
    path("settings/teams/", views.manage_teams, name="manage_teams"),
    path("settings/teams/<int:pk>/edit/", views.edit_team, name="edit_team"),
    path("settings/teams/<int:pk>/remove/", views.remove_team, name="remove_team"),
    path("settings/users/", views.manage_users, name="manage_users"),
    path("settings/users/<int:pk>/edit/", views.edit_user, name="edit_user"),
    path("settings/users/<int:pk>/remove/", views.remove_user, name="remove_user"),
    path("settings/users/<int:pk>/enable/", views.enable_user, name="enable_user"),
    path("<slug:module>/", views.record_list, name="record_list"),
    path("<slug:module>/new/", views.record_edit, name="record_new"),
    path("<slug:module>/<int:pk>/edit/", views.record_edit, name="record_edit"),
    path("<slug:module>/<int:pk>/delete/", views.record_delete, name="record_delete"),
    path("<slug:module>/export.csv", views.record_export, name="record_export"),
]

handler404 = "crm.views.page_not_found"
handler500 = "crm.views.server_error"
