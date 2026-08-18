/*
 * Standalone pricing page — duration selector + theme toggle.
 *
 * The duration selector is a self-contained port of initPricing() from app.js,
 * operating on the same [data-pricing*] hooks and #pricing-data JSON so the
 * marketing pricing page keeps live selection without loading the app bundle.
 * The pill <a> links still work as full-page navigations when JS is off.
 */
(function () {
  "use strict";

  function initPricing() {
    var root = document.querySelector("[data-pricing]");
    if (!root) return;
    var plans = [];
    try {
      var data = document.getElementById("pricing-data");
      plans = data ? JSON.parse(data.textContent || "[]") : [];
    } catch (_e) {
      return; // fall back to full-page navigation via the pill links
    }
    var byDays = {};
    plans.forEach(function (plan) {
      byDays[String(plan.days)] = plan;
    });
    var pills = Array.prototype.slice.call(
      root.querySelectorAll("[data-pricing-days]")
    );
    var els = {
      title: root.querySelector("[data-pricing-title]"),
      price: root.querySelector("[data-pricing-price]"),
      perday: root.querySelector("[data-pricing-perday]"),
      tagline: root.querySelector("[data-pricing-tagline]"),
      annotation: root.querySelector("[data-pricing-annotation]"),
      journey: root.querySelector("[data-pricing-journey]"),
      cta: root.querySelector("[data-pricing-cta]"),
      billing: root.querySelector("[data-pricing-billing]"),
    };

    var moreToggle = root.querySelector("[data-pricing-more-toggle]");
    var morePills = pills.filter(function (pill) {
      return pill.classList.contains("is-more");
    });

    function setMoreOpen(open) {
      morePills.forEach(function (pill) {
        pill.hidden = !open && !pill.classList.contains("is-selected");
      });
      if (moreToggle) {
        moreToggle.setAttribute("aria-expanded", open ? "true" : "false");
        moreToggle.textContent = open ? "Fewer options" : "More options";
      }
    }

    function select(days) {
      var plan = byDays[String(days)];
      if (!plan) return;
      root.setAttribute("data-selected-days", String(plan.days));
      pills.forEach(function (pill) {
        var active = pill.getAttribute("data-pricing-days") === String(plan.days);
        pill.classList.toggle("is-selected", active);
        pill.setAttribute("aria-checked", active ? "true" : "false");
      });
      if (els.title) els.title.textContent = plan.days + "-Day Recall";
      if (els.price) els.price.textContent = "₹" + plan.price_inr;
      if (els.perday) els.perday.textContent = "₹" + plan.per_day.toFixed(2) + " / day";
      if (els.tagline) els.tagline.textContent = plan.tagline;
      if (els.annotation) {
        els.annotation.textContent = plan.annotation || "";
        els.annotation.hidden = !plan.annotation;
      }
      if (els.journey) els.journey.hidden = plan.days !== 180;
      if (els.cta) {
        els.cta.textContent = "Start my " + plan.days + " days →";
        var href = els.cta.getAttribute("href");
        if (href) {
          var target = new URL(href, window.location.origin);
          target.searchParams.set("d", String(plan.days));
          els.cta.setAttribute("href", target.pathname + target.search);
        }
      }
      if (els.billing) els.billing.textContent = plan.billing_line;
      // Update only the d param — preserve any other query params and hash.
      var u = new URL(window.location.href);
      u.searchParams.set("d", String(plan.days));
      history.replaceState(null, "", u.pathname + u.search + u.hash);
    }

    pills.forEach(function (pill, index) {
      pill.addEventListener("click", function (event) {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
          return;
        }
        event.preventDefault();
        select(pill.getAttribute("data-pricing-days"));
        pill.focus();
      });
      pill.addEventListener("keydown", function (event) {
        var target = null;
        if (event.key === "ArrowRight" || event.key === "ArrowDown") {
          target = pills[(index + 1) % pills.length];
        } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
          target = pills[(index - 1 + pills.length) % pills.length];
        } else if (event.key === "Home") {
          target = pills[0];
        } else if (event.key === "End") {
          target = pills[pills.length - 1];
        } else {
          return;
        }
        event.preventDefault();
        if (target.hidden) setMoreOpen(true);
        select(target.getAttribute("data-pricing-days"));
        target.focus();
      });
    });

    if (moreToggle) {
      moreToggle.addEventListener("click", function () {
        setMoreOpen(moreToggle.getAttribute("aria-expanded") !== "true");
      });
    }
  }

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
    initPricing();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
