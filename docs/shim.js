// Minimal stand-in for the Claude dashboard runtime, so the same page code runs on a plain website.
// Datasets are JSON files in data/<id>.json shaped {rows, meta}. Calcs, drawings and links behave as on the dashboard.
(function () {
  const DATASETS = ['team_seasons', 'games', 'team_weeks', 'picks', 'keepers', 'trades', 'pickups', 'drop_regret', 'player_games', 'keeper_options'];
  const sources = {};   // id -> {status, data, message}
  const calcs = {};     // id -> {inputs, fn, cache, key}
  const draws = {};     // name -> fn | {mount, update, unmount}
  const mounted = new WeakMap();
  const onDataFns = [];

  for (const id of DATASETS) sources[id] = { status: 'loading', data: [] };

  function calcValue(id, seen = new Set()) {
    const c = calcs[id];
    if (seen.has(id)) return { status: 'error', data: null, message: 'circular calc' };
    seen.add(id);
    const ins = c.inputs.map((i) => (calcs[i] ? calcValue(i, new Set(seen)) : sources[i] || { status: 'missing', data: [] }));
    const bad = ins.find((r) => r.status !== 'ok');
    if (bad) return { status: bad.status === 'error' ? 'error' : bad.status, data: null };
    const key = ins.map((r) => r.version || 0).join('|');
    if (c.key !== key) {
      try { c.cache = c.fn(...ins.map((r) => r.data)); c.error = null; } catch (e) { c.error = e; console.error('calc', id, e); }
      c.key = key; c.version = (c.version || 0) + 1;
    }
    if (c.error) return { status: 'error', data: null, message: String(c.error) };
    return { status: 'ok', data: c.cache, version: c.version };
  }

  function data(id) {
    if (calcs[id]) return calcValue(id);
    return sources[id] || { status: 'missing', data: [] };
  }

  function visible(el) { return !el.closest('[hidden]'); }

  function runDraw(name) {
    const d = draws[name];
    if (!d) return;
    for (const el of document.querySelectorAll(`[data-draw="${name}"]`)) {
      if (!visible(el)) continue;
      try {
        if (typeof d === 'function') d(el);
        else {
          if (!mounted.has(el)) { el.replaceChildren(); mounted.set(el, d.mount ? d.mount(el) : undefined); }
          if (d.update) d.update(el, mounted.get(el));
        }
      } catch (e) { console.error('draw', name, e); }
    }
  }
  function runAll() {
    for (const fn of onDataFns) { try { fn(); } catch (e) { console.error(e); } }
    for (const name of Object.keys(draws)) runDraw(name);
  }
  let pending = false;
  function schedule() { if (pending) return; pending = true; requestAnimationFrame(() => { pending = false; runAll(); }); }

  window.dash = {
    data,
    calc(id, o) { calcs[id] = { inputs: o.inputs, fn: o.fn }; },
    loader() {},
    draw(name, fn) { if (fn === undefined) { runDraw(name); return; } draws[name] = fn; schedule(); },
    onData(fn) { onDataFns.push(fn); schedule(); },
    refresh() {},
    params() { return {}; }, setParams() {}, resetParams() {},
    setLink(name) { try { history.replaceState(null, '', '#' + name); } catch (e) {} },
    colors: ['var(--um-ink)', 'var(--um-ink-2)', 'var(--color-fg-muted)', 'var(--color-ok)', 'var(--color-bad)'],
  };

  // Load every dataset, then draw.
  for (const id of DATASETS) {
    fetch(`data/${id}.json`, { cache: 'no-cache' })
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then((j) => { sources[id] = { status: 'ok', data: Array.isArray(j) ? j : j.rows, version: 1, meta: j.meta }; schedule(); })
      .catch((e) => { sources[id] = { status: 'error', data: [], message: String(e) }; schedule(); });
  }
  // Redraw when a tab is shown, and when the width changes.
  new MutationObserver((ms) => { if (ms.some((m) => m.target.tagName === 'SECTION')) schedule(); }).observe(document.documentElement, { subtree: true, attributes: true, attributeFilter: ['hidden'] });
  let lastW = window.innerWidth;
  window.addEventListener('resize', () => { if (window.innerWidth !== lastW) { lastW = window.innerWidth; schedule(); } });
  document.addEventListener('DOMContentLoaded', schedule);
})();
