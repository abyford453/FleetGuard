from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("core:dashboard")
        messages.error(request, "Invalid username or password.")
    return render(request, "accounts/login.html")

def logout_view(request):
    logout(request)
    return redirect("accounts:login")

@require_http_methods(["GET", "POST"])
def signup_view(request):
    # Placeholder signup (we’ll make it real next)
    # For now, show page so it doesn't 404.
    return render(request, "accounts/signup.html")
