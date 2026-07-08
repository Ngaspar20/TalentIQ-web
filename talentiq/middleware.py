from django.shortcuts import redirect

PUBLIC_URLS = ("/accounts/login/", "/accounts/logout/", "/accounts/register/", "/setup/")


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and not request.path.startswith(PUBLIC_URLS):
            return redirect(f"/accounts/login/?next={request.path}")
        return self.get_response(request)
