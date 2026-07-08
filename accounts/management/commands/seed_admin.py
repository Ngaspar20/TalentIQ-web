import os
from django.core.management.base import BaseCommand
from accounts.models import Organisation, User


class Command(BaseCommand):
    help = "Create default organisation and admin user if none exist"

    def handle(self, *args, **options):
        email = os.environ.get("ADMIN_EMAIL", "admin@talentiq.app")
        password = os.environ.get("ADMIN_PASSWORD", "talentiq2024")

        # Fix: delete old user created with username "admin" (wrong username format)
        User.objects.filter(username="admin").delete()

        if not Organisation.objects.exists():
            org = Organisation.objects.create(name="TalentIQ Demo", slug="talentiq-demo")
            self.stdout.write(f"Created organisation: {org.name}")
        else:
            org = Organisation.objects.first()

        if not User.objects.filter(email=email).exists():
            User.objects.create_superuser(
                username=email,
                email=email,
                password=password,
                organisation=org,
                role=User.ROLE_ADMIN,
            )
            self.stdout.write(f"Created admin user: {email} / {password}")
        else:
            self.stdout.write(f"Admin user already exists: {email}")
