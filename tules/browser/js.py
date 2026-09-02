"""The JavaScript that runs inside the AI chat tab.

Every snippet is sent through ``Runtime.evaluate`` and returns a plain value
(``returnByValue``), so the Python side never holds live object handles: it
re-finds elements by index into ``window.__tules.els``, with sanity checks at
every use. Nothing here touches the page beyond reading the DOM and, when the
user teaches an element, recording what they focused or clicked.
"""

PROBE = r"""
(() => {
  const w = (window.__tules = window.__tules || { els: [] });
  if (w.els.length > 8000) { w.els = w.els.slice(-4000); }
  const keep = (el) => { w.els.push(el); return w.els.length - 1; };
  const attr = (el, n) => (el.getAttribute(n) || '');
  const visible = (el) => {
    if (!el || !el.isConnected) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 6 || r.height < 6) return false;
    const s = getComputedStyle(el);
    return s.visibility !== 'hidden' && s.display !== 'none' && Number(s.opacity) > 0.05;
  };
  const describe = (el) => {
    const r = el.getBoundingClientRect();
    const role = attr(el, 'role');
    return {
      ref: keep(el),
      tag: el.tagName.toLowerCase(),
      id: el.id || '',
      name: attr(el, 'name'),
      classes: Array.prototype.slice.call(el.classList || []),
      placeholder: attr(el, 'placeholder'),
      aria: attr(el, 'aria-label'),
      title: attr(el, 'title'),
      testid: attr(el, 'data-testid') || attr(el, 'data-test') || attr(el, 'data-test-id'),
      role: role,
      kind: el.tagName === 'INPUT' ? (el.type || 'text') : '',
      editable: el.isContentEditable === true,
      text: ((el.value !== undefined && el.value !== null ? el.value : el.innerText) || '').slice(-300),
      visible: visible(el),
      rect: { x: r.x, y: r.y, w: r.width, h: r.height }
    };
  };
  const inputs = [];
  for (const el of document.querySelectorAll('textarea, [contenteditable="true"], [role="textbox"]')) {
    if (!visible(el)) continue;
    const d = describe(el);
    d.kind = el.tagName === 'TEXTAREA' ? 'textarea' : (el.isContentEditable ? 'contenteditable' : d.kind);
    d.kind = el.tagName === 'INPUT' ? d.kind : (d.kind || 'contenteditable');
    inputs.push(d);
  }
  const copies = [];
  for (const el of document.querySelectorAll('button, [role="button"]')) {
    if (!visible(el)) continue;
    const d = describe(el);
    d.label = (d.aria + ' ' + d.testid + ' ' + d.title + ' ' + (el.innerText || '')).trim().toLowerCase().slice(0, 80);
    copies.push(d);
  }
  const firstMatch = (selectors) => {
    for (const sel of selectors) {
      let nodes;
      try { nodes = document.querySelectorAll(sel); } catch (err) { continue; }
      if (nodes.length) return { selector: sel, count: nodes.length,
        len: ((nodes[nodes.length - 1].innerText || '')).trim().length };
    }
    return { selector: null, count: 0, len: 0 };
  };
  const generating = (selectors) => {
    for (const sel of selectors) {
      let nodes;
      try { nodes = document.querySelectorAll(sel); } catch (err) { continue; }
      if (Array.prototype.some.call(nodes, visible)) return sel;
    }
    return null;
  };
  const active = document.activeElement;
  return {
    url: location.href,
    title: document.title,
    inputs: inputs,
    copies: copies,
    response: firstMatch(%RESPONSE_SELECTORS%),
    generating_selector: generating(%GENERATING_SELECTORS%),
    generating: generating(%GENERATING_SELECTORS%) !== null || document.querySelector('[aria-busy="true"]') !== null,
    active: active ? describe(active) : null
  };
})()
"""

BOX_TEXT = r"""
(() => {
  const el = (window.__tules && window.__tules.els || [])[%REF%];
  if (!el || !el.isConnected) return null;
  const text = ((el.value !== undefined && el.value !== null) ? el.value : el.innerText) || '';
  return { len: text.length, head: text.slice(0, 150), tail: text.slice(-150) };
})()
"""

CLEAR_BOX = r"""
(() => {
  const el = (window.__tules && window.__tules.els || [])[%REF%];
  if (!el || !el.isConnected) return { ok: false, reason: 'gone' };
  el.focus();
  if (el.isContentEditable) {
    try {
      document.execCommand('selectAll', false, null);
      document.execCommand('delete', false, null);
    } catch (err) {}
  } else {
    const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value');
    if (setter && setter.set) { setter.set.call(el, ''); }
    else { el.value = ''; }
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }
  return { ok: true };
})()
"""

SUBMISSION_VIEW = r"""
(() => {
  const w = window.__tules || { els: [] };
  const el = w.els[%REF%];
  const boxLen = el && el.isConnected
    ? (((el.value !== undefined && el.value !== null) ? el.value : el.innerText) || '').trim().length
    : -1;
  let responseCount = 0;
  try { responseCount = document.querySelectorAll(%RESPONSE_SELECTOR_JSON%).length; } catch (err) {}
  let generating = document.querySelector('[aria-busy="true"]') !== null;
  try {
    const stop = document.querySelector(%STOP_SELECTOR_JSON%);
    generating = generating || (stop !== null && stop.getBoundingClientRect().height > 4);
  } catch (err) {}
  return { box_len: boxLen, response_count: responseCount, generating: generating };
})()
"""

