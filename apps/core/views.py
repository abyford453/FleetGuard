from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

def home(request):
    # Always send to login for now (hero page)
    return redirect("accounts:login")

@login_required
def dashboard(request):
    return render(request, "core/dashboard.html")
