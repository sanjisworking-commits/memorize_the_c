/* ===========================================================================
   Visual Explainer controller — standalone and additive; app.js is untouched.
   One delegated listener; each trigger carries its own data-ve-* attributes.
   Guests see the CTA but opening is gated through the existing guest sign-in
   modal; pending intent resumes after login.
   =========================================================================== */
(function () {
  "use strict";

  var MIN = 0.25, MAX = 4, STEP = 1.25, MOBILE_BP = 720;
  var FALLBACK_W = 1000;   // only used if a stray SVG reports no intrinsic size
  var PENDING_KEY = "rtc_pending_ve";

  var el = {};
  // natW is read from the loaded image, so each Article's own export drives the
  // zoom maths — no diagram dimensions are hard-coded anywhere.
  var S = { open: false, scale: 1, fit: 1, touched: false, src: "", trigger: null, natW: 0 };

  function cache() {
    var root = document.getElementById("ve-modal");
    if (!root) return false;
    el.root = root;
    el.canvas = root.querySelector("[data-ve-canvas]");
    el.sheet = root.querySelector("[data-ve-sheet]");
    el.img = root.querySelector("[data-ve-img]");
    el.pcts = root.querySelectorAll("[data-ve-pct]");
    el.outs = root.querySelectorAll("[data-ve-out]");
    el.ins = root.querySelectorAll("[data-ve-in]");
    el.article = root.querySelector("[data-ve-article]");
    el.title = root.querySelector("[data-ve-title]");
    el.type = root.querySelector("[data-ve-type]");
    el.file = root.querySelector("[data-ve-file]");
    el.close = root.querySelector("[data-ve-close]");
    el.live = root.querySelector("[data-ve-live]");
    el.loading = root.querySelector("[data-ve-loading]");
    el.error = root.querySelector("[data-ve-error]");
    return true;
  }

  function isMobile() { return window.innerWidth <= MOBILE_BP; }
  function isGuest() { return document.body.classList.contains("is-guest"); }
  function say(msg) { if (el.live) el.live.textContent = msg; }
  function pad() { return isMobile() ? 10 : 26; }

  function payloadFromTrigger(trigger) {
    return {
      src: trigger.getAttribute("data-ve-src") || "",
      article: trigger.getAttribute("data-ve-article") || "",
      title: trigger.getAttribute("data-ve-title") || "",
      type: trigger.getAttribute("data-ve-type") || "flowchart",
    };
  }

  function savePending(payload) {
    try {
      sessionStorage.setItem(PENDING_KEY, JSON.stringify(payload));
    } catch (err) { /* private mode / quota */ }
  }

  function readPending() {
    try {
      var raw = sessionStorage.getItem(PENDING_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (err) {
      return null;
    }
  }

  function clearPending() {
    try {
      sessionStorage.removeItem(PENDING_KEY);
    } catch (err) { /* ignore */ }
  }

  // Fit-to-width on a phone lands near 25% and is unreadable, so open legible
  // and let the reader pan. "Fit" still gives the overview.
  function startScale() {
    return isMobile() ? Math.min(0.72, Math.max(0.46, S.fit * 2.2)) : S.fit;
  }

  function measure() {
    if (!el.canvas || !S.natW) return;
    var w = el.canvas.clientWidth - pad() * 2 - 2;
    S.fit = Math.max(MIN, Math.min(1, w / S.natW));
    if (!S.touched) apply(startScale(), false);
  }

  function apply(next, keepCentre) {
    next = Math.min(MAX, Math.max(MIN, next));
    var c = el.canvas, cx = 0.5, cy = 0.5, i;
    if (keepCentre && c) {
      cx = c.scrollWidth > c.clientWidth ? (c.scrollLeft + c.clientWidth / 2) / c.scrollWidth : 0.5;
      cy = (c.scrollTop + c.clientHeight / 2) / Math.max(1, c.scrollHeight);
    }
    S.scale = next;
    if (S.natW) el.sheet.style.width = Math.round(S.natW * next) + "px";
    for (i = 0; i < el.pcts.length; i++) el.pcts[i].textContent = Math.round(next * 100) + "%";
    for (i = 0; i < el.outs.length; i++) el.outs[i].disabled = next <= MIN + 0.001;
    for (i = 0; i < el.ins.length; i++) el.ins[i].disabled = next >= MAX - 0.001;
    if (!c) return;
    if (keepCentre) {
      c.scrollLeft = Math.max(0, cx * c.scrollWidth - c.clientWidth / 2);
      c.scrollTop = Math.max(0, cy * c.scrollHeight - c.clientHeight / 2);
    } else {
      c.scrollLeft = Math.max(0, (c.scrollWidth - c.clientWidth) / 2);
    }
  }

  function zoom(dir) {
    S.touched = true;
    apply(dir > 0 ? S.scale * STEP : S.scale / STEP, true);
    say("Zoom " + Math.round(S.scale * 100) + "%");
  }

  function fitWidth() {
    S.touched = false;
    apply(S.fit, false);
    if (el.canvas) el.canvas.scrollLeft = 0;
    say("Fit to width");
  }

  function openFromPayload(payload, trigger) {
    if (!el.root && !cache()) return;
    S.trigger = trigger || null;
    S.src = payload.src || "";
    var num = payload.article || "";
    var title = payload.title || "";
    var type = (payload.type || "flowchart").toLowerCase();

    el.article.textContent = num ? "Article " + num : "Visual explainer";
    el.title.textContent = title;
    el.title.hidden = !title;
    el.type.textContent = type;
    if (el.file) el.file.textContent = S.src.split("/").pop();

    el.error.hidden = true;
    el.loading.hidden = false;
    el.img.hidden = true;
    S.natW = 0;                       // re-read from whichever SVG this is
    el.sheet.style.width = "";
    el.img.removeAttribute("src");    // so switching Articles always re-fires load
    el.img.alt = "Article " + num + " " + type + (title ? " — " + title : "");
    el.img.src = S.src;

    document.body.style.overflow = "hidden";   // page keeps its scroll position
    el.root.hidden = false;
    S.open = true;
    S.touched = false;
    requestAnimationFrame(function () {
      measure();
      if (el.close) el.close.focus();
    });
    say("Visual explainer opened. Article " + num + ".");
  }

  function open(trigger) {
    openFromPayload(payloadFromTrigger(trigger), trigger);
  }

  function requestVisualExplainer(trigger) {
    if (!trigger) return;
    if (isGuest()) {
      savePending(payloadFromTrigger(trigger));
      if (typeof window.openGuestModal === "function") {
        window.openGuestModal("visualise");
      } else {
        var next = window.location.pathname + window.location.search;
        window.location.href =
          "/login?next=" + encodeURIComponent(next) + "&reason=visualise";
      }
      return;
    }
    open(trigger);
  }

  function resumePending() {
    if (isGuest()) return;
    var pending = readPending();
    if (!pending || !pending.src) return;
    clearPending();
    openFromPayload(pending, null);
  }

  function close() {
    if (!S.open) return;
    el.root.hidden = true;
    S.open = false;
    document.body.style.overflow = "";
    if (S.trigger && S.trigger.focus) S.trigger.focus();
    say("Visual explainer closed.");
  }

  // Desktop controls and the mobile pill both live in the DOM; only one set is
  // displayed per breakpoint, so the trap must skip anything not rendered.
  function focusable() {
    var all = el.root.querySelectorAll("button:not([disabled]), [href], [tabindex]:not([tabindex='-1'])");
    var out = [];
    for (var i = 0; i < all.length; i++) {
      var n = all[i];
      if (n.offsetParent === null) continue;              // display:none branch
      if (!n.getClientRects().length) continue;           // zero-box / clipped
      if (n.closest("[hidden]")) continue;                // hidden error panel
      out.push(n);
    }
    return out;
  }

  function wireGuestDismissClear() {
    // Only clear on explicit "Continue as guest" — do not clear when the user
    // follows Sign in (dialog may close during navigation and would wipe intent).
    document.querySelectorAll("[data-guest-modal-dismiss]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        clearPending();
      });
    });
  }

  function wire() {
    if (!cache()) return;

    el.img.addEventListener("load", function () {
      el.loading.hidden = true;
      el.error.hidden = true;
      el.img.hidden = false;
      // Intrinsic width of THIS Article's export. An SVG with a viewBox always
      // reports one; the fallback only guards a malformed export.
      S.natW = el.img.naturalWidth || FALLBACK_W;
      if (!el.img.naturalWidth && window.console) {
        console.warn("[visual-explainer] no intrinsic width on " + S.src + " — add a viewBox to the root <svg>.");
      }
      S.touched = false;
      measure();
    });
    el.img.addEventListener("error", function () {
      el.loading.hidden = true;
      el.img.hidden = true;
      el.error.hidden = false;
    });

    el.root.addEventListener("click", function (e) {
      var t = e.target.closest("[data-ve-action]");
      if (t) {
        var a = t.getAttribute("data-ve-action");
        if (a === "close") close();
        else if (a === "in") zoom(1);
        else if (a === "out") zoom(-1);
        else if (a === "fit") fitWidth();
        else if (a === "actual") { S.touched = true; apply(1, true); }
        else if (a === "retry") {
          el.error.hidden = true;
          el.loading.hidden = false;
          el.img.src = S.src + (S.src.indexOf("?") < 0 ? "?" : "&") + "r=" + Date.now();
        }
        return;
      }
      if (e.target === el.root && !isMobile()) close();   // backdrop, desktop only
    });

    // Cmd/Ctrl + wheel zooms; plain wheel scrolls. Needs a non-passive listener.
    el.canvas.addEventListener("wheel", function (e) {
      if (!(e.ctrlKey || e.metaKey)) return;
      e.preventDefault();
      S.touched = true;
      apply(S.scale * (e.deltaY < 0 ? 1.09 : 1 / 1.09), true);
    }, { passive: false });

    // drag to pan (mouse only — touch uses native two-axis scrolling)
    el.canvas.addEventListener("mousedown", function (e) {
      var c = el.canvas;
      if (e.button !== 0) return;
      if (c.scrollWidth <= c.clientWidth && c.scrollHeight <= c.clientHeight) return;
      e.preventDefault();
      var sx = c.scrollLeft, sy = c.scrollTop, x0 = e.clientX, y0 = e.clientY;
      c.classList.add("is-panning");
      function move(ev) { c.scrollLeft = sx - (ev.clientX - x0); c.scrollTop = sy - (ev.clientY - y0); }
      function up() {
        document.removeEventListener("mousemove", move);
        document.removeEventListener("mouseup", up);
        c.classList.remove("is-panning");
      }
      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", up);
    });

    // triggers anywhere on the page (Browse card, Article actions, Learn band)
    document.addEventListener("click", function (e) {
      var t = e.target.closest("[data-ve-open]");
      if (!t) return;
      e.preventDefault();
      requestVisualExplainer(t);
    });

    document.addEventListener("keydown", function (e) {
      // Real <button> triggers fire click on Enter/Space themselves; this only
      // covers a non-button trigger, should one ever be added.
      var t = e.target.closest && e.target.closest("[data-ve-open]");
      if (t && t.tagName !== "BUTTON" && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        requestVisualExplainer(t);
        return;
      }
      if (!S.open) return;
      if (e.key === "Escape") { e.preventDefault(); close(); }
      else if (e.key === "+" || e.key === "=") { e.preventDefault(); zoom(1); }
      else if (e.key === "-" || e.key === "_") { e.preventDefault(); zoom(-1); }
      else if (e.key === "0") { e.preventDefault(); fitWidth(); }
      else if (e.key === "Tab") {                        // keep focus in the dialog
        var f = focusable();
        if (!f.length) return;
        var first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    });

    window.addEventListener("resize", function () { if (S.open) measure(); });
    wireGuestDismissClear();
    resumePending();
  }

  window.requestVisualExplainer = requestVisualExplainer;

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
  else wire();
})();
