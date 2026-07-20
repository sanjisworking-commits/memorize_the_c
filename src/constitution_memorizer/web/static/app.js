/* Light progressive enhancement for the learning UI. */
(function () {
  const LEARN_MODES = new Set(["read", "cloze", "card"]);
  const DENSITY_THRESH = { light: 8, medium: 6, heavy: 4 };

  function letterLen(word) {
    return word.replace(/[^A-Za-z]/g, "").length;
  }

  function initCloze(panel) {
    if (!panel) {
      return null;
    }

    const textEl = panel.querySelector(".learn-cloze-text");
    const statusEl = panel.querySelector("[data-cloze-status]");
    const densityBtns = panel.querySelectorAll("[data-cloze-density]");
    const source = panel.getAttribute("data-cloze-text") || "";
    const words = source.trim() ? source.trim().split(/\s+/) : [];
    let density = panel.getAttribute("data-cloze-density") || "medium";
    if (!DENSITY_THRESH[density]) {
      density = "medium";
    }
    const revealed = new Set();

    function threshold() {
      return DENSITY_THRESH[density] || 6;
    }

    function isBlank(word) {
      return letterLen(word) >= threshold();
    }

    function updateStatus() {
      let hidden = 0;
      let shown = 0;
      words.forEach((word, index) => {
        if (!isBlank(word)) {
          return;
        }
        hidden += 1;
        if (revealed.has(index)) {
          shown += 1;
        }
      });
      if (statusEl) {
        statusEl.textContent =
          shown + " of " + hidden + " revealed — tap a blank";
      }
    }

    function render() {
      if (!textEl) {
        return;
      }
      textEl.replaceChildren();
      words.forEach((word, index) => {
        const span = document.createElement("span");
        span.className = "learn-cloze-word";
        span.textContent = word + " ";
        if (isBlank(word)) {
          span.classList.add("is-blank");
          span.setAttribute("role", "button");
          span.setAttribute("tabindex", "0");
          span.setAttribute("aria-label", "Reveal hidden word");
          if (revealed.has(index)) {
            span.classList.add("is-revealed");
            span.removeAttribute("tabindex");
            span.removeAttribute("role");
            span.removeAttribute("aria-label");
          } else {
            const reveal = () => {
              revealed.add(index);
              render();
            };
            span.addEventListener("click", reveal);
            span.addEventListener("keydown", (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                reveal();
              }
            });
          }
        }
        textEl.appendChild(span);
      });
      updateStatus();
    }

    function setDensity(next) {
      if (!DENSITY_THRESH[next]) {
        return;
      }
      density = next;
      panel.setAttribute("data-cloze-density", next);
      revealed.clear();
      densityBtns.forEach((btn) => {
        const active = btn.getAttribute("data-cloze-density") === next;
        btn.classList.toggle("is-active", active);
        btn.setAttribute("aria-pressed", active ? "true" : "false");
      });
      render();
    }

    densityBtns.forEach((btn) => {
      btn.setAttribute(
        "aria-pressed",
        btn.getAttribute("data-cloze-density") === density ? "true" : "false",
      );
      btn.addEventListener("click", () => {
        setDensity(btn.getAttribute("data-cloze-density"));
      });
    });

    const revealAll = panel.querySelector('[data-cloze-action="reveal-all"]');
    const hideAgain = panel.querySelector('[data-cloze-action="hide-again"]');
    if (revealAll) {
      revealAll.addEventListener("click", () => {
        words.forEach((word, index) => {
          if (isBlank(word)) {
            revealed.add(index);
          }
        });
        render();
      });
    }
    if (hideAgain) {
      hideAgain.addEventListener("click", () => {
        revealed.clear();
        render();
      });
    }

    setDensity(density);

    return {
      reset() {
        revealed.clear();
        render();
      },
    };
  }

  function initLearn() {
    const learn = document.querySelector(".learn");
    if (!learn) {
      return;
    }
    learn.classList.add("is-ready");

    const modeTabs = learn.querySelectorAll("[data-learn-mode]");
    const card = learn.querySelector(".learn-card");
    const clozePanel = learn.querySelector('[data-learn-panel="cloze"]');
    const cloze = initCloze(clozePanel);

    function setFlipped(flipped) {
      if (!card) {
        return;
      }
      card.dataset.flipped = flipped ? "true" : "false";
      card.classList.toggle("is-flipped", flipped);
      card.setAttribute("aria-pressed", flipped ? "true" : "false");
    }

    function setMode(mode) {
      const next = LEARN_MODES.has(mode) ? mode : "read";
      learn.dataset.mode = next;
      modeTabs.forEach((tab) => {
        const active = tab.getAttribute("data-learn-mode") === next;
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", active ? "true" : "false");
      });
      if (next === "card") {
        setFlipped(false);
      }
      if (next === "cloze" && cloze) {
        cloze.reset();
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

    // Honor server-rendered mode (e.g. hard navigation to ?mode=card|cloze).
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
