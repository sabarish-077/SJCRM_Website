from django.contrib.auth.backends import ModelBackend
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
import secrets
from .models import User

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = (kwargs.get("email") or username or "").strip().casefold()
        if not email or not password:
            return None
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            User().set_password(password)
            return None
        return user if user.check_password(password) and self.user_can_authenticate(user) else None

class EmailSignupAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return True

    def populate_username(self, request, user):
        # The CRM authenticates with email, but Django's user model still stores
        # a private unique username for each account.
        if not user.username:
            user.username = f"u{secrets.token_hex(16)}"

class EmailSignupSocialAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return bool((sociallogin.user.email or "").strip())
