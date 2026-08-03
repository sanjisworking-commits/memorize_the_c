(function () {
  "use strict";

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function initDemo() {
    var root = qs("[data-landing-demo]");
    if (!root) return;
    var input = qs("[data-demo-input]", root);
    var blank = qs("[data-demo-blank]", root);
    var status = qs("[data-demo-status]", root);
    var checkBtn = qs("[data-demo-check]", root);
    if (!input || !blank || !status || !checkBtn) return;

    function setCorrect() {
      blank.textContent = "units";
      blank.classList.add("is-filled");
      status.hidden = false;
      status.className = "landing-demo-status is-ok";
      status.innerHTML =
        '<span class="landing-demo-check" aria-hidden="true">✓</span> You recalled the C. That\'s the whole method.';
      input.value = "units";
    }

    function setWrong() {
      status.hidden = false;
      status.className = "landing-demo-status is-bad";
      status.innerHTML =
        "Not quite. Try 'units' — or <button type=\"button\" class=\"landing-demo-reveal\" data-demo-reveal>reveal the answer</button>";
      var reveal = qs("[data-demo-reveal]", status);
      if (reveal) {
        reveal.addEventListener("click", function () {
          setCorrect();
        });
      }
    }

    function clearStatus() {
      if (blank.classList.contains("is-filled")) return;
      status.hidden = true;
      status.textContent = "";
      status.className = "landing-demo-status";
    }

    function submit() {
      var raw = (input.value || "").trim().toLowerCase();
      if (!raw) return;
      if (raw === "units" || raw === "unit") {
        setCorrect();
      } else {
        setWrong();
      }
    }

    checkBtn.addEventListener("click", submit);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        submit();
      }
    });
    input.addEventListener("input", clearStatus);
  }

  function initReveal() {
    var nodes = document.querySelectorAll("[data-reveal], .landing-reveal, .landing-step");
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
      { threshold: 0.14 }
    );
    nodes.forEach(function (el) {
      obs.observe(el);
    });
  }

  function boot() {
    initDemo();
    initReveal();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
