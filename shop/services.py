import os
import time
import uuid
from decimal import Decimal
from django.db import transaction
from .models import Coupon, Order, Product
from . import observability as obs

def get_discount(code):
    if not code:
        return Decimal('0.00')
    coupon = Coupon.objects.filter(code=code).first()
    if os.getenv('DEMO_FIX_DISCOUNT', '0') == '1' and coupon is None:
        raise ValueError('This discount code is not valid.')
    # INTENTIONAL BUG: an unknown code returns None. The fix is the guard above.
    return coupon.amount

def calculate_shipping(scenario):
    if scenario == 'slow' and os.getenv('DEMO_FIX_SHIPPING', '0') != '1':
        # A controlled external-service delay, not a database-performance claim.
        time.sleep(float(os.getenv('DEMO_SLOW_SECONDS', '2.5')))
    return Decimal('4.50')

def place_order(product_id, quantity, coupon_code, user_id, scenario):
    with obs.span('inventory.check', **{'cart.quantity': quantity}):
        product = Product.objects.get(pk=product_id)
        subtotal = product.price * quantity
    with obs.span('discount.lookup'):
        discount = get_discount(coupon_code)
    with obs.span('shipping.calculate', **{'demo.scenario': scenario}):
        shipping = calculate_shipping(scenario)
    total = max(Decimal('0.00'), subtotal - discount) + shipping
    with obs.span('order.save'):
        with transaction.atomic():
            order = Order.objects.create(reference='DEMO-' + uuid.uuid4().hex[:10], product=product, quantity=quantity, demo_user=user_id, total=total)
    obs.breadcrumb('Order saved', order_reference=order.reference)
    return order
