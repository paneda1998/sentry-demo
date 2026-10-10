# Presenter Runbook

## Outcome

The audience should leave knowing how to capture a Django exception, read its context, revisit a browser experience, and identify a slow operation in a trace. Keep using the same checkout story throughout. Explain how each piece of evidence changes the next debugging decision.

## Before the webinar

1. Install dependencies, migrate, and seed the app. Rehearse each checkpoint using your tenant. Use the pinned versions in this package.
2. Put the DSN in `.env`. It is not needed in the slide deck. Keep `.env` out of any distributed copy and keep administrative tokens off the screen.
3. Verify a Django error, a frontend error, a replay, and a browser-to-Django trace appear in the tenant. If you use separate projects, select both when viewing the trace.
4. Confirm the tenant supports the SDK payloads, Replay, and tracing, and has available quota. Use `environment:webinar` and release `checkout-demo@1.0.0` to find the rehearsal data.
5. Keep browser developer tools open to Network and Console. Prepare code tabs for `observability.py`, `services.py`, `sentry-browser.js`, and `checkout.js`.
6. Prepare screenshots or a short recording from your own successful rehearsal. Capture one error with context, one replay, and one slow trace. These are your fallback if ingestion is delayed.
7. Reset synthetic orders. Run `python scripts/checkpoint.py off`, restart Django, and hard-refresh the page. Keep the five English slides ready.

## Timing

| Webinar minute | Segment | Checkpoint |
|---|---|---|
| 00–15 | Five-slide introduction | App ready, Sentry off |
| 15–25 | Initial app and connection | `errors` |
| 25–40 | Django exception and context | `context` |
| 40–50 | Browser error and Replay | `replay` |
| 50–70 | Slow checkout and spans | `tracing` |
| 70–75 | Fixes and second run | `tracing --fixed` |
| 75–80 | Recap and pilot suggestion | Revisit slide 5 |
| 80–90 | Questions | Use collected chat questions |

The checkpoints are recovery tools. For the main presentation, walk through the corresponding code and explain what you add. Avoid spending live time installing packages or creating the database schema.

## 15–25: Initial app and connection

**Actions**

1. Show normal checkout. Select Keyboard, quantity 1, apply `SAVE10`. Confirm the estimated total is $73.50. Place the order and show the successful response.
2. Select Backend error and place the order. Show the generic failure message. Ask: “What would we need to investigate this if it happened only for one user?”
3. Open `config/settings.py` and the initial `shop/observability.py`. Explain that the hooks currently do nothing.
4. Add the reference Python initialization in `shop/observability.py`. The key lines are:

```python
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn=os.environ['SENTRY_DSN'],
    integrations=[DjangoIntegration()],
    environment='webinar',
    release='checkout-demo@1.0.0',
    send_default_pii=False,
    traces_sample_rate=0.0,
)
```

The complete reference includes data scrubbing and staged settings. Use it for rehearsal rather than replacing it with this abbreviated teaching snippet.

5. Show how the template loads the locally bundled browser SDK before the checkout code. Add browser `Sentry.init` from the reference file, initially with tracing/Replay disabled.
6. Recovery shortcut: `python scripts/checkpoint.py errors`. Restart Django and hard-refresh. Trigger Backend error again.

**Expected evidence**

HTTP 500, a Python `AttributeError`, and a stack frame for `get_discount` in `shop/services.py`. Open the issue from the correct project and environment. Allow time for ingestion; do not promise immediate appearance.

**Suggested narration**

“Django returns a safe message to the user, while the SDK records the unexpected exception. We can inspect the failing call stack without exposing the debug page to the user.”

## 25–40: Error evidence, grouping, and context

**Actions**

1. Trigger the same backend error twice more. Refresh the issue and distinguish individual events from the issue grouping. Counts may update asynchronously.
2. Inspect the exception, stack frames, and release. Show `coupon = ...first()` returning `None`, followed by `coupon.amount`.
3. In the reference adapter, show `checkout_context` and `breadcrumb`. Explain the synthetic ID, tags, and context you deliberately record:

