import json
import os
from io import BytesIO
from wsgiref.util import setup_testing_defaults
from unittest.mock import patch
import sentry_sdk
from sentry_sdk.transport import Transport
from django.test import Client, TestCase
from django.core.handlers.wsgi import WSGIHandler
from .models import Coupon, Order, Product
from reference import observability as reference

class CheckoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Product.objects.create(id=1, name='Keyboard', price='79.00')
        Coupon.objects.create(code='SAVE10', amount='10.00')

    def post(self, **values):
        payload = {'productId': 1, 'quantity': 1, 'userId': 'demo-user-1', 'scenario': 'normal', 'coupon': ''}
        payload.update(values)
        return self.client.post('/api/checkout/', data=json.dumps(payload), content_type='application/json')

    def test_order_is_saved_and_discount_is_applied(self):
        result = self.post(quantity=2, coupon='SAVE10')
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json()['total'], '152.50')
        self.assertEqual(Order.objects.count(), 1)

    def test_backend_bug_returns_generic_500_and_saves_no_order(self):
        self.client.raise_request_exception = False
        with patch.dict(os.environ, {'DEMO_FIX_DISCOUNT': '0'}):
            result = self.post(scenario='backend-error')
        self.assertEqual(result.status_code, 500)
        self.assertNotIn('Traceback', result.content.decode())
        self.assertEqual(Order.objects.count(), 0)

    def test_discount_fix_returns_validation_error(self):
        with patch.dict(os.environ, {'DEMO_FIX_DISCOUNT': '1'}):
            result = self.post(scenario='backend-error')
        self.assertEqual(result.status_code, 400)
        self.assertIn('not valid', result.json()['message'])
        self.assertEqual(Order.objects.count(), 0)

    def test_invalid_quantity_and_identity_are_rejected(self):
        self.assertEqual(self.post(quantity=0).status_code, 400)
        self.assertEqual(self.post(userId='real-person').status_code, 400)
        self.assertEqual(self.post(productId=999).status_code, 400)

    def test_checkout_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        payload = json.dumps({'productId': 1, 'quantity': 1})
        self.assertEqual(client.post('/api/checkout/', data=payload, content_type='application/json').status_code, 403)
        client.get('/')
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post('/api/checkout/', data=payload, content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code, 201)

    def test_shipping_fix_removes_simulated_wait(self):
        with patch('shop.services.time.sleep') as sleep, patch.dict(os.environ, {'DEMO_FIX_SHIPPING': '0', 'DEMO_SLOW_SECONDS': '0.04'}):
            self.assertEqual(self.post(scenario='slow').status_code, 201)
            sleep.assert_called_once_with(0.04)
        with patch('shop.services.time.sleep') as sleep, patch.dict(os.environ, {'DEMO_FIX_SHIPPING': '1'}):
            self.assertEqual(self.post(scenario='slow').status_code, 201)
            sleep.assert_not_called()

class MemoryTransport(Transport):
    def __init__(self, options):
        super().__init__(options)
        self.items = []
    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.headers.get('type') in {'event', 'transaction'}:
                self.items.append(item.payload.json)

class SentryReferenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Product.objects.create(id=1, name='Keyboard', price='79.00')

    def test_reference_captures_exception_context_and_continues_trace(self):
        # Exercise the real initialization, Django integration, and custom spans.
        # The in-memory transport never sends anything to an external tenant.
        real_init = sentry_sdk.init
        def local_init(**kwargs):
            kwargs['transport'] = MemoryTransport
            return real_init(**kwargs)
        trace_id = '1234567890abcdef1234567890abcdef'
        env = {'DEMO_STAGE': 'tracing', 'SENTRY_DSN': 'https://public@example.invalid/1', 'DEMO_FIX_DISCOUNT': '0', 'DEMO_FIX_SHIPPING': '0', 'DEMO_SLOW_SECONDS': '0.04'}
        with patch.dict(os.environ, env), patch.object(sentry_sdk, 'init', side_effect=local_init):
            reference.bootstrap()
            transport = sentry_sdk.get_client().transport
            def wsgi_post(scenario, user_id='demo-user-1', trace=None):
                # Django's test Client bypasses WSGI instrumentation. Exercise
                # the actual WSGI entry point used by runserver instead.
                body = json.dumps({'productId': 1, 'quantity': 1, 'scenario': scenario, 'userId': user_id}).encode()
                env = {}
                setup_testing_defaults(env)
                env.update({'REQUEST_METHOD': 'POST', 'PATH_INFO': '/api/checkout/', 'SERVER_NAME': 'testserver', 'HTTP_HOST': 'testserver', 'CONTENT_TYPE': 'application/json', 'CONTENT_LENGTH': str(len(body)), 'wsgi.input': BytesIO(body), 'HTTP_COOKIE': 'csrftoken=' + 'a' * 32, 'HTTP_X_CSRFTOKEN': 'a' * 32})
                if trace:
                    env['HTTP_SENTRY_TRACE'] = trace + '-0123456789abcdef-1'
                status = []
                response = WSGIHandler()(env, lambda code, headers: status.append(code))
                list(response)
                response.close()
                return int(status[0].split()[0])
            with patch('shop.views.obs', reference), patch('shop.services.obs', reference):
                self.assertEqual(wsgi_post('backend-error'), 500)
                self.assertEqual(wsgi_post('slow', 'demo-user-2', trace_id), 201)
            sentry_sdk.flush()
            events = [x for x in transport.items if x.get('exception')]
            self.assertTrue(events)
            event = events[-1]
            self.assertEqual(event['user']['id'], 'demo-user-1')
            self.assertEqual(event['tags']['demo.scenario'], 'backend-error')
            self.assertTrue(any(b['message'] == 'Checkout submitted' for b in event['breadcrumbs']['values']))
            self.assertNotIn('headers', event.get('request', {}))
            transactions = [x for x in transport.items if x.get('type') == 'transaction']
            continued = [x for x in transactions if x['contexts']['trace']['trace_id'] == trace_id]
            self.assertTrue(continued, 'Django should continue the incoming browser trace')
            names = [span.get('description', span.get('name')) for span in continued[-1]['spans']]
            self.assertIn('shipping.calculate', names)
            self.assertIn('order.save', names)
            sentry_sdk.get_client().close()
