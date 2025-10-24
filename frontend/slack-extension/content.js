(function () {
  function readPayload() {
    try {
      const url = new URL(window.location.href);
      const params = new URLSearchParams(url.search);
      const fromHashUser = params.get('aci_user') || '';
      const fromHashMsg = params.get('aci_msg') || '';
      const fromSSUser = sessionStorage.getItem('aci_user') || '';
      const fromSSMsg = sessionStorage.getItem('aci_msg') || '';
      const user = fromHashUser || fromSSUser;
      const msg = fromHashMsg || fromSSMsg;
      return { user, msg };
    } catch (e) {
      return { user: '', msg: '' };
    }
  }

  async function waitForComposer(timeoutMs = 15000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      // Slack message composer is a contenteditable div with role="textbox"
      const el = document.querySelector('[role="textbox"][contenteditable="true"]');
      if (el) return el;
      await new Promise(r => setTimeout(r, 300));
    }
    return null;
  }

  async function waitForVisible(timeoutMs = 20000) {
    if (document.visibilityState === 'visible') return true;
    let resolved = false;
    const onVis = () => {
      if (document.visibilityState === 'visible') {
        resolved = true;
        document.removeEventListener('visibilitychange', onVis);
      }
    };
    document.addEventListener('visibilitychange', onVis);
    const started = Date.now();
    while (!resolved && Date.now() - started < timeoutMs) {
      await new Promise(r => setTimeout(r, 300));
      if (document.visibilityState === 'visible') {
        resolved = true;
        break;
      }
    }
    try { document.removeEventListener('visibilitychange', onVis); } catch {}
    return resolved;
  }

  async function waitForToField(timeoutMs = 8000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const el =
        document.querySelector('input[aria-label^="To"], input[placeholder*="To"], [data-qa="dm-composer-recipient-input"] input') ||
        document.querySelector('[role="combobox"] input') ||
        document.querySelector('div[role="dialog"] [role="combobox"][contenteditable="true"]') ||
        document.querySelector('[data-qa="dm-composer-recipient-input"] [contenteditable="true"]') ||
        document.querySelector('div[aria-label^="To"][contenteditable="true"]');
      if (el) return el;
      await new Promise(r => setTimeout(r, 300));
    }
    return null;
  }

  function getRecipientContainer() {
    return (
      document.querySelector('[data-qa="dm-composer-recipient-input"]') ||
      document.querySelector('div[aria-label^="To"]') ||
      document.querySelector('[role="dialog"] [aria-label^="To"]') ||
      document.querySelector('[role="combobox"]')
    );
  }

  async function waitForRecipientResolved(timeoutMs = 4000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const c = getRecipientContainer();
      if (c) {
        const pill = c.querySelector('[data-qa*="pill"], [class*="pill"], [class*="Pill"], [data-qa*="entity"], [data-qa*="selected_user"]');
        if (pill) return true;
      }
      await new Promise(r => setTimeout(r, 200));
    }
    return false;
  }

  async function openNewMessageUI() {
    // Try top nav "New message" button
    const selectors = [
      'button[data-qa="top_nav_composer_button"]',
      'button[aria-label="New message"]',
      'button[aria-label^="New message"]',
      'a[aria-label^="New message"]'
    ];
    for (const sel of selectors) {
      const btn = document.querySelector(sel);
      if (btn) {
        btn.click();
        await new Promise(r => setTimeout(r, 600));
        return true;
      }
    }
    // Try keyboard shortcuts for Compose/New message
    try {
      const isMac = navigator.platform.includes('Mac');
      // Plain 'n' sometimes opens compose
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'n', bubbles: true }));
      await new Promise(r => setTimeout(r, 300));
      // Ctrl/Cmd+N
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'n', ctrlKey: !isMac, metaKey: isMac, bubbles: true }));
      await new Promise(r => setTimeout(r, 500));
    } catch {}
    return false;
  }

  function focusToField() {
    const toSel = 'input[aria-label^="To"], input[placeholder*="To"], [data-qa="dm-composer-recipient-input"] input, [role="combobox"] input';
    const el = document.querySelector(toSel);
    if (el) {
      try { el.click(); } catch {}
      try { el.focus(); } catch {}
      return el;
    }
    return null;
  }

  function insertIntoInput(el, text) {
    try {
      el.focus();
      const ok = document.execCommand('insertText', false, text);
      if (ok) return true;
    } catch {}
    try {
      el.focus();
      // Ensure React sees the value change
      const proto = window.HTMLInputElement && window.HTMLInputElement.prototype;
      const setter = proto && Object.getOwnPropertyDescriptor(proto, 'value') && Object.getOwnPropertyDescriptor(proto, 'value').set;
      if (setter) {
        setter.call(el, text);
      } else {
        el.value = text;
      }
      el.dispatchEvent(new Event('change', { bubbles: true }));
      el.dispatchEvent(new InputEvent('input', { bubbles: true, data: text }));
      return true;
    } catch {}
    return false;
  }

  function insertIntoField(el, text) {
    if (!el) return false;
    const isContentEditable = el.getAttribute && el.getAttribute('contenteditable') === 'true';
    if (isContentEditable) {
      return insertIntoComposer(el, text);
    }
    return insertIntoInput(el, text);
  }

  function simulatePasteIntoField(el, text) {
    if (!el) return false;
    try {
      // Prepare clipboard as a fallback for user-triggered paste behavior
      const ta = document.createElement('textarea');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    } catch {}
    try {
      el.focus();
      // Clear existing
      if (el.getAttribute && el.getAttribute('contenteditable') === 'true') {
        el.textContent = '';
      } else if ('value' in el) {
        const proto = window.HTMLInputElement && window.HTMLInputElement.prototype;
        const setter = proto && Object.getOwnPropertyDescriptor(proto, 'value') && Object.getOwnPropertyDescriptor(proto, 'value').set;
        if (setter) {
          setter.call(el, '');
        } else {
          el.value = '';
        }
      }
      // Try to signal a paste to Slack's React handlers
      let pasteEv;
      try {
        const dt = new DataTransfer();
        dt.setData('text/plain', text);
        pasteEv = new ClipboardEvent('paste', { bubbles: true, clipboardData: dt });
      } catch {}
      const beforeInputEv = new InputEvent('beforeinput', { bubbles: true, data: text });
      try { Object.defineProperty(beforeInputEv, 'inputType', { value: 'insertFromPaste' }); } catch {}
      const inputEv = new InputEvent('input', { bubbles: true, data: text });
      try { Object.defineProperty(inputEv, 'inputType', { value: 'insertFromPaste' }); } catch {}
      if (el.getAttribute && el.getAttribute('contenteditable') === 'true') {
        // For contenteditable, insert as if pasted
        const ok = document.execCommand('insertText', false, text);
        if (!ok) {
          el.textContent = text;
        }
        if (pasteEv) el.dispatchEvent(pasteEv);
        el.dispatchEvent(beforeInputEv);
        el.dispatchEvent(inputEv);
      } else if ('value' in el) {
        const proto = window.HTMLInputElement && window.HTMLInputElement.prototype;
        const setter = proto && Object.getOwnPropertyDescriptor(proto, 'value') && Object.getOwnPropertyDescriptor(proto, 'value').set;
        if (setter) {
          setter.call(el, text);
        } else {
          el.value = text;
        }
        if (pasteEv) el.dispatchEvent(pasteEv);
        el.dispatchEvent(beforeInputEv);
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(inputEv);
      }
      return true;
    } catch {}
    // Fallback to normal insertion
    return insertIntoField(el, text);
  }

  function mouseClickEl(el) {
    try {
      el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
    } catch {}
    try {
      const rect = el.getBoundingClientRect();
      const x = Math.floor(rect.left + Math.min(24, Math.max(5, rect.width * 0.2)));
      const y = Math.floor(rect.top + rect.height / 2);
      const opts = { bubbles: true, cancelable: true, clientX: x, clientY: y, view: window };
      el.dispatchEvent(new MouseEvent('mousemove', opts));
      el.dispatchEvent(new MouseEvent('mousedown', opts));
      el.dispatchEvent(new MouseEvent('mouseup', opts));
      el.dispatchEvent(new MouseEvent('click', opts));
      return true;
    } catch {}
    try { el.click(); return true; } catch {}
    return false;
  }

  async function clickToArea() {
    const containers = [
      document.querySelector('[data-qa="dm-composer-recipient-input"]'),
      document.querySelector('div[aria-label^="To"]'),
      document.querySelector('[role="dialog"] [aria-label^="To"]'),
      document.querySelector('[role="combobox"]'),
      document.querySelector('button[aria-label^="To"], button[aria-label^="Add people"]'),
    ].filter(Boolean);
    for (const c of containers) {
      if (mouseClickEl(c)) {
        await new Promise(r => setTimeout(r, 150));
        return true;
      }
    }
    // Last resort: click the To input itself if present
    const input = focusToField() || await waitForToField(2000);
    if (input) {
      return mouseClickEl(input);
    }
    return false;
  }

  function setCaretToEnd(el) {
    try {
      const range = document.createRange();
      range.selectNodeContents(el);
      range.collapse(false);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
    } catch {}
  }

  function insertIntoComposer(el, msg) {
    try {
      setCaretToEnd(el);
      // Try execCommand path first
      const ok = document.execCommand('insertText', false, msg);
      if (ok) return true;
    } catch {}
    // Fallback: set textContent and dispatch input event so React sees the change
    try {
      el.focus();
      el.textContent = msg;
      el.dispatchEvent(new InputEvent('input', { bubbles: true, data: msg }));
      return true;
    } catch {}
    return false;
  }

  async function waitForSendButton(timeoutMs = 5000) {
    const start = Date.now();
    const selectors = [
      'button[data-qa="texty_send_button"]',
      'button[aria-label^="Send"]',
      'button[aria-label*="Send message"]',
      'div[data-qa="message_input"] button[data-qa="texty_send_button"]'
    ];
    while (Date.now() - start < timeoutMs) {
      for (const sel of selectors) {
        const btn = document.querySelector(sel);
        if (btn && !btn.disabled && btn.getAttribute('aria-disabled') !== 'true') return btn;
      }
      await new Promise(r => setTimeout(r, 200));
    }
    return null;
  }

  async function trySend(composer) {
    // Prefer clicking the explicit send button if available
    let btn = await waitForSendButton(3000);
    if (btn) {
      // If found but disabled, wait briefly for enable
      const start = Date.now();
      while ((btn.disabled || btn.getAttribute('aria-disabled') === 'true') && Date.now() - start < 3000) {
        await new Promise(r => setTimeout(r, 150));
      }
      try { btn.click(); return true; } catch {}
    }
    // Fallback: dispatch Enter keypress a couple of times
    try {
      const evOptions = { bubbles: true, key: 'Enter', code: 'Enter', keyCode: 13, which: 13 }; 
      composer.dispatchEvent(new KeyboardEvent('keydown', evOptions));
      await new Promise(r => setTimeout(r, 120));
      composer.dispatchEvent(new KeyboardEvent('keypress', evOptions));
      await new Promise(r => setTimeout(r, 120));
      composer.dispatchEvent(new KeyboardEvent('keyup', evOptions));
      return true;
    } catch {}
    return false;
  }

  async function run() {
    const { user, msg } = readPayload();
    if (!msg) return; // nothing to do

    // Ensure the Slack tab is foreground to avoid throttling and missing focus events
    await waitForVisible(20000);

    // Open a new message composer and paste the Slack ID into the "To" field first
    try {
      if (user) {
        // Retry loop to handle slow-loading Slack UI
        for (let attempt = 0; attempt < 3; attempt++) {
          // Try to open composer
          await openNewMessageUI();
          // Explicitly click near the To area to trigger recipient mode
          await clickToArea();
          // Ensure To field is focused
          let toInput = focusToField();
          if (!toInput) {
            toInput = await waitForToField(12000);
          }
          if (toInput) {
            simulatePasteIntoField(toInput, user);
            await new Promise(r => setTimeout(r, 300));
            const enter = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
            toInput.dispatchEvent(enter);
            await waitForRecipientResolved(2000);
            await new Promise(r => setTimeout(r, 500));
            break;
          }
          // Fallbacks: profile Message button or Quick Switcher Ctrl/Cmd+K
          const btn = document.querySelector('button[aria-label^="Message"]') || document.querySelector('button:has(svg[aria-label="Message"])');
          if (btn) {
            btn.click();
            await new Promise(r => setTimeout(r, 800));
          } else {
            const isMac = navigator.platform.includes('Mac');
            const ev = new KeyboardEvent('keydown', { key: 'k', ctrlKey: !isMac, metaKey: isMac, bubbles: true });
            document.dispatchEvent(ev);
            await new Promise(r => setTimeout(r, 500));
            const switcher = document.querySelector('input[placeholder*="Search"], input[aria-label*="Search"]');
            if (switcher) {
              switcher.focus();
              switcher.value = user;
              switcher.dispatchEvent(new Event('input', { bubbles: true }));
              await new Promise(r => setTimeout(r, 500));
              const enter2 = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
              switcher.dispatchEvent(enter2);
              await new Promise(r => setTimeout(r, 900));
            }
          }
        }
      }
    } catch {}

    const composer = await waitForComposer();
    if (!composer) return;
    // Insert text
    try {
      composer.focus();
      const inserted = insertIntoComposer(composer, msg);
      // Only auto-send if we successfully inserted the text
      if (inserted && String(composer.textContent || '').includes(msg)) {
        await trySend(composer);
      }
    } catch {}
  }

  // Run after a short delay to let Slack boot
  setTimeout(run, 1500);
})();


