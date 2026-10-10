(() => {
  const byId = (id) => document.getElementById(id);
  const config = JSON.parse(byId('sentry-config').textContent);
  const obs = window.demoObservability;
  let appliedCoupon = '';
  function updateTotal() {
    const price = Number(byId('product').selectedOptions[0].dataset.price);
    const subtotal = price * Number(byId('quantity').value);
    const discount = appliedCoupon === 'SAVE10' ? 10 : 0;
    byId('total').textContent = '$' + (Math.max(0, subtotal - discount) + 4.5).toFixed(2);
  }
  byId('product').addEventListener('change', updateTotal);
  byId('quantity').addEventListener('input', updateTotal);
  byId('apply-coupon').addEventListener('click', () => {
    appliedCoupon = byId('coupon').value.trim().toUpperCase();
    byId('coupon-status').textContent = appliedCoupon === 'SAVE10' ? 'Discount applied.' : (appliedCoupon ? 'Code will be checked at checkout.' : 'No discount applied.');
    obs.breadcrumb('Discount applied', {has_code: Boolean(appliedCoupon)});
    updateTotal();
  });
  byId('demo-user').addEventListener('change', () => obs.configureUser(byId('demo-user').value));
  byId('scenario').addEventListener('change', () => { byId('status').textContent = 'Ready when you are.'; });
  byId('reset-session').addEventListener('click', () => location.reload());
  obs.configureUser(byId('demo-user').value);
  byId('sdk-state').textContent = config.enabled ? 'Sentry stage: ' + config.stage : 'Sentry is off. This is the starting checkpoint.';

  function formatShippingQuote(quote) {
    // INTENTIONAL BUG: frontend-error supplies null. The fix checks the value.
    if (config.fixFrontend && quote == null) return 'Shipping quote unavailable.';
    return '$' + quote.toFixed(2);
  }
  async function submitCheckout() {
    const scenario = byId('scenario').value;
    obs.breadcrumb('Place order clicked', {scenario});
    if (scenario === 'frontend-error') {
      byId('status').textContent = 'Preparing your shipping quote…';
      byId('status').textContent = formatShippingQuote(null);
      return;
    }
    const button = byId('place-order');
    button.disabled = true;
    byId('status').textContent = 'Placing your order…';
    try {
      const response = await fetch('/api/checkout/', {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value},
        body: JSON.stringify({productId: Number(byId('product').value), quantity: Number(byId('quantity').value), coupon: appliedCoupon, userId: byId('demo-user').value, scenario}),
      });
      const data = await response.json();
      if (!response.ok) {
        // Server exception is captured by Django. Show its message without
        // manufacturing a second browser exception for the same failure.
        byId('status').textContent = data.message + (data.eventId ? ' Reference: ' + data.eventId : '');
        return;
      }
      byId('status').textContent = 'Order ' + data.reference + ' placed. Total: $' + data.total;
    } catch (error) {
      byId('status').textContent = 'The order request failed. Please try again.';
      throw error; // Browser SDK captures this unhandled rejection if connected.
    } finally { button.disabled = false; }
  }
  byId('checkout-form').addEventListener('submit', (event) => {
    event.preventDefault();
    // Do not catch this promise: frontend-error must reach the browser SDK.
    obs.runCheckout(submitCheckout);
  });
  updateTotal();
})();
