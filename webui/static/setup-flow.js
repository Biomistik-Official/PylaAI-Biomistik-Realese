(function (root) {
  'use strict';
  const routes = ['#setup-device', '#setup-account', '#setup-brawlers', '#setup-review'];
  const flow = {
    routes,
    stepFor(hash) { return !hash ? 0 : routes.indexOf(hash); },
    next(step, context) {
      if (step === 0 && !context.device) throw new Error('Выбери подключённый эмулятор.');
      if (step === 2 && !context.queue) throw new Error('Добавь хотя бы одного бойца в очередь.');
      return routes[step + 1] || null;
    },
    canStart(context) { return Boolean(context.device && context.queue); }
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = flow;
  else root.PylaSetup = flow;
})(globalThis);
