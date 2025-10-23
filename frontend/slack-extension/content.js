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

  async function waitForToField(timeoutMs = 8000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const el =
        document.querySelector('input[aria-label^="To"], input[placeholder*="To"], [data-qa="dm-composer-recipient-input"] input') ||
        document.querySelector('[role="combobox"] input');
      if (el) return el;
      await new Promise(r => setTimeout(r, 300));
    }
    return null;
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
    return false;
  }

  function insertIntoInput(el, text) {
    try {
      el.focus();
      const ok = document.execCommand('insertText', false, text);
      if (ok) return true;
    } catch {}
    try {
      el.focus();
      el.value = text;
      el.dispatchEvent(new InputEvent('input', { bubbles: true, data: text }));
      return true;
    } catch {}
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

  async function run() {
    const { user, msg } = readPayload();
    if (!msg) return; // nothing to do

    // Open a new message composer and paste the Slack ID into the "To" field first
    try {
      if (user) {
        await openNewMessageUI();
        const toInput = await waitForToField();
        if (toInput) {
          insertIntoInput(toInput, user);
          await new Promise(r => setTimeout(r, 300));
          const enter = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
          toInput.dispatchEvent(enter);
          await new Promise(r => setTimeout(r, 600));
        } else {
          // Fallback: try clicking the profile "Message" button if present
          const btn = document.querySelector('button[aria-label^="Message"]') || document.querySelector('button:has(svg[aria-label="Message"])');
          if (btn) {
            btn.click();
            await new Promise(r => setTimeout(r, 800));
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
        const sendEv = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
        composer.dispatchEvent(sendEv);
      }
    } catch {}
  }

  // Run after a short delay to let Slack boot
  setTimeout(run, 1500);
})();


