from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def index(request):
    tenant = getattr(request, "tenant", None)
    return render(request, "settings_app/index.html", {"tenant": tenant})
