import os
from django.core.management.base import BaseCommand
from accounts.models import Organisation, User


class Command(BaseCommand):
    help = "Ensure org, admin user, and superuser privileges exist"

    def handle(self, *args, **options):
        # Remove legacy placeholder user
        User.objects.filter(username="admin").exclude(email="admin").delete()

        # Ensure organisation exists
        if not Organisation.objects.exists():
            email = os.environ.get("ADMIN_EMAIL", "admin@talentiq.app")
            password = os.environ.get("ADMIN_PASSWORD", "talentiq2024")
            org = Organisation.objects.create(name="TalentIQ Demo", slug="talentiq-demo")
            User.objects.create_superuser(
                username=email, email=email, password=password,
                organisation=org, role=User.ROLE_ADMIN,
            )
            self.stdout.write(f"Created org and admin: {email} / {password}")
            return

        # Promote all existing users to superuser/staff so /admin/ is accessible
        updated = User.objects.filter(is_superuser=False).update(
            is_superuser=True, is_staff=True
        )
        if updated:
            self.stdout.write(f"Promoted {updated} user(s) to superuser.")
        else:
            self.stdout.write("All users already have superuser access.")
