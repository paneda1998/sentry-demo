"""Install/remove the reference hooks and update non-secret demo flags."""
import argparse
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('stage', choices=['off', 'errors', 'context', 'replay', 'tracing'])
parser.add_argument('--fixed', action='store_true', help='Enable all three fixes and release 1.0.1')
args = parser.parse_args()
if args.stage != 'off':
    shutil.copy2(ROOT / 'reference/observability.py', ROOT / 'shop/observability.py')
    shutil.copy2(ROOT / 'reference/sentry-browser.js', ROOT / 'shop/static/shop/sentry-browser.js')
env_path = ROOT / '.env'
content = env_path.read_text() if env_path.exists() else (ROOT / '.env.example').read_text()
updates = {'DEMO_STAGE': args.stage, 'DEMO_FIX_DISCOUNT': int(args.fixed), 'DEMO_FIX_FRONTEND': int(args.fixed), 'DEMO_FIX_SHIPPING': int(args.fixed), 'SENTRY_RELEASE': 'checkout-demo@1.0.1' if args.fixed else 'checkout-demo@1.0.0'}
for key, value in updates.items():
    line = f'{key}={value}'
    if re.search(rf'^{key}=.*$', content, flags=re.M):
        content = re.sub(rf'^{key}=.*$', line, content, flags=re.M)
    else:
        content += '\n' + line + '\n'
env_path.write_text(content)
print(f'Checkpoint: {args.stage}; fixes: {args.fixed}. Restart Django and hard-refresh the browser.')
