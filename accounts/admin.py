from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Organisation


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    search_fields = ("name", "slug")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "get_full_name", "organisation", "role", "is_active", "is_superuser")
    list_filter = ("role", "is_active", "organisation")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    fieldsets = BaseUserAdmin.fieldsets + (
        ("TalentIQ", {"fields": ("organisation", "role")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("TalentIQ", {"fields": ("email", "organisation", "role")}),
    )
