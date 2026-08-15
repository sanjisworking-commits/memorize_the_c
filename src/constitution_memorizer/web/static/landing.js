(function () {
  "use strict";

  var ART32 =
    "the right to move the supreme court by appropriate proceedings for the enforcement of the rights conferred by this part is guaranteed.";

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function qsa(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  function initModes() {
    var root = qs("[data-modes]");
    if (!root) return;
    var tabs = qsa("[data-mode]", root);
    var panels = qsa("[data-mode-panel]", root);
    if (!tabs.length || !panels.length) return;

    function show(name) {
      tabs.forEach(function (tab) {
        var on = tab.getAttribute("data-mode") === name;
        tab.setAttribute("aria-selected", on ? "true" : "false");
      });
      panels.forEach(function (panel) {
        var on = panel.getAttribute("data-mode-panel") === name;
        panel.hidden = !on;
      });
    }

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        show(tab.getAttribute("data-mode"));
      });
    });
  }

  function initType() {
    var input = qs("[data-type-input]");
    var btn = qs("[data-type-check]");
    var status = qs("[data-type-status]");
    if (!input || !btn || !status) return;

    function normalize(s) {
      return (s || "")
        .trim()
        .toLowerCase()
        .replace(/[“”]/g, '"')
        .replace(/[‘’]/g, "'")
        .replace(/\s+/g, " ")
        .replace(/[.,;:]+$/g, "");
    }

    function submit() {
      var raw = normalize(input.value);
      if (!raw) return;
      status.hidden = false;
      if (raw === ART32 || raw === ART32.replace(/\.$/, "")) {
        status.className = "lp-status is-ok";
        status.textContent = "You recalled the provision. That is the method.";
      } else {
        status.className = "lp-status";
        status.textContent = "Not yet. Try again from memory — wording has to match.";
      }
    }

    btn.addEventListener("click", submit);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        submit();
      }
    });
    input.addEventListener("input", function () {
      status.hidden = true;
      status.textContent = "";
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

  function initBoat() {
    var el = qs("[data-boat-day]");
    if (!el) return;
    var reduced =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      el.textContent = "Day 60";
      return;
    }
    var from = 5;
    var to = 60;
    var started = null;
    var duration = 2200;

    function frame(ts) {
      if (started == null) started = ts;
      var t = Math.min(1, (ts - started) / duration);
      var eased = 1 - Math.pow(1 - t, 3);
      var n = Math.round(from + (to - from) * eased);
      el.textContent = "Day " + n;
      if (t < 1) window.requestAnimationFrame(frame);
    }
    window.requestAnimationFrame(frame);
  }

  function initReveal() {
    var nodes = qsa("[data-reveal], .lp-reveal");
    if (!nodes.length) return;

    function showAll() {
      nodes.forEach(function (el) {
        el.classList.add("is-visible");
      });
    }

    if (!("IntersectionObserver" in window)) {
      showAll();
      return;
    }

    var reduced =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      showAll();
      return;
    }

    var obs = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          obs.unobserve(entry.target);
        });
      },
      { threshold: 0.12 }
    );
    nodes.forEach(function (el) {
      obs.observe(el);
    });
  }

  function boot() {
    initModes();
    initType();
    initCard();
    initBoat();
    initReveal();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
