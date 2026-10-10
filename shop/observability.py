"""REFERENCE: copy over shop/observability.py to connect the Python SDK."""
import os
from contextlib import contextmanager
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

STAGES = {'off', 'errors', 'context', 'replay', 'tracing'}

def stage():
    value = os.getenv('DEMO_STAGE', 'off')
    if value not in STAGES:
        raise ValueError('DEMO_STAGE must be off, errors, context, replay, or tracing.')
    return value

def before_send(event, hint):
    # Only synthetic identity is needed in this lab. Scrub request credentials/body.
    request = event.get('request', {})
    for key in ('cookies', 'headers', 'data', 'env', 'query_string'):
        request.pop(key, None)
    user = event.get('user', {})
    event['user'] = {'id': user['id']} if user.get('id', '').startswith('demo-user-') else {}
    return event

def bootstrap():
    if stage() == 'off':
        return
    dsn = os.getenv('SENTRY_DSN', '').strip()
    if not dsn:
        raise ValueError('Set SENTRY_DSN before enabling Sentry.')
    sentry_sdk.init(
        dsn=dsn,
        integrations=[DjangoIntegration(transaction_style='url', middleware_spans=False, signals_spans=False)],
        environment=os.getenv('SENTRY_ENVIRONMENT', 'webinar'),
        release=os.getenv('SENTRY_RELEASE', 'checkout-demo@1.0.0'),
        traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '1.0')) if stage() == 'tracing' else 0.0,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size='never',
        before_send=before_send,
        debug=os.getenv('SENTRY_DEBUG', '0') == '1',
    )

@contextmanager
def span(name, **attributes):
    if stage() != 'tracing':
        yield None
        return
    with sentry_sdk.start_span(op='function', name=name) as current_span:
        for key, value in attributes.items():
            current_span.set_data(key, value)
        yield current_span

def checkout_context(user_id, scenario, quantity):
    if stage() not in {'context', 'replay', 'tracing'}:
        return
    sentry_sdk.set_user({'id': user_id})
    sentry_sdk.set_tag('demo.scenario', scenario)
    sentry_sdk.set_tag('app.layer', 'django')
    sentry_sdk.set_context('checkout', {'quantity': quantity, 'flow': 'place-order'})

def breadcrumb(message, **data):
    if stage() in {'context', 'replay', 'tracing'}:
        sentry_sdk.add_breadcrumb(category='checkout', message=message, level='info', data=data)

def last_event_id():
    return sentry_sdk.last_event_id() if stage() != 'off' else None

def browser_config():
    return {
        'enabled': stage() != 'off', 'stage': stage(),
        'dsn': os.getenv('SENTRY_BROWSER_DSN') or os.getenv('SENTRY_DSN', ''),
        'environment': os.getenv('SENTRY_ENVIRONMENT', 'webinar'),
        'release': os.getenv('SENTRY_RELEASE', 'checkout-demo@1.0.0'),
        'tracesSampleRate': float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '1.0')),
        'replaysSessionSampleRate': float(os.getenv('SENTRY_REPLAYS_SESSION_SAMPLE_RATE', '1.0')),
        'debug': os.getenv('SENTRY_DEBUG', '0') == '1',
    }
