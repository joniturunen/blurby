// Apply the reader's saved choice of light or dark mode before the page is
// drawn, so it doesn't flash in the other one: <head> loads this file without
// defer. Without a saved choice, Pico CSS follows the system's setting. The
// switch that saves the choice is set up in blurby.js.
"use strict";

try {
  const theme = localStorage.getItem("blurby-theme");
  if (theme === "light" || theme === "dark") {
    document.documentElement.dataset.theme = theme;
  }
} catch {
  // Storage is blocked (in some private windows): follow the system.
}
