import io
import time
import traceback
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.management import call_command
from django.conf import settings


def _verify_secret(request):
    return request.headers.get('Authorization') == f'Bearer {settings.CRON_SECRET}'


def _run_job(job_name, command_name):
    from stocks.models import CronLog
    out = io.StringIO()
    start = time.time()
    success = True
    try:
        call_command(command_name, stdout=out)
    except Exception:
        out.write(traceback.format_exc())
        success = False
    duration = round(time.time() - start, 2)
    output = out.getvalue()[:5000]
    CronLog.objects.create(name=job_name, success=success, output=output, duration_seconds=duration)
    return output, success


@csrf_exempt
@require_POST
def run_update_prices(request):
    if not _verify_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    output, success = _run_job('update_prices', 'update_prices')
    return JsonResponse({'result': output, 'success': success})


@csrf_exempt
@require_POST
def run_update_dividends(request):
    if not _verify_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    output, success = _run_job('update_dividends', 'update_dividends')
    return JsonResponse({'result': output, 'success': success})


@csrf_exempt
@require_POST
def run_process_notifications(request):
    if not _verify_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    output, success = _run_job('process_notifications', 'process_notifications')
    return JsonResponse({'result': output, 'success': success})
