from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect


def healthz(_request):
    return HttpResponse('ok')


@login_required
def home(request):
    if request.user.is_pharmacy:
        return redirect('chats:inbox')
    return redirect('orders:list')
