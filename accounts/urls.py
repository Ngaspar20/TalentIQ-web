from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_view, name="register"),
    path("profile/", views.profile_view, name="profile"),
    path("reset-admin/", views.reset_admin_password, name="reset_admin"),
    path("system-init/", views.system_init, name="system_init"),
    path("debug-login/", views.debug_login, name="debug_login"),
    path("debug-auth/", views.debug_auth, name="debug_auth"),
    path("auto-login/", views.auto_login, name="auto_login"),
]
