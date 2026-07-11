import os
from django.core.management.base import BaseCommand
from accounts.models import Organisation, User


class Command(BaseCommand):
    help = "Ensure default org and admin user exist with correct credentials"

    def handle(self, *args, **options):
        # Only run if the database has no users at all (first deploy).
        if User.objects.exists():
            self.stdout.write("Users already exist — skipping seed_admin.")
            return

        if not Organisation.objects.exists():
            org = Organisation.objects.create(name="TalentIQ Demo", slug="talentiq-demo")
            self.stdout.write(f"Created organisation: {org.name}")
        else:
            org = Organisation.objects.first()

        email = "ngaspar10@gmail.com"
        password = os.environ.get("ADMIN_PASSWORD", "TalentIQ2024!")

        try:
            user = User.objects.get(email__iexact=email)
            user.username = email
            user.is_active = True
            user.is_superuser = True
            user.is_staff = True
            user.organisation = org
            user.set_password(password)
            user.save()
            self.stdout.write(f"Admin updated: {email} — password reset from ADMIN_PASSWORD")
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
