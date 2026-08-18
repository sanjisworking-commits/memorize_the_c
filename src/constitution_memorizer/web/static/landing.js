/*
 * Recall the C — landing page motion.
 *
 * A vanilla port of the Claude Design component (`Recall the C - Landing.dc.html`).
 * Drives the full-screen letter-field → sphere → brain canvas, the top progress
 * rail, per-section scrims, scroll reveals, the 180-day ruler, the six mode
 * circles, the running-head marker, and the pinned closing statement.
 *
 * Brain path data (window.BRAIN_PATHS / window.BRAIN_BOX) is provided by
 * /static/brain-path.js, which must load first.
 */
(function () {
  "use strict";

  var reduced =
    !!(window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  var state = { lit: 0 };
  var scrollP = 0;

  var parts = null;
  var groups = null;
  var canvas = null;
  var ctx = null;

  // ── Letter field → sphere → brain ─────────────────────────────
  function setupField() {
    if (parts) return;
    // Path data arrives from a separate script; retry until it is there.
    try {
      buildField();
    } catch (e) {
      parts = null;
    }
  }

  function buildField() {
    var D = window.BRAIN_PATHS;
    if (!D) throw new Error("brain path data not loaded");

    var ns = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(ns, "svg");
    svg.setAttribute(
      "style",
      "position:absolute;width:0;height:0;overflow:hidden;opacity:0"
    );
    document.body.appendChild(svg);

    // Measure every subpath first, then hand out a fixed particle budget in
    // proportion to length, so long contours read and hairline folds survive.
    var els = [];
    var lens = [];
    var total = 0;
    var i;
    for (i = 0; i < D.length; i++) {
      var path = document.createElementNS(ns, "path");
      path.setAttribute("d", D[i]);
      svg.appendChild(path);
      var L = path.getTotalLength();
      els.push(path);
      lens.push(L);
      total += L;
    }

    var step = total / 1250;
    var CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789§";
    var built = [];
    var grps = [];

    for (i = 0; i < els.length; i++) {
      var len = lens[i];
      var n = Math.max(2, Math.round(len / step));
      var idx = [];
      for (var k = 0; k < n; k++) {
        var pt = els[i].getPointAtLength((k / (n - 1)) * len);
        idx.push(built.length);
        built.push({
          bx: pt.x,
          by: pt.y,
          ch: CHARS[(Math.random() * CHARS.length) | 0],
        });
      }
      grps.push({ idx: idx, closed: /z\s*$/i.test(D[i]), major: len > 360 });
    }
    svg.remove();

    // Sphere seats (fibonacci) + scattered origins out in space
    var N = built.length;
    var golden = Math.PI * (3 - Math.sqrt(5));
    built.forEach(function (p, j) {
      var y = 1 - (j / (N - 1)) * 2;
      var r = Math.sqrt(Math.max(0, 1 - y * y));
      var th = golden * j;
      p.sx = Math.cos(th) * r;
      p.sy = y;
      p.sz = Math.sin(th) * r;
      var a = Math.random() * Math.PI * 2;
      var d = 0.55 + Math.random() * 0.95;
      p.ox = Math.cos(a) * d;
      p.oy = Math.sin(a) * d * 0.9;
      p.delay = Math.random() * 0.42;
      p.accent = Math.random() < 0.09;
      p.size = 8 + Math.random() * 4;
    });

    parts = built;
    groups = grps;
  }

  function drawField() {
    // Lazy attach: the canvas may render after this script boots.
    if (!canvas || !canvas.isConnected) {
      var el = document.querySelector("[data-brain]");
      if (!el) return;
      canvas = el;
      ctx = el.getContext("2d");
    }
    if (!parts) setupField();
    var c = canvas;
    if (!c || !parts) return;
    var rect = c.getBoundingClientRect();
    if (!rect.width || !rect.height) return;

    var dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    if (
      c.width !== Math.round(rect.width * dpr) ||
      c.height !== Math.round(rect.height * dpr)
    ) {
      c.width = Math.round(rect.width * dpr);
      c.height = Math.round(rect.height * dpr);
    }
    var w = rect.width;
    var hgt = rect.height;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, hgt);

    var p = scrollP || 0;
    var clamp = function (v) {
      return v < 0 ? 0 : v > 1 ? 1 : v;
    };
    var easeOut = function (v) {
      return 1 - Math.pow(1 - v, 3);
    };
    var easeInOut = function (v) {
      return v < 0.5 ? 4 * v * v * v : 1 - Math.pow(-2 * v + 2, 3) / 2;
    };

    var morph = easeInOut(clamp((p - 0.46) / 0.32));
    var t = Date.now();
    var spin = (reduced ? 0 : t * 0.00007) + p * 2.6;

    var cx = w * 0.5;
    var cy = hgt * 0.5;
    var R = Math.min(w * 0.3, hgt * 0.4);
    // Glyphs scale with the viewport — at full size on a phone the field reads
    // as a crowd rather than a haze.
    var gScale = Math.max(0.52, Math.min(1, Math.min(w, hgt * 1.4) / 1280));
    var box = window.BRAIN_BOX || [940, 670];
    var bScale = Math.min(w * 0.00066, hgt * 0.00116);
    var bw = box[0] * bScale;
    var bh = box[1] * bScale;

    var cosR = Math.cos(spin);
    var sinR = Math.sin(spin);

    var i;
    for (i = 0; i < parts.length; i++) {
      var q = parts[i];
      // each letter gathers on its own slightly staggered schedule
      var g = easeOut(clamp((p / 0.24 - q.delay) / (1 - q.delay)));

      var rx = q.sx * cosR - q.sz * sinR;
      var rz = q.sx * sinR + q.sz * cosR;
      var persp = 1 / (1 + rz * 0.42);

      var sphX = cx + rx * R * persp;
      var sphY = cy + q.sy * R * persp;
      var spaceX = cx + q.ox * w * 0.5;
      var spaceY = cy + q.oy * hgt * 0.5;

      var x = spaceX + (sphX - spaceX) * g;
      var y = spaceY + (sphY - spaceY) * g;

      if (morph > 0) {
        // The finished brain keeps breathing. Phase comes from the point's
        // BRAIN-space position, so neighbours on a contour drift together
        // (sphere coords are unordered along a path and would zigzag), and
        // amplitude scales with the drawing so it stays subtle when small.
        var bob = reduced ? 0 : morph * bScale * 9;
        var bX =
          cx - bw / 2 + q.bx * bScale + Math.sin(t * 0.00021 + q.by * 0.006) * bob;
        var bY =
          cy -
          bh / 2 +
          q.by * bScale +
          Math.sin(t * 0.00027 + q.bx * 0.005) * bob * 0.7;
        x += (bX - x) * morph;
        y += (bY - y) * morph;
      }
      q.x = x;
      q.y = y;
      q.depth = persp;
    }

    // Lines take over from the letters as the brain resolves.
    // Only once the points have essentially landed — drawn any earlier, each
    // polyline still joins scattered sphere seats and reads as noise.
    if (morph > 0.86) {
      var la = clamp((morph - 0.86) / 0.14);
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      for (var gi = 0; gi < groups.length; gi++) {
        var grp = groups[gi];
        ctx.lineWidth = gi === 0 ? 1.5 : grp.major ? 1.2 : 0.9;
        ctx.strokeStyle =
          gi === 0
            ? "rgba(110,130,200," + la.toFixed(3) + ")"
            : grp.major
            ? "rgba(110,130,200," + (la * 0.8).toFixed(3) + ")"
            : "rgba(244,241,234," + (la * 0.72).toFixed(3) + ")";
        ctx.beginPath();
        var ix = grp.idx;
        for (var kk = 0; kk < ix.length; kk++) {
          var qp = parts[ix[kk]];
          if (kk === 0) ctx.moveTo(qp.x, qp.y);
          else ctx.lineTo(qp.x, qp.y);
        }
        if (grp.closed) ctx.closePath();
        ctx.stroke();
      }
    }

    // Letters fade out as the lines arrive
    var glyphA = 1 - clamp((morph - 0.8) / 0.2);
    if (glyphA > 0.02) {
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      var lastFont = "";
      for (i = 0; i < parts.length; i++) {
        var qc = parts[i];
        var a = glyphA * (0.3 + qc.depth * 0.5);
        var f =
          Math.max(4, Math.round(qc.size * gScale * (0.75 + qc.depth * 0.4))) +
          'px "Source Sans 3", system-ui, sans-serif';
        if (f !== lastFont) {
          ctx.font = f;
          lastFont = f;
        }
        ctx.fillStyle = qc.accent
          ? "rgba(110,130,200," + Math.min(1, a * 1.2).toFixed(3) + ")"
          : "rgba(244,241,234," + a.toFixed(3) + ")";
        ctx.fillText(qc.ch, qc.x, qc.y);
      }
    }
  }

  // The visible state rides on the attribute so the authored inline style is
  // never fought over; a per-element delay staggers card rows.
  function reveal(el) {
    if (el.getAttribute("data-shown") || el.getAttribute("data-pending")) return;
    var d = reduced ? 0 : parseInt(el.getAttribute("data-delay") || "0", 10);
    if (!d) {
      el.setAttribute("data-shown", "1");
      return;
    }
    el.setAttribute("data-pending", "1");
    setTimeout(function () {
      el.setAttribute("data-shown", "1");
    }, d);
  }

  function revealAll() {
    var nodes = document.querySelectorAll("[data-reveal]");
    Array.prototype.forEach.call(nodes, function (el) {
      reveal(el);
    });
  }

  function measure() {
    var vh = window.innerHeight || 800;
    var doc = document.documentElement;
    if (doc.scrollHeight < vh * 1.4) return; // still laying out

    var y = window.pageYOffset || doc.scrollTop || 0;

    // Top progress rail — always true page scroll.
    var max = doc.scrollHeight - vh;
    var trueP = max > 0 ? Math.min(1, y / max) : 0;
    var bar = document.querySelector("[data-progress-bar]");
    if (bar) bar.style.width = (trueP * 100).toFixed(2) + "%";

    // The letter field runs on its own clock, frozen while #arithmetic is
    // pinned: that section's scroll span is removed from the total, so the
    // brain holds the state it reached and resumes from there afterwards.
    var ay = y;
    var hold = 0;
    var pinSrc = document.querySelector("[data-pin-src]");
    if (pinSrc) {
      var psr = pinSrc.getBoundingClientRect();
      var pinTop = psr.top + y;
      hold = Math.max(0, psr.height - vh);
      if (y > pinTop + hold) ay = y - hold;
      else if (y > pinTop) ay = pinTop;
    }
    scrollP = Math.min(1, ay / Math.max(1, max - hold));

    // Per-section scrims: rise as the section enters, fall as it leaves, so
    // the letter field stays visible between sections but never under copy.
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-scrim]"),
      function (el) {
        var r = el.getBoundingClientRect();
        var enter = Math.max(0, Math.min(1, (vh - r.top) / (vh * 0.22)));
        var exit = Math.max(0, Math.min(1, r.bottom / (vh * 0.16)));
        el.style.opacity = Math.min(enter, exit).toFixed(3);
      }
    );

    // Section reveals.
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-reveal]"),
      function (el) {
        if (el.getBoundingClientRect().top < vh * 0.9) reveal(el);
        if (el.getAttribute("data-shown") && el.style.opacity !== "1") {
          el.style.opacity = "1";
          el.style.transform = "none";
        }
      }
    );

    // §01 "The arithmetic": 13 Part squares fly up from the bottom of the
    // pinned frame and settle in a scatter (desktop) / stream through (phone).
    var pin = document.querySelector("[data-pin-src]");
    if (pin) {
      var pr = pin.getBoundingClientRect();
      var span = pr.height - vh;
      var p = span > 40 ? Math.max(0, Math.min(1, -pr.top / span)) : 1;

      // The field holds its state here but dims to ~25% so the squares read;
      // brightness returns only once #method is half scrolled.
      var brain = document.querySelector("[data-brain]");
      if (brain) {
        var enterD = Math.min(1, p / 0.12);
        var holdD = 1;
        var nxt = document.getElementById("method");
        if (nxt) {
          var mr = nxt.getBoundingClientRect();
          holdD = 1 - Math.max(0, Math.min(1, -mr.top / Math.max(1, mr.height * 0.5)));
        }
        var dimv = Math.max(0, Math.min(enterD, holdD));
        brain.style.opacity = (1 - 0.75 * dimv).toFixed(3);
      }

      var cards = pin.querySelectorAll("[data-pcard]");
      var n = cards.length;
      var narrow = window.innerWidth <= 900;
      var frameH = pr.height > vh ? vh : pr.height;
      Array.prototype.forEach.call(cards, function (el, i) {
        if (narrow && !reduced) {
          // Phone: no rest — rise from below the frame and carry out the top.
          var kk = Math.max(0, Math.min(1, (p - (i / n) * 0.7) / 0.3));
          el.style.opacity = "1";
          el.style.transform =
            "translate3d(0," + (((110 - 160 * kk) * vh) / 100).toFixed(1) + "px,0)";
          return;
        }
        // Desktop: the statement lands first, then each square eases up to its
        // authored resting slot (pulled up rather than clipped at the bottom).
        var start = 0.16 + (i / n) * 0.62;
        var k = reduced ? 1 : Math.max(0, Math.min(1, (p - start) / 0.22));
        var e = 1 - Math.pow(1 - k, 3);
        var lift = Math.max(0, el.offsetTop + el.offsetHeight - frameH + 10);
        var travel = Math.max(0, frameH - el.offsetTop + lift);
        el.style.opacity = k > 0 ? "1" : "0";
        el.style.transform =
          "translate3d(0," + ((1 - e) * travel - lift).toFixed(1) + "px,0)";
      });
    }

    // Six mode circles: overlapped when the section arrives, spaced out as it passes
    var wrap = document.querySelector("[data-circles]");
    if (wrap) {
      var wide = window.innerWidth > 820;
      var wr = wrap.getBoundingClientRect();
      var cp = Math.max(0, Math.min(1, (vh * 0.92 - wr.top) / (vh * 0.72)));
      var ml = (-24 + 27 * cp).toFixed(2) + "%";
      // Phone: 3-column grid, so overlap applies within each row and rows
      // close up vertically by the same amount.
      var gml = (-30 + 26 * cp).toFixed(2) + "%";
      var circles = wrap.querySelectorAll("[data-circ]");
      Array.prototype.forEach.call(circles, function (el, i) {
        if (wide) {
          if (i > 0) el.style.marginLeft = ml;
          el.style.marginTop = "";
        } else {
          el.style.marginLeft = i % 3 === 0 ? "0%" : gml;
          el.style.marginTop = i > 2 ? gml : "";
        }
        var on = cp * 6.4 > i + 0.15;
        el.style.color = on ? "#f4f1ea" : "rgba(244,241,234,0.62)";
        el.style.borderColor = on
          ? "rgba(110,130,200,0.5)"
          : "rgba(244,241,234,0.14)";
      });
    }

    // Closing statement lights line by line across its pinned scroll
    var lit = state.lit;
    var src = document.querySelector("[data-lit-src]");
    if (src) {
      var r = src.getBoundingClientRect();
      var span = r.height - vh;
      var pp = span > 0 ? Math.max(0, Math.min(1, -r.top / span)) : 0;
      // Nothing lights until the block is actually pinned (top reaches 0);
      // before that it is still sliding up and the words are off-centre.
      var pinned = r.top <= 1;
      lit = !pinned ? 0 : Math.max(1, Math.min(4, 1 + Math.floor(pp * 4.4)));

      // Colour is set inline per line (the CSS-selector approach lost to the
      // reduced-motion !important override and lit every line at once).
      var spans = src.querySelectorAll("[data-l]");
      Array.prototype.forEach.call(spans, function (el, i) {
        var on = reduced || (pinned && i < lit);
        el.style.color = on
          ? i === spans.length - 1 && lit >= spans.length
            ? "#6E82C8"
            : "#f4f1ea"
          : "rgba(244,241,234,0.26)";
      });

      // Scrim only reaches full once the block is pinned and the statement owns
      // the viewport; releases as the block leaves.
      var scrim = src.querySelector("[data-closescrim]");
      if (scrim) {
        var near = Math.max(0, Math.min(1, (vh - r.top) / vh));
        var out = Math.max(0, Math.min(1, r.bottom / (vh * 0.6)));
        scrim.style.opacity = (Math.min(near, out) * 0.96).toFixed(3);
      }
    }

    if (lit !== state.lit) {
      state.lit = lit;
      var litHost = src && src.querySelector("[data-lit]");
      if (litHost) litHost.setAttribute("data-lit", String(lit));
    }
  }

  // ── Boot ──────────────────────────────────────────────────────
  var lastY = -1;
  var lastH = -1;
  var raf;

  function tick() {
    var y = window.pageYOffset || document.documentElement.scrollTop || 0;
    var h = document.documentElement.scrollHeight;
    if (y !== lastY || h !== lastH) {
      lastY = y;
      lastH = h;
      measure();
    }
    drawField();
    raf = requestAnimationFrame(tick);
  }

  function onEvt() {
    measure();
    drawField();
  }

  function boot() {
    raf = requestAnimationFrame(tick);

    measure();
    setTimeout(measure, 160);
    // rAF is paused while the tab is hidden; this only covers that case.
    setInterval(function () {
      if (document.hidden) {
        measure();
        drawField();
      }
    }, 250);
    document.addEventListener("visibilitychange", onEvt);
    window.addEventListener("scroll", onEvt, { passive: true });
    window.addEventListener("resize", onEvt);
    // Last resort: content must never stay permanently invisible.
    setTimeout(revealAll, 1400);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
