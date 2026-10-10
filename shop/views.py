import json
import os
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from .models import Product
from .services import place_order
from . import observability as obs

SCENARIOS = {'normal', 'backend-error', 'frontend-error', 'slow'}
DEMO_USERS = {'demo-user-1', 'demo-user-2', 'demo-user-3'}

@require_GET
@ensure_csrf_cookie
def index(request):
    config = obs.browser_config()
    config['fixFrontend'] = os.getenv('DEMO_FIX_FRONTEND', '0') == '1'
    return render(request, 'shop/index.html', {'products': Product.objects.order_by('id'), 'sentry_config': config})

@require_GET
def health(request):
    return JsonResponse({'ok': True})

@require_POST
def checkout(request):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError('Expected a JSON object.')
        product_id = int(data['productId'])
        quantity = int(data['quantity'])
        scenario = str(data.get('scenario', 'normal'))
        user_id = str(data.get('userId', 'demo-user-1'))
        coupon_code = str(data.get('coupon', '')).strip().upper()
        if not 1 <= quantity <= 10 or scenario not in SCENARIOS or user_id not in DEMO_USERS or len(coupon_code) > 30:
            raise ValueError('Invalid checkout input.')
        if not Product.objects.filter(pk=product_id).exists():
            raise ValueError('Product not found.')
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'message': 'Please check the checkout input.'}, status=400)

    obs.checkout_context(user_id, scenario, quantity)
    obs.breadcrumb('Checkout submitted', scenario=scenario, quantity=quantity)
    # Force one repeatable backend bug, without changing the visible coupon field.
    code = 'MISSING' if scenario == 'backend-error' else coupon_code
    try:
        order = place_order(product_id, quantity, code, user_id, scenario)
    except ValueError as error:
        # Expected validation errors are handled. Unexpected exceptions propagate
        # to DjangoIntegration rather than being captured twice.
        return JsonResponse({'message': str(error)}, status=400)
    return JsonResponse({'reference': order.reference, 'total': str(order.total)}, status=201)

def server_error(request):
    return JsonResponse({'message': 'We could not place your order. Please try again.', 'eventId': obs.last_event_id()}, status=500)
