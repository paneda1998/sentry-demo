# Django Sentry Webinar Starter

A Django checkout application for the 90-minute Sentry webinar. The initial code runs with observability disabled. A reference implementation and staged checkpoints are included for rehearsal and recovery during the live session.

The stack is Python 3.12+, Django 5.2, SQLite, Django templates, and vanilla JavaScript. There is no Node build step. Django uses the Python SDK; browser errors, browser tracing, and Session Replay use the browser JavaScript SDK.

## Start the initial application

From this directory, on macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8000 --insecure
```

On Windows, use `python` instead of `python3`, `.venv\Scripts\activate`, and `copy .env.example .env`.

Open **http://127.0.0.1:8000/**. Keep this exact host throughout rehearsal. `--insecure` is necessary here because `DJANGO_DEBUG=0` and Django's local development server must still serve static assets. This is a local teaching app, not a deployment setup.

Select Mechanical Keyboard, quantity 1, apply `SAVE10`, and place the order. Expected total: **$73.50**. The order is saved in SQLite. There is no payment collection and all identities are synthetic.

## Connect your tenant

Edit `.env` locally:

```dotenv
SENTRY_DSN=your-project-dsn
SENTRY_BROWSER_DSN=
```

If `SENTRY_BROWSER_DSN` is blank, the browser uses the same DSN. One project/DSN is enough for the webinar. If you prefer separate Django and browser projects, provide the second DSN and make sure both projects are selected while investigating distributed traces. A DSN is an ingestion key; no administrative API token is required for these SDK integrations.

Install the reference hooks and enable error collection:

```bash
python scripts/checkpoint.py errors
```

Stop and restart Django. Hard-refresh the browser. You should see `Sentry stage: errors` in Presenter controls. Environment variables already exported in the shell take precedence over `.env`; avoid exporting `DEMO_STAGE` if you want the checkpoint script to control it.

The checkpoint script copies two files into the working application:

- `reference/observability.py` to `shop/observability.py`
- `reference/sentry-browser.js` to `shop/static/shop/sentry-browser.js`

For live teaching, explain and edit these files rather than silently running the checkpoint script. The script is your rehearsal and recovery shortcut.

## Rehearsal checkpoints

| Command | Features | What to demonstrate |
|---|---|---|
| `python scripts/checkpoint.py off` | No SDK collection | Normal checkout and a user's failed attempt |
| `python scripts/checkpoint.py errors` | Python/browser errors | Stack trace and repeated events in an issue |
| `python scripts/checkpoint.py context` | Errors plus explicit context | Synthetic user ID, tags, breadcrumbs, release |
| `python scripts/checkpoint.py replay` | Context plus browser Replay | Frontend error linked to a browser replay |
| `python scripts/checkpoint.py tracing` | All preceding features plus tracing | Browser request and Django custom spans |
| `python scripts/checkpoint.py tracing --fixed` | All features, fixes enabled | Validation instead of a 500, safe browser message, shipping wait removed |

**Restart Django and hard-refresh the browser after every checkpoint.** The restart is required because SDK initialization happens at process startup. Each checkpoint resets the three fix flags and release to a known state unless `--fixed` is supplied. `off` disables the installed reference hooks; it does not delete their code.

## Scenarios

| Presenter selection | Deliberate condition | Expected result |
|---|---|---|
| Normal checkout | Valid product and coupon | HTTP 201, saved order, confirmation |
| Backend error | Unknown coupon, unchecked `None` | HTTP 500, `AttributeError` in `get_discount`, no saved order |
| Frontend error | Missing shipping quote, unchecked `null` | Browser `TypeError` in `formatShippingQuote`, no checkout request |
| Slow shipping | Simulated 2.5-second provider wait | Successful order; `shipping.calculate` is the long custom span |

The backend-error selection forces the missing coupon for repeatability. Independently, entering an unknown coupon in Normal checkout also reaches the bug. The slowdown is an intentional sleep representing a provider wait. SQLite stores real demo orders, but no real shipping service is called.

The fixes are in `shop/services.py` and `shop/static/shop/checkout.js`. Their flags let you reproduce and then remove the problem without maintaining separate app copies. The frontend fix handles an unavailable quote and stops checkout; it does not invent a valid quote. The shipping fix removes the injected delay; it is a teaching comparison, not proof of a production optimization.

## Files to show on screen

| File | Purpose |
|---|---|
| `config/settings.py` | Django config and early SDK bootstrap |
| `shop/observability.py` | Initial no-op hooks, then Python SDK init/context/spans |
| `shop/services.py` | Business flow and the discount/shipping problems |
| `shop/views.py` | Request validation, context, JSON results, generic 500 response |
| `shop/static/shop/sentry-browser.js` | Initial no-op adapter, then browser SDK setup |
| `shop/static/shop/checkout.js` | User interactions, browser error, checkout fetch |
| `shop/templates/shop/index.html` | Local browser SDK and safe JSON configuration |
| `FLOW.md` | Minute-by-minute presenter script and fallback plan |

The no-op hooks are intentional scaffolding. They let the application work at the initial checkpoint and keep the live edits focused on observability rather than building a shop from scratch.

## Tests and reset

```bash
python manage.py check
python manage.py test
python manage.py seed_demo --reset-orders
```

Resetting orders affects only this app's synthetic SQLite orders. It does not delete Sentry events, replays, or issues. Click Reset page to reset the browser form. For a new recording session, use a fresh private browsing session, or clear this site's browser storage during rehearsal.

The tests check order persistence, input validation, CSRF, the backend failure and fix, the shipping wait and fix, and Sentry error/context/trace capture with an in-memory transport. They do not send data to a tenant.

Preparation checks passed: seven Django tests, Django system checks, local HTTP/static serving, and a JavaScript harness checking checkout behavior, the browser error/fix, SDK exports, and stage configuration. Full browser end-to-end Replay capture and delivery to your tenant have not been verified here. Rehearse those with your DSN before the webinar.

## SDK settings and rehearsal limits

- Backend SDK: `sentry-sdk==2.71.0`. Browser SDK: official `11.4.0` error/tracing/replay bundle, stored under `shop/static/shop/vendor/`. Versions are pinned for a repeatable rehearsal, not automatically updated.
- Demo traces and recording sessions use 100% sampling at their respective checkpoints. Use appropriate sampling and quotas for real applications.
- Text is masked by default. Only elements explicitly marked `data-replay-public` expose static or synthetic lab text. Form inputs remain masked, and replay network bodies are disabled.
- The backend does not send request bodies, credentials, cookies, or local variables in error events. It explicitly records only synthetic user IDs and selected checkout metadata.
- Raw exception stack traces identify source lines, but Sentry cannot fetch files from your local machine. For browser line inspection, keep `checkout.js` open locally. It is unminified, so there is no application bundling/source-map exercise in this demo. Source-map uploads for a real minified build are a separate topic.
- Tenant ingestion, Replay support, trace ingestion, quotas, project permissions, network access, and actual UI correlations must be rehearsed with your own DSN. SDK capture tests are not proof of delivery to your tenant.
- A server error does not automatically guarantee a directly linked replay. Use the **frontend-error** case for the error-to-Replay demonstration. Use the **slow** case for browser-to-Django trace propagation.

## Official references

- Django integration: https://docs.sentry.io/platforms/python/integrations/django/
- Python tracing: https://docs.sentry.io/platforms/python/tracing/
- Python distributed tracing: https://docs.sentry.io/platforms/python/tracing/distributed-tracing/
- Browser SDK: https://docs.sentry.io/platforms/javascript/
- Browser tracing: https://docs.sentry.io/platforms/javascript/configuration/integrations/browsertracing/
- Session Replay and official CDN bundle: https://docs.sentry.io/platforms/javascript/session-replay/
- Replay privacy: https://docs.sentry.io/platforms/javascript/session-replay/privacy/

Prepared for the five-slide English introduction. The live flow and code comments are in English.
