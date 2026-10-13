from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@login_required
def home(request):
    if request.user.is_pharmacy:
        return redirect('chats:inbox')
    return redirect('orders:list')
