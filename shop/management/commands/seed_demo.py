from decimal import Decimal
from django.core.management.base import BaseCommand
from shop.models import Coupon, Order, Product

class Command(BaseCommand):
    help = 'Create synthetic catalog/coupon data; --reset-orders clears demo orders.'
    def add_arguments(self, parser):
        parser.add_argument('--reset-orders', action='store_true')
    def handle(self, *args, **options):
        Product.objects.update_or_create(id=1, defaults={'name': 'Mechanical Keyboard', 'price': Decimal('79.00')})
        Product.objects.update_or_create(id=2, defaults={'name': 'Wireless Mouse', 'price': Decimal('29.00')})
        Coupon.objects.update_or_create(code='SAVE10', defaults={'amount': Decimal('10.00')})
        if options['reset_orders']:
            Order.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Synthetic catalog ready. Coupon: SAVE10.'))
