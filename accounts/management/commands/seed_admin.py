import os
from django.core.management.base import BaseCommand
from accounts.models import Organisation, User


class Command(BaseCommand):
    help = "Ensure default org and admin user exist with correct credentials"

    def handle(self, *args, **options):
        if not Organisation.objects.exists():
            org = Organisation.objects.create(name="TalentIQ Demo", slug="talentiq-demo")
            self.stdout.write(f"Created organisation: {org.name}")
        else:
            org = Organisation.objects.first()

        email = "ngaspar10@gmail.com"
        password = os.environ.get("ADMIN_PASSWORD", "TalentIQ2024!")

        try:
            user = User.objects.get(email__iexact=email)
            # Existing user — only fix structural fields, NEVER touch the password.
            # This preserves whatever password the user has set.
            changed = False
            if user.username != email:
                user.username = email
                changed = True
            if not user.is_active:
                user.is_active = True
                changed = True
            if not user.is_superuser:
                user.is_superuser = True
                changed = True
            if not user.is_staff:
                user.is_staff = True
                changed = True
            if user.organisation != org:
                user.organisation = org
                changed = True
            if changed:
                user.save()
            self.stdout.write(f"Admin already exists: {email} (password unchanged)")
        except User.DoesNotExist:
            # New user — set everything including the initial password.
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                organisation=org,
                role=User.ROLE_ADMIN,
                is_superuser=True,
                is_staff=True,
                is_active=True,
            )
            self.stdout.write(f"Admin created: {email} with password from ADMIN_PASSWORD")