```python
sentry_sdk.set_user({'id': 'demo-user-1'})
sentry_sdk.set_tag('demo.scenario', 'backend-error')
sentry_sdk.set_context('checkout', {'quantity': 1, 'flow': 'place-order'})
sentry_sdk.add_breadcrumb(
    category='checkout', message='Checkout submitted', level='info',
    data={'quantity': 1, 'scenario': 'backend-error'},
)
```

4. Recovery shortcut: `python scripts/checkpoint.py context`. Restart and reload.
5. Trigger Backend error as demo-user-1, then demo-user-2. Inspect the new events' User, Tags, Contexts, and Breadcrumbs. Existing events will not gain this context retroactively.
6. Ask: “Does the most frequent issue always deserve the first fix?” Explain the importance of affected users, the checkout flow, severity, and versions alongside event count.

**Expected evidence**

New events carry synthetic user IDs, `demo.scenario:backend-error`, `app.layer:django`, checkout quantity, the custom Checkout submitted breadcrumb, and release `checkout-demo@1.0.0`.

**Suggested narration**

“The failure is now connected to a specific attempt. The context narrows our investigation. It also helps us assess the impact, although these user counts describe captured, identified users rather than every person who may have encountered the problem.”

**Keep the investigation honest**

The stack frame identifies the failing expression. It does not by itself explain why the coupon was missing. The deliberate scenario makes this cause known for teaching. In a real app, investigate the request and data assumptions too.

## 40–50: Browser error and Replay

**Actions**

1. Show `Sentry.replayIntegration` in `reference/sentry-browser.js`. Explain masking and why the SDK runs in the browser even though the server uses Django.
2. Recovery shortcut: `python scripts/checkpoint.py replay`. Restart, hard-refresh, and use a fresh browser session if needed.
3. Select demo-user-2, change the quantity, apply `SAVE10`, then select Frontend error and click Place order.
4. Show the unhandled browser error in Console. Open the browser error event in Sentry and follow its linked Replay if available.
5. Rewind to the interactions before the error. Inspect clicks, interface state, and the error timing. Compare the custom breadcrumbs with the replayed path.
6. Explain `formatShippingQuote(null)` and the unchecked `.toFixed()` call. Show that this case fails before `fetch`, so there is no checkout POST for this attempt.

**Expected evidence**

A browser `TypeError` with the `formatShippingQuote` frame in the unminified `checkout.js`, the synthetic user ID, checkout breadcrumbs, and a recorded browser session if delivery and tenant support are working.

**Suggested narration**

“The stack trace shows where the JavaScript failed. Replay lets us revisit the interface and the sequence of interactions around that failure. It reconstructs the page from DOM changes and interactions; it is not a video of the entire desktop.”

**Important distinction**

Use the browser error for the direct error-to-Replay exercise. Do not claim that every Django exception automatically has a linked browser recording. Inputs remain masked. The app selectively unmasks explicit static/synthetic text to make the recording legible.

## 50–70: Slow checkout and spans

**Actions**

1. Select Normal checkout and clear the coupon by applying an empty value. Place an order as a baseline.
2. Select Slow shipping and place another order. Observe the spinner/message and roughly 2.5-second extra delay. The order still succeeds.
3. Ask: “We know it is slow. Which operation should we investigate?”
4. Show `traces_sample_rate` for Python and `browserTracingIntegration`, `tracesSampleRate`, and `tracePropagationTargets` for the browser. Explain the deliberate 100% sampling for a short demo.
5. Show the timed business operations in `shop/services.py`, and the reference span helper:

```python
with sentry_sdk.start_span(op='function', name='shipping.calculate') as span:
    span.set_data('demo.scenario', 'slow')
    shipping = calculate_shipping('slow')
```

The complete reference uses a context manager adapter so the same business code works before and after initialization. DjangoIntegration creates the server request transaction; the custom spans sit within it.

