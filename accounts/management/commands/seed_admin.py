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

        user, created = User.objects.get_or_create(
            email__iexact=email,
            defaults={
                "username": email,
                "email": email,
                "organisation": org,
                "role": User.ROLE_ADMIN,
                "is_superuser": True,
                "is_staff": True,
                "is_active": True,
            }
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(f"Admin created: {email} / {password}")
        else:
            user.username = email
            user.is_active = True
            user.is_superuser = True
            user.is_staff = True
            user.organisation = org
            user.save(update_fields=["username", "is_active", "is_superuser", "is_staff", "organisation"])
            self.stdout.write(f"Admin already exists: {email} (password unchanged)")
