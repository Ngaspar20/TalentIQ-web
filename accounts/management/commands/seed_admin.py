import os
from django.core.management.base import BaseCommand
from accounts.models import Organisation, User


class Command(BaseCommand):
    help = "Create default organisation and admin user if none exist"

    def handle(self, *args, **options):
        if Organisation.objects.exists():
            self.stdout.write("Organisation already exists, skipping seed.")
            return

        org = Organisation.objects.create(name="TalentIQ Demo", slug="talentiq-demo")
        self.stdout.write(f"Created organisation: {org.name}")

        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD", "talentiq2024")
        email = os.environ.get("ADMIN_EMAIL", "admin@talentiq.app")

        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            organisation=org,
            role=User.ROLE_ADMIN,
        )
        self.stdout.write(f"Created admin user: {user.username} / {password}")
