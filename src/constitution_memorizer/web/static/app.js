/* Light progressive enhancement for the learning UI. */
(function () {
  function initLearn() {
    const learn = document.querySelector(".learn");
    if (!learn) {
      return;
    }
    learn.classList.add("is-ready");

    const modeTabs = learn.querySelectorAll("[data-learn-mode]");
    const card = learn.querySelector(".learn-card");

    function setFlipped(flipped) {
      if (!card) {
        return;
      }
      card.dataset.flipped = flipped ? "true" : "false";
      card.classList.toggle("is-flipped", flipped);
      card.setAttribute("aria-pressed", flipped ? "true" : "false");
    }

    function setMode(mode) {
      const next = mode === "card" ? "card" : "read";
      learn.dataset.mode = next;
      modeTabs.forEach((tab) => {
        const active = tab.getAttribute("data-learn-mode") === next;
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", active ? "true" : "false");
      });
      if (next === "card") {
        setFlipped(false);
      }
      try {
        const url = new URL(window.location.href);
        if (next === "read") {
          url.searchParams.delete("mode");
        } else {
          url.searchParams.set("mode", next);
        }
        window.history.replaceState(null, "", url.pathname + url.search);
      } catch (_err) {
        /* ignore */
      }
    }

    modeTabs.forEach((tab) => {
      tab.addEventListener("click", (event) => {
        const mode = tab.getAttribute("data-learn-mode");
        if (!mode) {
          return;
        }
        // Soft-switch when JS works; <a href="?mode="> still works without JS.
        event.preventDefault();
        setMode(mode);
      });
    });

    if (card) {
      card.addEventListener("click", () => {
        setFlipped(card.dataset.flipped !== "true");
      });
      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          setFlipped(card.dataset.flipped !== "true");
        }
      });
    }

    // Honor server-rendered mode (e.g. hard navigation to ?mode=card).
    if (learn.dataset.mode === "card") {
      setFlipped(false);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLearn);
  } else {
    initLearn();
  }
})();
