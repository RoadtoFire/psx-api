import io
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.management import call_command
from django.conf import settings


def _verify_secret(request):
    return request.headers.get('Authorization') == f'Bearer {settings.CRON_SECRET}'


@csrf_exempt
@require_POST
def run_update_prices(request):
    if not _verify_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    out = io.StringIO()
    call_command('update_prices', stdout=out)
    return JsonResponse({'result': out.getvalue()})


@csrf_exempt
@require_POST
def run_update_dividends(request):
    if not _verify_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    out = io.StringIO()
    call_command('update_dividends', stdout=out)
    return JsonResponse({'result': out.getvalue()})


@csrf_exempt
@require_POST
def run_process_notifications(request):
    if not _verify_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    out = io.StringIO()
    call_command('process_notifications', stdout=out)
    return JsonResponse({'result': out.getvalue()})
