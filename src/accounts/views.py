from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def home(request):
    # Temporary landing page until the customer and pharmacy dashboards exist.
    return render(request, 'accounts/home.html')
