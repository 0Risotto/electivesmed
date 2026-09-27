/* electivesmed web behaviors: theme, dialogs, snackbar, submit guard, onboarding. */
(() => {
  "use strict";

  const THEME_KEY = "electivesmed-theme";
  const root = document.documentElement;

  const stored = localStorage.getItem(THEME_KEY);
  if (stored === "light" || stored === "dark") root.dataset.theme = stored;

  function currentTheme() {
    if (root.dataset.theme) return root.dataset.theme;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-theme-toggle]")) {
      const next = currentTheme() === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      localStorage.setItem(THEME_KEY, next);
    }

    const opener = event.target.closest("[data-dialog-open]");
    if (opener) {
      const dialog = document.querySelector(opener.dataset.dialogOpen);
      if (dialog && typeof dialog.showModal === "function") dialog.showModal();
    }

    const closer = event.target.closest("[data-dialog-close]");
    if (closer) {
      const dialog = closer.closest("dialog");
      if (dialog) dialog.close();
    }

    if (event.target instanceof HTMLDialogElement) {
      const rect = event.target.getBoundingClientRect();
      const inside =
        event.clientX >= rect.left &&
        event.clientX <= rect.right &&
        event.clientY >= rect.top &&
        event.clientY <= rect.bottom;
      if (!inside) event.target.close();
    }
  });

  document.addEventListener("input", (event) => {
    const input = event.target.closest("[data-confirm-expect]");
    if (!input) return;
    const form = input.closest("form");
    const button = form ? form.querySelector("[data-confirm-submit]") : null;
    if (button) button.disabled = input.value.trim() !== input.dataset.confirmExpect;
  });

  const snackbar = document.getElementById("snackbar");
  if (snackbar) {
    const dismiss = () => snackbar.remove();
    const dismissButton = snackbar.querySelector("[data-snackbar-dismiss]");
    if (dismissButton) dismissButton.addEventListener("click", dismiss);
    setTimeout(dismiss, 6000);
    const url = new URL(window.location.href);
    if (url.searchParams.has("flash")) {
      url.searchParams.delete("flash");
      const query = url.searchParams.toString();
      history.replaceState({}, "", url.pathname + (query ? "?" + query : ""));
    }
  }

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (form.dataset.submitting === "true") {
      event.preventDefault();
      return;
    }
    form.dataset.submitting = "true";
    setTimeout(() => {
      form.querySelectorAll('button[type="submit"], button:not([type])').forEach((button) => {
        button.disabled = true;
      });
    }, 0);
    setTimeout(() => {
      form.dataset.submitting = "false";
    }, 4000);
  });

  const onboarding = document.getElementById("onboarding");
  if (onboarding) {
    if (localStorage.getItem("electivesmed-onboarding-dismissed") === "1") {
      onboarding.classList.add("hidden");
    }
    const dismiss = onboarding.querySelector("[data-onboarding-dismiss]");
    if (dismiss) {
      dismiss.addEventListener("click", () => {
        localStorage.setItem("electivesmed-onboarding-dismissed", "1");
        onboarding.classList.add("hidden");
      });
    }
  }
})();
