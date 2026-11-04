// Blurby's enhancements for browsers with JavaScript. Every page also works
// without this file. The Content-Security-Policy forbids inline scripts and
// event handlers, so everything is wired up here.
"use strict";

// Copy a field's text: through the Clipboard API, which needs a secure
// context (HTTPS or localhost), or else by selecting the text and using the
// older copy command. Returns whether either worked.
async function copyText(field) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(field.value);
      return true;
    } catch {
      // Denied or unavailable: fall back to the copy command.
    }
  }
  field.focus();
  field.select();
  try {
    return document.execCommand("copy");
  } catch {
    return false;
  }
}

// <button data-copy="#field-id" hidden> copies that field's text. The button
// is hidden in the markup, so browsers without JavaScript don't show it.
function setUpCopyButtons(root) {
  for (const button of root.querySelectorAll("button[data-copy]")) {
    const field = document.querySelector(button.dataset.copy);
    if (!field) continue;
    const label = button.textContent;
    button.hidden = false;
    button.addEventListener("click", async () => {
      // If copying fails, the text is still selected for Ctrl+C.
      button.textContent = (await copyText(field)) ? "Copied!" : "Press Ctrl+C";
      setTimeout(() => {
        button.textContent = label;
      }, 2000);
    });
  }
}

setUpCopyButtons(document);
