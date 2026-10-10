// REFERENCE: copy over shop/static/shop/sentry-browser.js to connect the browser SDK.
(() => {
  const config = JSON.parse(document.getElementById('sentry-config').textContent);
  const contextEnabled = ['context', 'replay', 'tracing'].includes(config.stage);
  const replayEnabled = ['replay', 'tracing'].includes(config.stage);
  const tracingEnabled = config.stage === 'tracing';
  if (config.enabled && !window.Sentry) {
    throw new Error('The local Sentry browser bundle did not load. Check /static/.');
  }
  if (config.enabled) {
    const integrations = [];
    if (tracingEnabled) integrations.push(Sentry.browserTracingIntegration());
    if (replayEnabled) integrations.push(Sentry.replayIntegration({
      maskAllText: true,
      blockAllMedia: true,
      // Only explicit static/synthetic lab text is revealed. Inputs stay masked.
      unmask: ['[data-replay-public]'],
      networkCaptureBodies: false,
    }));
    Sentry.init({
      dsn: config.dsn,
      environment: config.environment,
      release: config.release,
      integrations,
      tracesSampleRate: tracingEnabled ? config.tracesSampleRate : 0,
      tracePropagationTargets: [/^\/api\//, new RegExp('^' + location.origin.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '/api/')],
      replaysSessionSampleRate: replayEnabled ? config.replaysSessionSampleRate : 0,
      replaysOnErrorSampleRate: replayEnabled ? 1 : 0,
      sendDefaultPii: false,
      debug: config.debug,
      beforeSend(event) {
        if (event.request) { delete event.request.cookies; delete event.request.headers; delete event.request.data; }
        return event;
      },
    });
    Sentry.setTag('app.layer', 'browser');
  }
  window.demoObservability = {
    configureUser(id) { if (config.enabled && contextEnabled) Sentry.setUser({id}); },
    breadcrumb(message, data) {
      if (!config.enabled || !contextEnabled) return;
      Sentry.setTag('demo.scenario', document.getElementById('scenario').value);
      Sentry.addBreadcrumb({category: 'checkout', message, level: 'info', data});
    },
    runCheckout(callback) {
      if (!config.enabled || !tracingEnabled) return callback();
      return Sentry.startSpan({name: 'checkout.submit', op: 'ui.action', forceTransaction: true}, callback);
    },
  };
})();
