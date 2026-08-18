/*
 * Recall the C — light landing motion.
 *
 * Vanilla port of the "v2 light" Claude Design component. Drives the
 * scroll-revealed sections, the sticky orbit-rings figure (data-g stage), the
 * 180-day ruler fill, the Read→Card mode switcher, the flip card, and the
 * persisted dark/light theme toggle. No canvas — the figure is inline SVG.
 */
(function () {
  "use strict";

  var reduced =
    !!(window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  // One line per staged section (hero, §01, §02, §03, §05-laws). §04 was removed.
  var LINES = [
    "It begins with one line, held on purpose.",
    "Ordinary days, in a row, are the whole method.",
    "Recognition is borrowed. Recall is yours.",
    "Ask it six ways and it stops being a habit.",
    "The more you know, the more free you become.",
  ];
  var LAST = LINES.length - 1;

  var state = { stage: -1 };

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }
  function qsa(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  // ── Scroll reveal ─────────────────────────────────────────────
  function reveal(el) {
    if (el.getAttribute("data-shown")) return;
    el.setAttribute("data-shown", "1");
    var d = reduced ? 0 : parseInt(el.getAttribute("data-delay") || "0", 10);
    setTimeout(function () {
      el.style.opacity = "1";
      el.style.transform = "none";
    }, d);
  }
  function revealAll() {
    qsa("[data-reveal]").forEach(reveal);
  }

  // ── Sticky orbit-rings figure ─────────────────────────────────
  function renderFigure() {
    var stage = Math.max(0, Math.min(state.stage, LAST));
    // The last staged section reveals the whole figure (the CSS ring cascade
    // tops out at data-g="5", one more than the number of sections left).
    var g = stage >= LAST ? 5 : stage;
    var wrap = qs("[data-figwrap]");
    if (wrap) wrap.setAttribute("data-g", String(g));
    var figline = qs("[data-figline]");
    if (figline) {
      var sp = figline.querySelectorAll("span");
      if (sp[0]) sp[0].textContent = LINES[stage];
      if (sp[1]) sp[1].textContent = "0" + (stage + 1) + " / 0" + LINES.length;
    }
  }

  function measure() {
    var vh = window.innerHeight || 800;
    // Bail while the document is still laying out — every rect would read 0.
    if (document.documentElement.scrollHeight < vh * 1.4) return;

    qsa("[data-reveal]").forEach(function (el) {
      if (el.getBoundingClientRect().top < vh * 0.92) reveal(el);
    });

    var line = vh * 0.55;
    var stage = 0;
    qsa("[data-stage]").forEach(function (el) {
      var n = parseInt(el.getAttribute("data-stage"), 10);
      if (el.getBoundingClientRect().top < line && n > stage) stage = n;
    });
    if (stage !== state.stage) {
      state.stage = stage;
      renderFigure();
    }
  }

  // ── 180-day ruler fill ────────────────────────────────────────
  function initRuler() {
    var fill = qs("[data-fill]");
    if (!fill) return;
    var w = fill.getAttribute("data-fill") + "%";
    if (reduced) fill.style.width = w;
    else setTimeout(function () { fill.style.width = w; }, 500);
  }

  // ── Read → Card mode switcher ─────────────────────────────────
  function resetCard() {
    var front = qs("[data-card-front]");
    var back = qs("[data-card-back]");
    if (front && back) {
      front.hidden = false;
      back.hidden = true;
    }
  }

  function initModes() {
    var root = qs("[data-modes]");
    if (!root) return;
    var tabs = qsa("[data-mode]", root);
    var panels = qsa("[data-mode-panel]");
    var prog = qs("[data-mode-prog]");
    if (!tabs.length || !panels.length) return;

    function show(i) {
      tabs.forEach(function (t) {
        t.setAttribute(
          "data-tab",
          t.getAttribute("data-mode") === String(i) ? "on" : "off"
        );
      });
      panels.forEach(function (p) {
        p.hidden = p.getAttribute("data-mode-panel") !== String(i);
      });
      if (prog) prog.style.width = Math.round(((i + 1) / 6) * 100) + "%";
      resetCard();
    }

    tabs.forEach(function (t) {
      t.addEventListener("click", function () {
        show(parseInt(t.getAttribute("data-mode"), 10));
      });
    });
  }

  function initCard() {
    var btn = qs("[data-card-flip]");
    if (!btn) return;
    var front = qs("[data-card-front]", btn);
    var back = qs("[data-card-back]", btn);
    if (!front || !back) return;
    btn.addEventListener("click", function () {
      var showingBack = !back.hidden;
      front.hidden = !showingBack;
      back.hidden = showingBack;
    });
  }

  // ── Persisted dark/light landing toggle ───────────────────────
  function wireThemeToggle() {
    var btn = document.getElementById("landing-theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var to = btn.getAttribute("data-to") || "dark";
      document.cookie =
        "rtc_landing_theme=" + to + "; path=/; max-age=31536000; samesite=lax";
      location.reload();
    });
  }

  function boot() {
    wireThemeToggle();
    initRuler();
    initModes();
    initCard();
    renderFigure();
    measure();
    setTimeout(measure, 160);
    window.addEventListener("scroll", measure, { passive: true });
    window.addEventListener("resize", measure);
    // Last resort: content must never stay permanently invisible.
    setTimeout(revealAll, 1400);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
