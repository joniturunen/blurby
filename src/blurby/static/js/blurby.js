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

// While a read-once secret is on screen (<article data-shown-once>), ask before
// the reader leaves: it won't be shown again. Browsers show their own generic
// wording, so the page itself explains why, and they ask only after the reader
// has interacted with the page.
function warnBeforeLeaving(root) {
  if (!root.querySelector("[data-shown-once]")) return;
  window.addEventListener("beforeunload", (event) => {
    event.preventDefault();
    event.returnValue = ""; // for older browsers
  });
}

// <form data-reveal> reveals a read-once secret in place, with fetch, so that
// the Reveal click counts as interaction for the leave-page prompt. Without
// JavaScript, or if the request fails, the form posts as usual.
function setUpReveal(root) {
  for (const form of root.querySelectorAll("form[data-reveal]")) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      form.querySelector("button")?.setAttribute("aria-busy", "true");
      let page;
      try {
        const response = await fetch(form.action, { method: "POST" });
        page = new DOMParser().parseFromString(await response.text(), "text/html");
      } catch {
        form.submit(); // doesn't fire this handler again
        return;
      }
      const main = page.querySelector("main");
      if (!main) {
        // Not a Blurby page (a proxy's error page, say): let the browser show it.
        form.submit();
        return;
      }
      document.querySelector("main").replaceWith(main);
      document.title = page.title;
      setUp(main);
    });
  }
}

// <button data-theme-switch hidden> switches between light and dark mode, and
// saves the choice for theme.js. A choice that matches the system's setting is
// forgotten instead, so the page follows the system again.
const THEME_KEY = "blurby-theme";
const systemDark = window.matchMedia("(prefers-color-scheme: dark)");

function systemTheme() {
  return systemDark.matches ? "dark" : "light";
}

function setUpThemeSwitch() {
  const button = document.querySelector("button[data-theme-switch]");
  if (!button) return;
  const page = document.documentElement;
  const show = () => {
    const dark = (page.dataset.theme || systemTheme()) === "dark";
    button.setAttribute("aria-pressed", String(dark));
    button.title = dark ? "Switch to light mode" : "Switch to dark mode";
  };
  button.addEventListener("click", () => {
    const theme = button.getAttribute("aria-pressed") === "true" ? "light" : "dark";
    const chosen = theme !== systemTheme();
    if (chosen) page.dataset.theme = theme;
    else delete page.dataset.theme;
    try {
      if (chosen) localStorage.setItem(THEME_KEY, theme);
      else localStorage.removeItem(THEME_KEY);
    } catch {
      // Not saved: the choice lasts until the reader leaves the page.
    }
    show();
  });
  systemDark.addEventListener("change", show);
  show();
  button.hidden = false;
}

function setUp(root) {
  setUpCopyButtons(root);
  setUpReveal(root);
  warnBeforeLeaving(root);
}

setUpThemeSwitch();
setUp(document);