ELEMENT_BY_SELECTOR = r"""
(() => {
  const w = (window.__tules = window.__tules || { els: [] });
  const keep = (el) => { w.els.push(el); return w.els.length - 1; };
  const attr = (el, n) => (el.getAttribute(n) || '');
  const visible = (el) => {
    if (!el || !el.isConnected) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 6 || r.height < 6) return false;
    const s = getComputedStyle(el);
    return s.visibility !== 'hidden' && s.display !== 'none' && Number(s.opacity) > 0.05;
  };
  let nodes;
  try { nodes = document.querySelectorAll(%SELECTOR_JSON%); } catch (err) { return { error: 'bad selector' }; }
  const matches = Array.prototype.filter.call(nodes, visible);
  if (!matches.length) return { found: 0 };
  const el = matches[matches.length - 1];
  const r = el.getBoundingClientRect();
  return {
    found: nodes.length,
    visible_found: matches.length,
    element: {
      ref: keep(el),
      tag: el.tagName.toLowerCase(),
      id: el.id || '',
      name: attr(el, 'name'),
      classes: Array.prototype.slice.call(el.classList || []),
      placeholder: attr(el, 'placeholder'),
      aria: attr(el, 'aria-label'),
      title: attr(el, 'title'),
      testid: attr(el, 'data-testid') || attr(el, 'data-test') || attr(el, 'data-test-id'),
      role: attr(el, 'role'),
      kind: el.tagName === 'INPUT' ? (el.type || 'text') : '',
      editable: el.isContentEditable === true,
      text: ((el.value !== undefined && el.value !== null ? el.value : el.innerText) || '').slice(-300),
      visible: true,
      rect: { x: r.x, y: r.y, w: r.width, h: r.height }
    }
  };
})()
"""

VERIFY_CANDIDATE = r"""
(() => {
  const w = (window.__tules = window.__tules || { els: [] });
  let nodes;
  try { nodes = document.querySelectorAll(%SELECTOR_JSON%); } catch (err) { return { error: 'bad selector' }; }
  if (!nodes.length) return { found: 0 };
  const el = (window.__tules && window.__tules.els || [])[%REF%];
  for (const node of nodes) { if (node === el) return { found: nodes.length, hit: true }; }
  return { found: nodes.length, hit: false };
})()
"""

TEACH_INPUT_ARM = r"""
(() => {
  const w = (window.__tules = window.__tules || { els: [] });
  if (w.teachFocus) return true;
  w.teachFocus = true;
  w.taughtInput = null;
  document.addEventListener('focusin', (event) => {
    const el = event.target;
    if (!el || !el.tagName) return;
    const tag = el.tagName.toLowerCase();
    const type = (el.type || '').toLowerCase();
    const ok = tag === 'textarea' || el.isContentEditable || attr(el, 'role') === 'textbox'
      || (tag === 'input' && ['text', 'search', ''].indexOf(type) !== -1);
    if (!ok) return;
    const r = el.getBoundingClientRect();
    w.taughtInput = {
      ref: w.els.push(el) - 1,
      tag: tag, id: el.id || '', name: attr(el, 'name'),
      classes: Array.prototype.slice.call(el.classList || []),
      placeholder: attr(el, 'placeholder'), aria: attr(el, 'aria-label'),
      title: attr(el, 'title'),
      testid: attr(el, 'data-testid') || attr(el, 'data-test') || attr(el, 'data-test-id'),
      role: attr(el, 'role'),
      kind: tag === 'TEXTAREA' ? 'textarea' : (el.isContentEditable ? 'contenteditable' : (el.type || 'text')),
      editable: el.isContentEditable === true,
      text: '', visible: r.width > 0,
      rect: { x: r.x, y: r.y, w: r.width, h: r.height }
    };
  }, true);
  return true;
})()
"""

TEACH_COPY_ARM = r"""
(() => {
  const w = (window.__tules = window.__tules || { els: [] });
  if (w.teachClick) return true;
  w.teachClick = true;
  w.taughtCopy = null;
  document.addEventListener('click', (event) => {
    if (w.taughtCopy) return;
    let el = event.target;
    while (el && el.tagName && el.tagName.toLowerCase() !== 'button' && attr(el, 'role') !== 'button') {
      el = el.parentElement;
      if (!el || el === document.body) { el = event.target; break; }
    }
    const r = el.getBoundingClientRect();
    w.taughtCopy = {
      ref: w.els.push(el) - 1,
      tag: el.tagName.toLowerCase(), id: el.id || '', name: attr(el, 'name'),
      classes: Array.prototype.slice.call(el.classList || []),
      placeholder: attr(el, 'placeholder'), aria: attr(el, 'aria-label'),
      title: attr(el, 'title'),
      testid: attr(el, 'data-testid') || attr(el, 'data-test') || attr(el, 'data-test-id'),
      role: attr(el, 'role'),
      kind: '', editable: false, text: ((el.innerText || '') + '').slice(-80),
      visible: r.width > 0,
      rect: { x: r.x, y: r.y, w: r.width, h: r.height }
    };
    w.taughtCopy.label = (w.taughtCopy.aria + ' ' + w.taughtCopy.testid + ' ' + w.taughtCopy.title + ' '
      + w.taughtCopy.text).trim().toLowerCase().slice(0, 80);
  }, true);
  return true;
})()
"""

TEACH_RESULT = "(window.__tules && window.__tules.%NAME%) || null\n"

# A clipboard that lives inside the page: used when the system clipboard cannot
# observe the browser (headless, remote) and by the smoke test.
PAGE_READ_CLIPBOARD = (
	"navigator.clipboard.readText()"
	".then((t) => ({ ok: true, text: t }), (e) => ({ ok: false, error: String(e) }))"
)

PAGE_WRITE_CLIPBOARD = (
	"navigator.clipboard.writeText(%TEXT%)"
	".then(() => ({ ok: true }), (e) => ({ ok: false, error: String(e) }))"
)