6. Recovery shortcut: `python scripts/checkpoint.py tracing`. Restart and hard-refresh.
7. Trigger a new normal checkout and a new slow checkout. These new attempts should produce traces; old attempts without tracing will not gain traces.
8. In Network, inspect the checkout request's `sentry-trace` and `baggage` headers. The same-origin request goes straight to Django, so there is no cross-origin CORS exercise.
9. In Sentry's trace view, locate `checkout.submit`, the browser HTTP request, the Django request, and custom spans `inventory.check`, `discount.lookup`, `shipping.calculate`, and `order.save`. Find the roughly 2.5-second shipping span in the slow run.
10. Compare normal and slow traces. Do not add all nested span durations together to calculate total request duration.

**Expected evidence**

A connected browser/Django execution path with a long `shipping.calculate` span in the slow scenario. Database activity can appear under the corresponding business operation. Rendering and ingestion latency can change when the UI updates.

**Suggested narration**

“The trace tells us which timed operation deserves attention. In this teaching app, we deliberately injected a provider wait inside shipping calculation. In a real service, a long span identifies the next investigation target, but it does not alone prove why that operation is slow.”

## 70–75: Fix and check again

**Actions**

1. Show the missing-coupon guard in `get_discount`. The corrected path returns a validation error instead of raising an unexpected exception.
2. Show the null guard in `formatShippingQuote`. It displays Shipping quote unavailable and stops checkout safely.
3. Show how `DEMO_FIX_SHIPPING` removes the deliberate provider wait. Explain that this is a controlled before/after illustration.
4. Run `python scripts/checkpoint.py tracing --fixed`. Restart and hard-refresh. Release now becomes `checkout-demo@1.0.1`.
5. Repeat all three scenarios. Expected: Backend error returns HTTP 400 with a validation message; Frontend error shows a safe unavailable-quote message; Slow shipping succeeds without the injected wait.
6. Trigger one normal order as a positive check and compare its new shipping span with the old slow run.

**Suggested narration**

“We have changed the behavior and executed the same paths again. The validation failure is expected, the browser handles its missing data, and the artificial wait is gone. This verifies these specific paths. It does not prove the whole application is bug-free.”

Do not claim the Sentry issue will automatically close, or that no new event in the UI immediately proves a fix. Check the actual response and browser behavior, then inspect recorded new traces. You can manually mark an issue resolved as a separate workflow if time permits.

## 75–90: Recap and questions

Revisit slide 5. Recap Error for the failing execution and context, Replay for the browser experience, and Trace/Spans for operation timing. Invite the audience to run a pilot on one important flow in their own application.

For a CTO: “Can the team collect enough evidence to assess user impact and decide what to investigate next?”

For a developer: “Can you capture one controlled failure, explain its context, and locate a slow operation?”

Use the last 10 minutes for questions collected in chat. Defer platform-specific setup details you cannot verify to the documentation for the relevant SDK.

## Recovery plan

| Symptom | First checks | Recovery during the webinar |
|---|---|---|
| No errors in Sentry | Stage, DSN, project, environment filter, network, ingestion quota | Show your own rehearsed error screenshot; continue reading the source and Console |
| Browser SDK missing | `/static/shop/vendor/sentry-11.4.0.min.js`, `--insecure`, Console | Restart with the documented command and hard-refresh; SDK bundle is local |
| No Replay | Browser checkpoint, recording rates, fresh session, browser storage, tenant support/quota | Use a recording from rehearsal; continue the browser-error investigation |
| Masked form inputs | Expected privacy behavior | Explain the masking; use visible static labels and browser breadcrumbs |
| Trace split between browser and server | Tracing stage, incoming headers, project selection, tenant compatibility | Inspect the Django trace and custom spans on their own; explain what is missing |
| Trace not yet visible | Wait for delivery, check filters and time range | Use the rehearsed slow trace; do not repeatedly generate large volumes |
| Changed settings have no effect | Process restart, hard-refresh, exported env variables | Run the desired checkpoint, restart Django, reload the page |
| App state is confusing | Selected scenario, synthetic user, applied coupon, fix flags | Reset page; run checkpoint again. Clear synthetic orders if needed |

Local code and tests were validated without your tenant credentials. Complete the tenant rehearsal before presenting. The kit does not include fabricated screenshots or replays claiming to come from your tenant.
