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

  async function run() {
    const { user, msg } = readPayload();
    if (!msg) return; // nothing to do

    // If a user ID is provided, try to navigate to the DM search quickly
    // On user_profile page, click the "Message" button to open DM
    try {
      const btn = document.querySelector('button[aria-label^="Message"]') || document.querySelector('button:has(svg[aria-label="Message"])');
      if (btn) {
        btn.click();
        await new Promise(r => setTimeout(r, 800));
      }
    } catch {}

    // If we're on a channel page with an empty composer, attempt to focus DM by keyboard shortcut
    // Ctrl/Cmd+K then type user ID (Slack resolves it) and Enter
    try {
      if (user) {
        const mod = navigator.platform.includes('Mac') ? 'metaKey' : 'ctrlKey';
        const openQuickSwitcher = new KeyboardEvent('keydown', { key: 'k', [mod]: true, bubbles: true });
        document.dispatchEvent(openQuickSwitcher);
        await new Promise(r => setTimeout(r, 400));
        const switcher = document.querySelector('input[placeholder*="Search"]') || document.querySelector('input[aria-label*="Search"]');
        if (switcher) {
          switcher.focus();
          switcher.value = user;
          switcher.dispatchEvent(new Event('input', { bubbles: true }));
          await new Promise(r => setTimeout(r, 400));
          const enter = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
          switcher.dispatchEvent(enter);
          await new Promise(r => setTimeout(r, 800));
        }
      }
    } catch {}

    const composer = await waitForComposer();
    if (!composer) return;
    // Insert text
    try {
      composer.focus();
      // Use clipboard if available; fallback to direct insertion
      if (navigator.clipboard && navigator.clipboard.readText) {
        try {
          const clip = await navigator.clipboard.readText();
          if (!clip) await navigator.clipboard.writeText(msg);
        } catch {}
      }
      // Direct insertion
      const sel = window.getSelection();
      if (sel && sel.rangeCount > 0) sel.deleteFromDocument();
      document.execCommand('insertText', false, msg);
      // Send (Enter)
      const sendEv = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
      composer.dispatchEvent(sendEv);
    } catch {}
  }

  // Run after a short delay to let Slack boot
  setTimeout(run, 1500);
})();


