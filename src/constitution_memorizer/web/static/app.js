/* Light progressive enhancement for the learning UI. */
(function () {
  const LEARN_MODES = new Set(["read", "cloze", "letters", "type", "recite", "card"]);
  const MOTION_KEY = "cm-motion";
  const SOUND_KEY = "cm-completion-sound";
  const DONE_SOUND_SRC = "/static/completion-done.mp3";
  const AFFIRMATION_HOLD_MS = 10000;
  let doneAudio = null;

  function prefersReducedMotion() {
    return Boolean(
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function motionEnabled() {
    try {
      return !prefersReducedMotion() && localStorage.getItem(MOTION_KEY) !== "off";
    } catch (_e) {
      return !prefersReducedMotion();
    }
  }

  function soundEnabled() {
    try {
      return localStorage.getItem(SOUND_KEY) !== "off";
    } catch (_e) {
      return true;
    }
  }

  function syncRtcAnim() {
    document.documentElement.classList.toggle("rtc-anim", motionEnabled());
  }

  function scrollToElement(el) {
    if (!el) {
      return;
    }
    const rect = el.getBoundingClientRect();
    if (rect.top >= 0 && rect.bottom <= (window.innerHeight || 0)) {
      return;
    }
    el.scrollIntoView({
      behavior: motionEnabled() ? "smooth" : "auto",
      block: "center",
    });
  }

  function rtcReveal(el, opts) {
    if (!el) {
      return;
    }
    const delay = (opts && opts.delay) || 0;
    if (!motionEnabled()) {
      el.classList.add("rtc-reveal--visible");
      return;
    }
    window.setTimeout(function () {
      el.classList.add("rtc-reveal--visible");
    }, delay);
  }

  function initHeadingReveal() {
    document.querySelectorAll("[data-rtc-reveal]").forEach(function (el) {
      rtcReveal(el, { delay: 0 });
    });
  }
  const DENSITY_THRESH = { light: 8, medium: 6, heavy: 4 };
  const EN_SPACE = "\u2002";

  function letterLen(word) {
    return word.replace(/[^A-Za-z]/g, "").length;
  }

  /** First-letter cue string matching the design prototype. */
  function toInitials(text) {
    const words = text.trim() ? text.trim().split(/\s+/) : [];
    return words
      .map((word) => {
        const match = word.match(/^[A-Za-z]/);
        if (!match) {
          return word;
        }
        const punct = word
          .replace(/[A-Za-z]+/g, "")
          .replace(/[^.,;\u2014()]/g, "");
        return match[0] + punct;
      })
      .join(EN_SPACE);
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

  function initLetters(panel) {
    if (!panel) {
      return null;
    }

    const display = panel.querySelector("[data-letters-display]");
    const toggle = panel.querySelector("[data-letters-toggle]");
    const source = panel.getAttribute("data-letters-text") || "";
    const initials = toInitials(source);
    let full = panel.getAttribute("data-letters-full") === "true";

    function render() {
      if (!display) {
        return;
      }
      display.textContent = full ? source : initials;
      display.classList.toggle("is-full", full);
      display.classList.toggle("is-initials", !full);
      panel.setAttribute("data-letters-full", full ? "true" : "false");
      if (toggle) {
        toggle.textContent = full ? "Back to initials" : "Show full text";
        toggle.setAttribute("aria-pressed", full ? "true" : "false");
      }
    }

    if (toggle) {
      toggle.addEventListener("click", () => {
        full = !full;
        render();
        if (full) {
          scrollToElement(display);
        }
      });
    }

    render();

    return {
      reset() {
        full = false;
        render();
      },
    };
  }

  function normWord(text) {
    return text.toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  function initType(panel) {
    if (!panel) {
      return null;
    }

    const input = panel.querySelector("[data-type-input]");
    const diffEl = panel.querySelector("[data-type-diff]");
    const statsEl = panel.querySelector("[data-type-stats]");
    const source = panel.getAttribute("data-type-text") || "";
    const words = source.trim() ? source.trim().split(/\s+/) : [];

    function render() {
      const typed = input ? input.value : "";
      const typedWords = typed.trim() ? typed.trim().split(/\s+/) : [];
      let correct = 0;

      if (diffEl) {
        diffEl.replaceChildren();
        words.forEach((word, index) => {
          const span = document.createElement("span");
          span.className = "learn-type-word";
          span.textContent = word + " ";
          if (index >= typedWords.length) {
            span.classList.add("is-unreached");
          } else if (normWord(typedWords[index]) === normWord(word)) {
            span.classList.add("is-correct");
            correct += 1;
          } else {
            span.classList.add("is-wrong");
          }
          diffEl.appendChild(span);
        });
      }

      if (statsEl) {
        statsEl.textContent =
          typedWords.length +
          " / " +
          words.length +
          " words · " +
          correct +
          " correct";
      }
    }

    if (input) {
      input.addEventListener("input", render);
    }
    render();

    return {
      reset() {
        if (input) {
          input.value = "";
        }
        render();
      },
    };
  }

  function initRecite(panel) {
    if (!panel) {
      return null;
    }

    const textEl = panel.querySelector("[data-recite-blur]");
    const toggle = panel.querySelector("[data-recite-toggle]");
    const peekBtn = panel.querySelector("[data-recite-peek]");
    const statusEl = panel.querySelector("[data-recite-status]");
    const transcriptEl = panel.querySelector("[data-recite-transcript]");
    const fallbackEl = panel.querySelector("[data-recite-fallback]");
    const manualEl = panel.querySelector("[data-recite-manual]");
    const checkBtn = panel.querySelector("[data-recite-check]");
    const mapEl = panel.querySelector("[data-recite-map]");
    const statsEl = panel.querySelector("[data-recite-stats]");
    const extrasEl = panel.querySelector("[data-recite-extras]");
    const source = panel.getAttribute("data-recite-text") || "";

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition || null;

    let recOn = false;
    let peeking = false;
    let recognition = null;
    let finalTranscript = "";
    let interimTranscript = "";
    let unsupported = !SpeechRecognition;
    let stopping = false;

    function setHidden(el, hidden) {
      if (!el) {
        return;
      }
      el.hidden = hidden;
    }

    function showFallback(show) {
      setHidden(fallbackEl, !show);
      if (show && manualEl) {
        manualEl.focus();
      }
    }

    function clearResults() {
      finalTranscript = "";
      interimTranscript = "";
      if (transcriptEl) {
        transcriptEl.textContent = "";
        transcriptEl.classList.remove("is-live");
      }
      if (mapEl) {
        mapEl.replaceChildren();
      }
      if (statsEl) {
        statsEl.textContent = "";
      }
      if (extrasEl) {
        extrasEl.textContent = "";
      }
      if (manualEl) {
        manualEl.value = "";
      }
      setHidden(transcriptEl, true);
      setHidden(mapEl, true);
      setHidden(statsEl, true);
      setHidden(extrasEl, true);
      showFallback(false);
    }

    function showStatus(message, kind) {
      if (!statusEl) {
        return;
      }
      statusEl.textContent = message || "";
      statusEl.classList.toggle("is-listening", kind === "listening");
      statusEl.classList.toggle("is-error", kind === "error");
      setHidden(statusEl, !message);
    }

    function renderTranscriptLive() {
      const combined = (finalTranscript + " " + interimTranscript).trim();
      if (!transcriptEl) {
        return;
      }
      if (!combined) {
        setHidden(transcriptEl, true);
        transcriptEl.textContent = "";
        transcriptEl.classList.remove("is-live");
        return;
      }
      transcriptEl.classList.add("is-live");
      transcriptEl.textContent = combined;
      setHidden(transcriptEl, false);
    }

    function renderAccuracyMap(spokenText, labelPrefix) {
      const align = window.RecallAlign;
      if (!align || !mapEl) {
        return;
      }
      const result = align.alignText(source, spokenText || "");
      mapEl.replaceChildren();
      result.sourceWords.forEach((word, index) => {
        const span = document.createElement("span");
        span.className = "learn-recite-map-word";
        span.classList.add(result.hitIndices.has(index) ? "is-hit" : "is-miss");
        span.textContent = word + " ";
        mapEl.appendChild(span);
      });
      setHidden(mapEl, result.sourceWords.length === 0);

      if (statsEl) {
        statsEl.textContent = result.statsLabel;
        setHidden(statsEl, false);
      }
      if (extrasEl) {
        if (result.extras.length) {
          extrasEl.textContent = "Heard (extra): " + result.extras.join(" ");
          setHidden(extrasEl, false);
        } else {
          extrasEl.textContent = "";
          setHidden(extrasEl, true);
        }
      }

      if (transcriptEl) {
        transcriptEl.classList.remove("is-live");
        const heard = (spokenText || "").trim();
        const prefix = labelPrefix || "Heard";
        if (heard) {
          transcriptEl.textContent = prefix + ": " + heard;
          setHidden(transcriptEl, false);
        } else {
          transcriptEl.textContent = "";
          setHidden(transcriptEl, true);
        }
      }
    }

    function stopRecognition() {
      if (recognition) {
        try {
          recognition.onresult = null;
          recognition.onerror = null;
          recognition.onend = null;
          recognition.abort();
        } catch (_err) {
          try {
            recognition.stop();
          } catch (_err2) {
            /* ignore */
          }
        }
        recognition = null;
      }
    }

    function abortForServiceFailure(message) {
      recOn = false;
      stopping = true;
      stopRecognition();
      stopping = false;
      render();
      showStatus(message, "error");
      showFallback(true);
    }

    function finishRecite() {
      stopping = true;
      recOn = false;
      stopRecognition();
      stopping = false;
      const spoken = (finalTranscript + " " + interimTranscript).trim();
      finalTranscript = spoken;
      interimTranscript = "";
      render();
      if (spoken) {
        showStatus("Accuracy map from your recital.", null);
        showFallback(false);
        renderAccuracyMap(spoken, "Heard");
      } else {
        showStatus(
          "No speech captured. Check your connection, or type what you recited below.",
          "error",
        );
        clearResults();
        setHidden(statusEl, false);
        showFallback(true);
      }
    }

    function startRecognition() {
      clearResults();
      finalTranscript = "";
      interimTranscript = "";
      recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
      // Prefer Indian English for Bare Act wording; browsers fall back if missing.
      recognition.lang = "en-IN";

      recognition.onresult = (event) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const piece = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript = (finalTranscript + " " + piece).trim();
          } else {
            interim += piece;
          }
        }
        interimTranscript = interim.trim();
        renderTranscriptLive();
      };

      recognition.onerror = (event) => {
        const err = event && event.error ? event.error : "error";
        if (err === "aborted") {
          return;
        }
        if (err === "not-allowed" || err === "service-not-allowed") {
          unsupported = true;
          abortForServiceFailure(
            "Voice recite needs Chrome or Edge with microphone access.",
          );
          if (toggle) {
            toggle.disabled = true;
          }
          return;
        }
        if (err === "no-speech") {
          // Benign while continuous; keep listening.
          showStatus("Listening… speak the Bare Act aloud.", "listening");
          return;
        }
        if (err === "network" || err === "audio-capture") {
          // Chrome's Web Speech API needs reachability to its cloud speech
          // service. Without it, stop cleanly and offer manual check.
          abortForServiceFailure(
            err === "network"
              ? "Speech service unreachable (network). Chrome needs internet access to its speech servers — or type what you recited below."
              : "Microphone capture failed. Type what you recited below, or check mic permissions.",
          );
          return;
        }
        abortForServiceFailure(
          "Speech recognition failed (" +
            err +
            "). Type what you recited below.",
        );
      };

      recognition.onend = () => {
        if (stopping || !recOn) {
          return;
        }
        // Chrome often ends continuous sessions early — restart while active.
        try {
          recognition.start();
        } catch (_err) {
          finishRecite();
        }
      };

      try {
        recognition.start();
        showStatus("Listening… speak the Bare Act aloud.", "listening");
      } catch (_err) {
        unsupported = true;
        recOn = false;
        recognition = null;
        showStatus(
          "Voice recite needs Chrome or Edge with microphone access.",
          "error",
        );
        if (toggle) {
          toggle.disabled = true;
        }
        showFallback(true);
        render();
      }
    }

    function render() {
      panel.setAttribute("data-recite-on", recOn ? "true" : "false");
      panel.setAttribute("data-peeking", peeking ? "true" : "false");
      if (textEl) {
        textEl.classList.toggle("is-blurred", !peeking);
      }
      if (toggle) {
        toggle.classList.toggle("is-active", recOn);
        toggle.textContent = recOn ? "■ Stop reciting" : "▸ Start reciting";
        toggle.setAttribute("aria-pressed", recOn ? "true" : "false");
        if (unsupported) {
          toggle.disabled = true;
        }
      }
    }

    function setPeek(next) {
      peeking = next;
      render();
    }

    if (unsupported) {
      showStatus(
        "Voice recite needs Chrome or Edge with microphone access.",
        "error",
      );
      if (toggle) {
        toggle.disabled = true;
      }
      showFallback(true);
    }

    if (toggle) {
      toggle.addEventListener("click", () => {
        if (unsupported) {
          return;
        }
        if (recOn) {
          finishRecite();
          return;
        }
        recOn = true;
        render();
        startRecognition();
      });
    }

    if (checkBtn) {
      checkBtn.addEventListener("click", () => {
        const spoken = manualEl ? manualEl.value.trim() : "";
        if (!spoken) {
          showStatus("Type what you recited, then check accuracy.", "error");
          return;
        }
        showStatus("Accuracy map from your text.", null);
        renderAccuracyMap(spoken, "Entered");
      });
    }

    if (peekBtn) {
      const startPeek = (event) => {
        event.preventDefault();
        setPeek(true);
      };
      const endPeek = (event) => {
        event.preventDefault();
        setPeek(false);
      };
      peekBtn.addEventListener("mousedown", startPeek);
      peekBtn.addEventListener("mouseup", endPeek);
      peekBtn.addEventListener("mouseleave", endPeek);
      peekBtn.addEventListener("touchstart", startPeek, { passive: false });
      peekBtn.addEventListener("touchend", endPeek);
      peekBtn.addEventListener("touchcancel", endPeek);
      peekBtn.addEventListener("keydown", (event) => {
        if (event.key === " " || event.key === "Enter") {
          event.preventDefault();
          setPeek(true);
        }
      });
      peekBtn.addEventListener("keyup", (event) => {
        if (event.key === " " || event.key === "Enter") {
          event.preventDefault();
          setPeek(false);
        }
      });
      peekBtn.addEventListener("blur", () => setPeek(false));
    }

    render();

    return {
      reset() {
        stopping = true;
        recOn = false;
        peeking = false;
        stopRecognition();
        stopping = false;
        clearResults();
        if (!unsupported) {
          showStatus("", null);
        } else {
          showStatus(
            "Voice recite needs Chrome or Edge with microphone access.",
            "error",
          );
          showFallback(true);
        }
        render();
      },
    };
  }

  function initBareFns(root) {
    const scope = root || document;
    const LEAVE_MS = 120;
    let pinnedPrimary = null;

    function closeNested(trigger) {
      if (!trigger) {
        return;
      }
      const tipId = trigger.getAttribute("aria-controls");
      const nested = tipId ? document.getElementById(tipId) : null;
      trigger.setAttribute("aria-expanded", "false");
      trigger.classList.remove("is-open");
      if (nested) {
        nested.hidden = true;
        nested.classList.remove("is-open");
      }
    }

    function openNested(trigger) {
      if (!trigger) {
        return;
      }
      const tipId = trigger.getAttribute("aria-controls");
      const nested = tipId ? document.getElementById(tipId) : null;
      trigger.setAttribute("aria-expanded", "true");
      trigger.classList.add("is-open");
      if (nested) {
        nested.hidden = false;
        nested.classList.add("is-open");
      }
    }

    function closePrimary(el, tip) {
      el.querySelectorAll(".bare-fn-nested-trigger").forEach(closeNested);
      tip.hidden = true;
      el.classList.remove("is-open", "is-pinned");
      if (pinnedPrimary === el) {
        pinnedPrimary = null;
      }
    }

    function openPrimary(el, tip, pin) {
      if (pinnedPrimary && pinnedPrimary !== el) {
        const otherTip = pinnedPrimary.querySelector(":scope > .bare-fn-tip");
        if (otherTip) {
          closePrimary(pinnedPrimary, otherTip);
        }
      }
      tip.hidden = false;
      el.classList.add("is-open");
      if (pin) {
        el.classList.add("is-pinned");
        pinnedPrimary = el;
      }
    }

    scope.querySelectorAll(".bare-fn").forEach((el) => {
      const tip = el.querySelector(":scope > .bare-fn-tip");
      if (!tip || el.dataset.bareFnBound === "1") {
        return;
      }
      el.dataset.bareFnBound = "1";
      let leaveTimer = null;

      function clearLeave() {
        if (leaveTimer) {
          window.clearTimeout(leaveTimer);
          leaveTimer = null;
        }
      }

      function scheduleLeave() {
        clearLeave();
        leaveTimer = window.setTimeout(() => {
          if (el.classList.contains("is-pinned")) {
            return;
          }
          if (el.contains(document.activeElement)) {
            return;
          }
          closePrimary(el, tip);
        }, LEAVE_MS);
      }

      el.addEventListener("mouseenter", () => {
        clearLeave();
        openPrimary(el, tip, false);
      });
      el.addEventListener("mouseleave", scheduleLeave);
      el.addEventListener("focusin", () => {
        clearLeave();
        openPrimary(el, tip, false);
      });
      el.addEventListener("focusout", (event) => {
        if (el.contains(event.relatedTarget)) {
          return;
        }
        scheduleLeave();
      });

      // Tap/click on the marked word toggles pin (nested triggers stopPropagation).
      el.addEventListener("click", (event) => {
        if (event.target.closest(".bare-fn-nested-trigger")) {
          return;
        }
        event.preventDefault();
        if (el.classList.contains("is-pinned")) {
          closePrimary(el, tip);
        } else {
          openPrimary(el, tip, true);
        }
      });

      tip.querySelectorAll(".bare-fn-nested-trigger").forEach((trigger) => {
        if (trigger.dataset.bareNestedBound === "1") {
          return;
        }
        trigger.dataset.bareNestedBound = "1";
        const nestedId = trigger.getAttribute("aria-controls");
        const nested = nestedId ? document.getElementById(nestedId) : null;

        function showChild() {
          clearLeave();
          openPrimary(el, tip, el.classList.contains("is-pinned"));
          openNested(trigger);
        }

        function hideChild() {
          closeNested(trigger);
        }

        trigger.addEventListener("mouseenter", showChild);
        trigger.addEventListener("focus", showChild);
        if (nested) {
          nested.addEventListener("mouseenter", () => {
            clearLeave();
            showChild();
          });
          nested.addEventListener("mouseleave", () => {
            if (trigger.getAttribute("aria-expanded") !== "true") {
              return;
            }
            // Keep open while pinned via click; hover-only closes with parent leave.
          });
        }
        // Nested click must not toggle the parent tip.
        trigger.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          clearLeave();
          openPrimary(el, tip, true);
          if (trigger.getAttribute("aria-expanded") === "true") {
            hideChild();
          } else {
            showChild();
          }
        });
        trigger.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            event.stopPropagation();
            trigger.click();
          }
        });
      });
    });

    if (scope.dataset.bareFnGlobalBound === "1") {
      return;
    }
    scope.dataset.bareFnGlobalBound = "1";

    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") {
        return;
      }
      const openNestedBtn = document.querySelector(
        ".bare-fn-nested-trigger[aria-expanded='true']"
      );
      if (openNestedBtn) {
        closeNested(openNestedBtn);
        openNestedBtn.focus();
        event.preventDefault();
        return;
      }
      const openPrimaryEl = document.querySelector(".bare-fn.is-open, .bare-fn.is-pinned");
      if (openPrimaryEl) {
        const tip = openPrimaryEl.querySelector(":scope > .bare-fn-tip");
        if (tip) {
          closePrimary(openPrimaryEl, tip);
        }
        openPrimaryEl.focus();
        event.preventDefault();
      }
    });

    document.addEventListener("pointerdown", (event) => {
      const inside = event.target.closest(".bare-fn");
      document.querySelectorAll(".bare-fn.is-open, .bare-fn.is-pinned").forEach((el) => {
        if (inside === el || (inside && el.contains(inside))) {
          return;
        }
        const tip = el.querySelector(":scope > .bare-fn-tip");
        if (tip) {
          closePrimary(el, tip);
        }
      });
    });
  }

  function initLearn() {
    const learn = document.querySelector(".learn");
    if (!learn) {
      return;
    }
    learn.classList.add("is-ready");
    initBareFns(learn);

    const card = learn.querySelector(".learn-card");
    const clozePanel = learn.querySelector('[data-learn-panel="cloze"]');
    const lettersPanel = learn.querySelector('[data-learn-panel="letters"]');
    const typePanel = learn.querySelector('[data-learn-panel="type"]');
    const recitePanel = learn.querySelector('[data-learn-panel="recite"]');
    const cloze = initCloze(clozePanel);
    const letters = initLetters(lettersPanel);
    const typeMode = initType(typePanel);
    const recite = initRecite(recitePanel);
    const doneBtn = document.getElementById("learn-done-btn");

    function setFlipped(flipped) {
      if (!card) {
        return;
      }
      card.dataset.flipped = flipped ? "true" : "false";
      card.classList.toggle("is-flipped", flipped);
      card.setAttribute("aria-pressed", flipped ? "true" : "false");
    }

    const MODE_LABELS = {
      read: "Read",
      cloze: "Cloze",
      letters: "Letters",
      type: "Type",
      recite: "Recite",
      card: "Card",
    };
    const isGuest = learn.hasAttribute("data-guest-learn");
    const unitId = learn.getAttribute("data-unit-id") || "";
    const tabs = Array.from(learn.querySelectorAll("[data-learn-mode]"));
    const trackerEl = document.getElementById("methods-tracker");

    function parseModes(raw) {
      const set = new Set();
      String(raw || "")
        .split(",")
        .forEach((part) => {
          const value = part.trim();
          if (LEARN_MODES.has(value)) {
            set.add(value);
          }
        });
      return set;
    }

    const confirmedModes = parseModes(learn.getAttribute("data-modes-seen"));
    const guestVisitedModes = parseModes(learn.getAttribute("data-modes-seen"));
    const lockedModes = parseModes(learn.getAttribute("data-locked-modes"));
    // Entitlement-aware required set: six normally; the four open modes for
    // guests / cap-reached Articles (Type/Recite locked).
    const requiredModesRaw = parseModes(learn.getAttribute("data-required-modes"));
    const requiredModes = requiredModesRaw.size > 0 ? requiredModesRaw : new Set(LEARN_MODES);
    // Unclaimed Articles keep mode visits provisional until claimed on Done —
    // tracked in sessionStorage so a reload keeps the marks without any server
    // persistence (R2: three saved Articles, not unlimited half-saved ones).
    const seenProvisional = learn.getAttribute("data-seen-provisional") === "true";
    const provisionalKey = "cm-provisional:" + unitId;
    const provisionalModes = (function () {
      if (!seenProvisional) {
        return new Set();
      }
      try {
        return parseModes(sessionStorage.getItem(provisionalKey));
      } catch (_e) {
        return new Set();
      }
    })();
    function saveProvisional() {
      if (!seenProvisional) {
        return;
      }
      try {
        sessionStorage.setItem(provisionalKey, Array.from(provisionalModes).join(","));
      } catch (_e) {
        /* ignore */
      }
    }
    function visitedUnion() {
      const union = new Set(confirmedModes);
      provisionalModes.forEach(function (mode) {
        union.add(mode);
      });
      return union;
    }
    const inFlight = new Set();
    let serverDoneUnlocked = learn.dataset.doneUnlocked === "true";

    function requiredVisitedCount(visited) {
      let count = 0;
      requiredModes.forEach(function (mode) {
        if (visited.has(mode)) {
          count += 1;
        }
      });
      return count;
    }

    function methodsTrackerLine(count) {
      const total = requiredModes.size;
      if (count >= total) {
        return "All " + total + " methods visited — revision complete, mark it Done";
      }
      const word = total === 6 ? "six" : String(total);
      return (
        count +
        " of " + total + " methods visited · revision completes when you've been through all " +
        word
      );
    }

    function lockedMethodsLeftLabel(confirmedCount) {
      const remaining = requiredModes.size - confirmedCount;
      if (remaining <= 0) {
        return null;
      }
      if (remaining === 1) {
        return "1 method left";
      }
      return remaining + " methods left";
    }

    function applyLockedDoneLabel() {
      if (isGuest || !doneBtn || serverDoneUnlocked) {
        return;
      }
      const label = lockedMethodsLeftLabel(requiredVisitedCount(visitedUnion()));
      if (label) {
        doneBtn.textContent = label;
      }
    }

    function maybeUnlockProvisionalDone() {
      // Unclaimed Articles persist nothing server-side, so the Done affordance
      // unlocks from the provisional union; the server re-validates on POST.
      if (!seenProvisional || isGuest || serverDoneUnlocked || !doneBtn) {
        return;
      }
      if (requiredVisitedCount(visitedUnion()) >= requiredModes.size) {
        serverDoneUnlocked = true;
        applyDoneUnlocked("Mark it Done");
      } else {
        applyLockedDoneLabel();
      }
    }

    function applyTabMarks(visited) {
      tabs.forEach((tab) => {
        const tabMode = tab.getAttribute("data-learn-mode");
        if (!LEARN_MODES.has(tabMode)) {
          return;
        }
        const label = MODE_LABELS[tabMode] || tabMode;
        if (lockedModes.has(tabMode)) {
          // Locked modes never earn a ✓ — keep the restrained lock mark.
          tab.textContent = label + " 🔒";
          return;
        }
        tab.textContent = visited.has(tabMode) ? label + " ✓" : label;
      });
    }

    function applyTracker(visited) {
      if (!trackerEl) {
        return;
      }
      const count = requiredVisitedCount(visited);
      trackerEl.setAttribute("data-count", String(count));
      trackerEl.textContent = methodsTrackerLine(count);
    }

    function applyDoneUnlocked(label) {
      if (isGuest || !doneBtn) {
        return;
      }
      doneBtn.disabled = false;
      doneBtn.removeAttribute("disabled");
      doneBtn.setAttribute("aria-disabled", "false");
      doneBtn.classList.remove("btn-done-locked");
      doneBtn.classList.add("btn-accent");
      if (label) {
        doneBtn.textContent = label;
      }
    }

    function resetDestination(nextMode, prevMode) {
      if (prevMode === "recite" && nextMode !== "recite" && recite) {
        recite.reset();
      }
      if (nextMode === "card") {
        setFlipped(false);
      }
      if (nextMode === "cloze" && cloze) {
        cloze.reset();
      }
      if (nextMode === "letters" && letters) {
        letters.reset();
      }
      if (nextMode === "type" && typeMode) {
        typeMode.reset();
      }
      if (nextMode === "recite" && prevMode !== "recite" && recite) {
        recite.reset();
      }
    }

    function switchModeLocal(nextMode, tab) {
      const prevMode = learn.dataset.mode || "read";
      learn.dataset.mode = nextMode;
      tabs.forEach((item) => {
        const active = item.getAttribute("data-learn-mode") === nextMode;
        item.classList.toggle("is-active", active);
        item.setAttribute("aria-selected", active ? "true" : "false");
      });
      const href = tab.getAttribute("href");
      if (href) {
        history.replaceState({}, "", href);
      }
      resetDestination(nextMode, prevMode);
    }

    function persistSeen(mode) {
      if (
        isGuest ||
        lockedModes.has(mode) ||
        confirmedModes.has(mode) ||
        provisionalModes.has(mode) ||
        inFlight.has(mode) ||
        !unitId
      ) {
        return;
      }
      inFlight.add(mode);
      const body = new FormData();
      body.append("mode", mode);
      fetch("/learn/" + encodeURIComponent(unitId) + "/seen", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: body,
      })
        .then((response) => {
          const type = response.headers.get("content-type") || "";
          if (!response.ok || !type.includes("application/json")) {
            throw new Error("seen-failed");
          }
          return response.json();
        })
        .then((payload) => {
          inFlight.delete(mode);
          if (payload && payload.persisted === false) {
            // Provisional visit — track locally until the Article is claimed.
            provisionalModes.add(mode);
            saveProvisional();
            applyTabMarks(visitedUnion());
            applyTracker(visitedUnion());
            maybeUnlockProvisionalDone();
            return;
          }
          const seen = Array.isArray(payload.seen) ? payload.seen : [];
          seen.forEach((item) => {
            if (LEARN_MODES.has(item)) {
              confirmedModes.add(item);
            }
          });
          applyTabMarks(visitedUnion());
          applyTracker(visitedUnion());
          if (payload.done && payload.done.unlocked === true) {
            serverDoneUnlocked = true;
            applyDoneUnlocked(payload.done.label);
          } else if (serverDoneUnlocked) {
            /* keep unlocked; ignore stale unlocked:false */
          } else {
            applyLockedDoneLabel();
          }
        })
        .catch(() => {
          inFlight.delete(mode);
        });
    }

    learn.addEventListener("click", (event) => {
      if (
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey ||
        event.button !== 0
      ) {
        return;
      }
      const tab = event.target.closest("[data-learn-mode]");
      if (!tab || !learn.contains(tab)) {
        return;
      }
      const nextMode = tab.getAttribute("data-learn-mode");
      if (!LEARN_MODES.has(nextMode)) {
        return;
      }
      event.preventDefault();
      const current = learn.dataset.mode || "read";
      if (nextMode === current) {
        if (!isGuest) {
          persistSeen(nextMode);
        }
        return;
      }
      switchModeLocal(nextMode, tab);
      if (isGuest) {
        if (!lockedModes.has(nextMode)) {
          guestVisitedModes.add(nextMode);
        }
        applyTabMarks(guestVisitedModes);
        applyTracker(guestVisitedModes);
        return;
      }
      if (seenProvisional && !lockedModes.has(nextMode)) {
        provisionalModes.add(nextMode);
        saveProvisional();
        applyTabMarks(visitedUnion());
        applyTracker(visitedUnion());
        maybeUnlockProvisionalDone();
        return;
      }
      persistSeen(nextMode);
    });

    // Provisional boot: the server records nothing for unclaimed Articles, so
    // count the currently open mode locally and restore prior session marks.
    if (seenProvisional) {
      const bootMode = learn.dataset.mode || "read";
      if (!lockedModes.has(bootMode)) {
        provisionalModes.add(bootMode);
        saveProvisional();
      }
      applyTabMarks(visitedUnion());
      applyTracker(visitedUnion());
      maybeUnlockProvisionalDone();
      // The server-rendered claim panel re-validates the mode gate on POST.
      const claimModes = document.querySelector("[data-claim-modes]");
      if (claimModes) {
        claimModes.value = Array.from(provisionalModes).join(",");
      }
    }

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

    // Honor server-rendered mode (e.g. hard navigation to ?mode=…).
    // Reset interactive panels when landing on them.
    const mode = learn.dataset.mode || "read";
    if (mode === "card") {
      setFlipped(false);
    }
    if (mode === "cloze" && cloze) {
      cloze.reset();
    }
    if (mode === "letters" && letters) {
      letters.reset();
    }
    if (mode === "type" && typeMode) {
      typeMode.reset();
    }
    if (mode === "recite" && recite) {
      recite.reset();
    }

    if (doneBtn) {
      const unlocked = learn.dataset.doneUnlocked === "true";
      doneBtn.disabled = !unlocked;
      if (unlocked) {
        doneBtn.removeAttribute("disabled");
      } else {
        doneBtn.setAttribute("disabled", "disabled");
      }
    }
  }

  function initBrowseArticle() {
    const root = document.querySelector(".browse-article [data-bare-fn-root]");
    if (!root) {
      return;
    }
    initBareFns(root);
  }

  function cardHasMark(card, key) {
    const raw = card.getAttribute("data-browse-marks") || "";
    return raw.split(/\s+/).filter(Boolean).indexOf(key) !== -1;
  }

  function initBrowseIndex() {
    const panel = document.querySelector("section.browse");
    if (!panel) {
      return;
    }
    const cards = Array.from(panel.querySelectorAll(".browse-article-card"));
    const legendItems = Array.from(panel.querySelectorAll(".browse-legend-item"));
    let active = null;

    function applyFilter(next) {
      if (next && next === active) {
        active = null;
      } else {
        active = next || null;
      }
      if (active) {
        panel.setAttribute("data-mark-filter", active);
      } else {
        panel.removeAttribute("data-mark-filter");
      }
      legendItems.forEach((item) => {
        item.setAttribute(
          "aria-pressed",
          item.getAttribute("data-browse-filter") === active ? "true" : "false"
        );
      });
      cards.forEach((card) => {
        const hide = Boolean(active) && !cardHasMark(card, active);
        card.classList.toggle("is-mark-hidden", hide);
      });
      panel.querySelectorAll(".browse-chapter").forEach((chapter) => {
        const visible = chapter.querySelectorAll(
          ".browse-article-card:not(.is-mark-hidden)"
        );
        chapter.classList.toggle("is-filter-empty", Boolean(active) && visible.length === 0);
      });
      panel.querySelectorAll(".browse-part").forEach((part) => {
        const visible = part.querySelectorAll(
          ".browse-article-card:not(.is-mark-hidden)"
        );
        part.classList.toggle("is-filter-empty", Boolean(active) && visible.length === 0);
      });
    }

    panel.addEventListener("click", (event) => {
      const trigger = event.target.closest("[data-browse-filter]");
      if (!trigger || !panel.contains(trigger)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      applyFilter(trigger.getAttribute("data-browse-filter"));
    });
  }

  function wait(ms) {
    return new Promise(function (resolve) {
      window.setTimeout(resolve, ms);
    });
  }

  function getDoneAudio() {
    if (!doneAudio) {
      doneAudio = new Audio(DONE_SOUND_SRC);
      doneAudio.preload = "auto";
    }
    return doneAudio;
  }

  function ensureAudio() {
    const audio = getDoneAudio();
    // Unlock playback under the Done click; stay silent until persist confirms.
    audio.muted = true;
    const playing = audio.play();
    if (playing && playing.then) {
      playing
        .then(function () {
          audio.pause();
          audio.currentTime = 0;
          audio.muted = false;
        })
        .catch(function () {
          audio.muted = false;
        });
    } else {
      audio.muted = false;
    }
    return audio;
  }

  function playCompletionSound() {
    return new Promise(function (resolve) {
      const audio = getDoneAudio();
      let settled = false;
      function finish() {
        if (settled) {
          return;
        }
        settled = true;
        audio.removeEventListener("ended", finish);
        audio.removeEventListener("error", finish);
        resolve();
      }
      audio.muted = false;
      try {
        audio.currentTime = 0;
      } catch (_e) {
        /* ignore */
      }
      audio.addEventListener("ended", finish);
      audio.addEventListener("error", finish);
      const playing = audio.play();
      if (playing && playing.catch) {
        playing.catch(finish);
      }
      window.setTimeout(finish, 2300);
    });
  }

  function cleanDoneParam(urlString) {
    const u = new URL(urlString, window.location.origin);
    u.searchParams.delete("done");
    return u.pathname + u.search + u.hash;
  }

  function showNotConfirmed(root) {
    const host = root || document.querySelector(".learn") || document.querySelector("main") || document.body;
    if (host.querySelector(".rtc-not-confirmed")) {
      return;
    }
    const box = document.createElement("div");
    box.className = "rtc-not-confirmed";
    box.setAttribute("role", "status");
    box.setAttribute("aria-live", "polite");
    box.innerHTML =
      '<p class="rtc-not-confirmed-eyebrow">Not confirmed</p>' +
      "<p>Could not confirm whether this review was saved. Reload to check your progress.</p>" +
      '<button type="button" class="rtc-not-confirmed-reload">Reload</button>';
    const reload = box.querySelector(".rtc-not-confirmed-reload");
    reload.addEventListener("click", function () {
      window.location.reload();
    });
    host.insertBefore(box, host.firstChild);
  }

  function buildAffirmationEl(payload) {
    const quote = payload.quote || {};
    const continueLabel = payload.continue_label
      ? "Continue to " + payload.continue_label
      : "Continue";
    const wrap = document.createElement("div");
    wrap.className = "rtc-affirmation";
    wrap.setAttribute("data-rtc-completion", "");
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-modal", "true");
    wrap.setAttribute("aria-live", "polite");
    wrap.innerHTML =
      '<div class="rtc-affirmation-scrim" data-rtc-advance tabindex="-1"></div>' +
      '<div class="rtc-affirmation-card">' +
      '<p class="rtc-affirmation-eyebrow"></p>' +
      '<blockquote class="rtc-affirmation-quote" id="rtc-affirmation-quote"></blockquote>' +
      '<p class="rtc-affirmation-attr"></p>' +
      '<p class="rtc-affirmation-ledger"><span></span><span></span></p>' +
      '<div class="rtc-affirmation-actions">' +
      '<a class="rtc-affirmation-continue" data-rtc-advance href="#"></a>' +
      '<span class="rtc-affirmation-esc">Esc</span></div>' +
      '<div class="rtc-affirmation-hold" aria-hidden="true"></div></div>';
    wrap.querySelector(".rtc-affirmation-eyebrow").textContent = payload.eyebrow || "Review complete";
    wrap.querySelector(".rtc-affirmation-quote").textContent = quote.text || "";
    wrap.querySelector(".rtc-affirmation-attr").textContent = quote.author ? "— " + quote.author : "";
    const ledger = wrap.querySelectorAll(".rtc-affirmation-ledger span");
    ledger[0].textContent = payload.article_ref || "";
    ledger[1].textContent = payload.ledger || "";
    const link = wrap.querySelector(".rtc-affirmation-continue");
    link.textContent = continueLabel;
    link.setAttribute("href", cleanDoneParam(payload.next_url || "/"));
    return wrap;
  }

  function holdAffirmation(el) {
    return new Promise(function (resolve) {
      let settled = false;
      function finish(event) {
        if (settled) {
          return;
        }
        if (event && event.type === "click" && event.currentTarget.tagName === "A") {
          event.preventDefault();
        }
        settled = true;
        window.clearTimeout(timer);
        document.removeEventListener("keydown", onKey);
        el.classList.add("is-exiting");
        el.classList.remove("is-holding");
        window.setTimeout(resolve, motionEnabled() ? 200 : 0);
      }
      function onKey(event) {
        if (event.key === "Escape") {
          finish();
        }
      }
      el.querySelectorAll("[data-rtc-advance]").forEach(function (node) {
        node.addEventListener("click", finish);
      });
      document.addEventListener("keydown", onKey);
      el.classList.add("is-open", "is-holding");
      const timer = window.setTimeout(finish, AFFIRMATION_HOLD_MS);
    });
  }

  async function presentAffirmation(el, nextUrl) {
    if (!el.isConnected) {
      document.body.appendChild(el);
    }
    await holdAffirmation(el);
    el.remove();
    if (nextUrl) {
      window.location.assign(cleanDoneParam(nextUrl));
    }
  }

  async function initServerAffirmation() {
    const el = document.querySelector("[data-rtc-completion]");
    if (!el) {
      return;
    }
    const u = new URL(window.location.href);
    u.searchParams.delete("done");
    window.history.replaceState(null, "", u.pathname + u.search + u.hash);
    const href = el.querySelector(".rtc-affirmation-continue");
    const nextUrl = href ? href.getAttribute("href") : u.pathname + u.search + u.hash;
    await presentAffirmation(el, nextUrl);
  }

  function buildClaimDialog(payload) {
    const article = String(payload.article_number || "");
    const slots = Number(payload.slots_remaining || 0);
    const dialog = document.createElement("dialog");
    dialog.className = "guest-modal claim-modal";
    dialog.setAttribute("aria-labelledby", "claim-modal-title");
    dialog.innerHTML =
      '<div class="guest-modal-card">' +
      '<h2 class="guest-modal-title" id="claim-modal-title"></h2>' +
      '<p class="guest-modal-body"></p>' +
      '<div class="guest-modal-actions">' +
      '<button type="button" class="btn" data-claim-confirm></button>' +
      '<button type="button" class="btn btn-ghost" data-claim-dismiss>Not now</button>' +
      "</div>" +
      '<p class="claim-modal-note"></p>' +
      "</div>";
    dialog.querySelector(".guest-modal-title").textContent =
      "Add Article " + article + " to your Free Articles?";
    dialog.querySelector(".guest-modal-body").textContent =
      "Article " + article + " and all its clauses will count as 1 of your 3 permanent " +
      "Free Articles. You’ll keep its progress and scheduled revisions.";
    dialog.querySelector("[data-claim-confirm]").textContent = "Add Article " + article;
    dialog.querySelector(".claim-modal-note").textContent =
      slots + " of 3 Free Article slot" + (slots === 1 ? "" : "s") + " remaining.";
    return dialog;
  }

  function confirmClaim(payload) {
    return new Promise(function (resolve) {
      const dialog = buildClaimDialog(payload);
      document.body.appendChild(dialog);
      let settled = false;
      function finish(confirmed) {
        if (settled) {
          return;
        }
        settled = true;
        try {
          dialog.close();
        } catch (_e) {
          /* ignore */
        }
        dialog.remove();
        resolve(confirmed);
      }
      dialog.querySelector("[data-claim-confirm]").addEventListener("click", function () {
        finish(true);
      });
      dialog.querySelector("[data-claim-dismiss]").addEventListener("click", function () {
        finish(false);
      });
      dialog.addEventListener("cancel", function () {
        finish(false);
      });
      if (typeof dialog.showModal === "function") {
        dialog.showModal();
      } else {
        dialog.setAttribute("open", "");
      }
    });
  }

  function initDoneInterceptor() {
    const form = document.querySelector("form.learn-action-done");
    if (!form) {
      return;
    }
    const btn = form.querySelector("#learn-done-btn") || form.querySelector("button[type='submit']");
    let fetchAttempted = false;

    function restoreButton(original) {
      btn.classList.remove("is-rtc-saving");
      btn.textContent = original;
      btn.disabled = false;
    }

    async function postDone(extraFields) {
      const body = new FormData(form);
      // Unclaimed Articles track mode visits provisionally (sessionStorage);
      // the Done POST carries that list so the server can validate the gate.
      const learnEl = form.closest(".learn");
      if (learnEl && learnEl.getAttribute("data-seen-provisional") === "true") {
        const unit = learnEl.getAttribute("data-unit-id") || "";
        let provisional = "";
        try {
          provisional = sessionStorage.getItem("cm-provisional:" + unit) || "";
        } catch (_e) {
          /* ignore */
        }
        if (provisional) {
          body.set("modes", provisional);
        }
      }
      if (extraFields) {
        Object.keys(extraFields).forEach(function (key) {
          body.set(key, extraFields[key]);
        });
      }
      const response = await fetch(form.getAttribute("action"), {
        method: "POST",
        headers: {
          Accept: "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: body,
      });
      const type = response.headers.get("content-type") || "";
      if (!type.includes("application/json")) {
        return null;
      }
      return response.json();
    }

    async function celebrate(payload) {
      btn.classList.remove("is-rtc-saving");
      btn.classList.add("is-rtc-saved");
      btn.textContent = "Saved";
      const soundP = soundEnabled() ? playCompletionSound() : Promise.resolve();
      await wait(motionEnabled() ? 120 : 0);
      const modal = buildAffirmationEl(payload);
      await presentAffirmation(modal, null);
      await soundP;
      window.location.assign(cleanDoneParam(payload.next_url));
    }

    function surfaceError(payload, original) {
      showNotConfirmed(form.closest(".learn"));
      const box = document.querySelector(".rtc-not-confirmed p:not(.rtc-not-confirmed-eyebrow)");
      if (box && payload && payload.error === "modes_incomplete") {
        box.textContent = "All six methods need a visit before Done can save.";
      } else if (box && payload && payload.error === "subscription_required") {
        box.textContent =
          "Your 3 Free Articles are in use, so this review can’t be saved on the Free plan.";
      } else if (box && payload && payload.error && payload.error !== "sign_in_required") {
        box.textContent = String(payload.error);
      }
      restoreButton(original);
    }

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      if (!btn || btn.disabled) {
        return;
      }
      if (fetchAttempted) {
        return;
      }
      fetchAttempted = true;
      ensureAudio();
      const original = btn.textContent;
      btn.disabled = true;
      btn.classList.add("is-rtc-saving");
      btn.textContent = "Saving…";
      try {
        let payload = await postDone(null);
        if (!payload) {
          showNotConfirmed(form.closest(".learn"));
          restoreButton(original);
          return;
        }
        if (!payload.ok && payload.error === "claim_required") {
          const confirmed = await confirmClaim(payload);
          if (!confirmed) {
            // "Not now" — nothing persisted; the learner may press Done again.
            restoreButton(original);
            fetchAttempted = false;
            return;
          }
          // User-confirmed second action (not an auto-retry).
          payload = await postDone({ claim_article: "1" });
          if (!payload) {
            showNotConfirmed(form.closest(".learn"));
            restoreButton(original);
            return;
          }
        }
        if (!payload.ok) {
          surfaceError(payload, original);
          return;
        }
        await celebrate(payload);
      } catch (_err) {
        showNotConfirmed(form.closest(".learn"));
        restoreButton(original);
      }
    });
  }

  function initExperienceControls() {
    function stored(key, fallback) {
      try {
        const value = localStorage.getItem(key);
        return value === "on" || value === "off" ? value : fallback;
      } catch (_e) {
        return fallback;
      }
    }
    function persist(key, value) {
      try {
        localStorage.setItem(key, value);
      } catch (_e) {
        /* ignore */
      }
    }

    const motionPref = stored(MOTION_KEY, "on");
    const soundPref = stored(SOUND_KEY, "on");
    document.querySelectorAll("[data-motion-set]").forEach(function (el) {
      const on = el.getAttribute("data-motion-set") === motionPref;
      el.classList.toggle("is-active", on);
      el.setAttribute("aria-pressed", on ? "true" : "false");
      el.addEventListener("click", function () {
        if (prefersReducedMotion()) {
          return;
        }
        const next = el.getAttribute("data-motion-set");
        persist(MOTION_KEY, next);
        document.querySelectorAll("[data-motion-set]").forEach(function (btn) {
          const active = btn.getAttribute("data-motion-set") === next;
          btn.classList.toggle("is-active", active);
          btn.setAttribute("aria-pressed", active ? "true" : "false");
        });
        syncRtcAnim();
      });
    });
    document.querySelectorAll("[data-sound-set]").forEach(function (el) {
      const on = el.getAttribute("data-sound-set") === soundPref;
      el.classList.toggle("is-active", on);
      el.setAttribute("aria-pressed", on ? "true" : "false");
      el.addEventListener("click", function () {
        const next = el.getAttribute("data-sound-set");
        persist(SOUND_KEY, next);
        document.querySelectorAll("[data-sound-set]").forEach(function (btn) {
          const active = btn.getAttribute("data-sound-set") === next;
          btn.classList.toggle("is-active", active);
          btn.setAttribute("aria-pressed", active ? "true" : "false");
        });
      });
    });

    const motionRow = document.querySelector('[data-experience-row="motion"]');
    const note = document.querySelector("[data-motion-note]");
    if (prefersReducedMotion() && motionRow) {
      motionRow.classList.add("is-os-reduced");
      if (note) {
        note.textContent = "Following your system — reduced motion is on.";
      }
    }
    syncRtcAnim();
  }

  function initPricing() {
    const root = document.querySelector("[data-pricing]");
    if (!root) {
      return;
    }
    let plans = [];
    try {
      const data = document.getElementById("pricing-data");
      plans = data ? JSON.parse(data.textContent || "[]") : [];
    } catch (_e) {
      return; // fall back to full-page navigation via the pill links
    }
    const byDays = {};
    plans.forEach(function (plan) {
      byDays[String(plan.days)] = plan;
    });
    const pills = Array.from(root.querySelectorAll("[data-pricing-days]"));
    const els = {
      title: root.querySelector("[data-pricing-title]"),
      price: root.querySelector("[data-pricing-price]"),
      perday: root.querySelector("[data-pricing-perday]"),
      tagline: root.querySelector("[data-pricing-tagline]"),
      annotation: root.querySelector("[data-pricing-annotation]"),
      journey: root.querySelector("[data-pricing-journey]"),
      cta: root.querySelector("[data-pricing-cta]"),
      ctaNote: root.querySelector("[data-pricing-cta-note]"),
      billing: root.querySelector("[data-pricing-billing]"),
    };

    function select(days) {
      const plan = byDays[String(days)];
      if (!plan) {
        return;
      }
      root.setAttribute("data-selected-days", String(plan.days));
      pills.forEach(function (pill) {
        const active = pill.getAttribute("data-pricing-days") === String(plan.days);
        pill.classList.toggle("is-selected", active);
        pill.setAttribute("aria-checked", active ? "true" : "false");
      });
      if (els.title) {
        els.title.textContent = plan.days + "-Day Recall";
      }
      if (els.price) {
        els.price.textContent = "₹" + plan.price_inr;
      }
      if (els.perday) {
        els.perday.textContent = "₹" + plan.per_day.toFixed(2) + " / day";
      }
      if (els.tagline) {
        els.tagline.textContent = plan.tagline;
      }
      if (els.annotation) {
        els.annotation.textContent = plan.annotation || "";
        els.annotation.hidden = !plan.annotation;
      }
      if (els.journey) {
        els.journey.hidden = plan.days !== 180;
      }
      if (els.cta) {
        els.cta.textContent = "Start my " + plan.days + " days →";
      }
      if (els.ctaNote) {
        els.ctaNote.hidden = true;
      }
      if (els.billing) {
        els.billing.textContent = plan.billing_line;
      }
      // Update only the d param — preserve any other query params and hash.
      const u = new URL(window.location.href);
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
        let target = null;
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
        const more = root.querySelector("[data-pricing-more]");
        if (more && more.hidden && more.contains(target)) {
          more.hidden = false;
          const toggle = root.querySelector("[data-pricing-more-toggle]");
          if (toggle) {
            toggle.setAttribute("aria-expanded", "true");
          }
        }
        select(target.getAttribute("data-pricing-days"));
        target.focus();
      });
    });

    const moreToggle = root.querySelector("[data-pricing-more-toggle]");
    const moreRail = root.querySelector("[data-pricing-more]");
    if (moreToggle && moreRail) {
      moreToggle.addEventListener("click", function () {
        const open = moreRail.hidden;
        moreRail.hidden = !open;
        moreToggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }

    if (els.cta && els.ctaNote) {
      els.cta.addEventListener("click", function () {
        // No purchase flow yet — quiet inline note, never a dead-end page.
        els.ctaNote.hidden = false;
      });
    }
  }

  function bootInteraction() {
    syncRtcAnim();
    getDoneAudio();
    initHeadingReveal();
    initDoneInterceptor();
    initServerAffirmation();
    initExperienceControls();
    initPricing();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      initLearn();
      initBrowseArticle();
      initBrowseIndex();
      initExplainBack();
      initThemeToggle();
      bootInteraction();
    });
  } else {
    initLearn();
    initBrowseArticle();
    initBrowseIndex();
    initExplainBack();
    initThemeToggle();
    bootInteraction();
  }

  function wordCount(text) {
    const trimmed = text.trim();
    return trimmed ? trimmed.split(/\s+/).length : 0;
  }

  function initExplainBack() {
    const root = document.querySelector("[data-gloss-article]");
    if (!root) {
      return;
    }
    const article = root.getAttribute("data-gloss-article");
    const input = root.querySelector("[data-gloss-input]");
    const meta = root.querySelector("[data-gloss-meta]");
    const clearBtn = root.querySelector("[data-gloss-clear]");
    if (!article || !input || !meta || !clearBtn) {
      return;
    }

    const emptyHint =
      "Saved automatically — rewrite it whenever your understanding sharpens.";
    let timer = null;
    let lastSaved = input.value;

    function renderMeta(text) {
      const n = wordCount(text);
      if (n === 0) {
        meta.textContent = emptyHint;
        clearBtn.hidden = true;
      } else {
        meta.textContent = n + " word" + (n === 1 ? "" : "s") + " · saved";
        clearBtn.hidden = false;
      }
    }

    function persist(text) {
      const trimmed = text.trim();
      if (!trimmed) {
        return fetch("/browse/article/" + encodeURIComponent(article) + "/gloss", {
          method: "DELETE",
        }).then(() => {
          lastSaved = "";
          renderMeta("");
        });
      }
      return fetch("/browse/article/" + encodeURIComponent(article) + "/gloss", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text }),
      }).then((res) => {
        if (!res.ok) {
          throw new Error("save failed");
        }
        lastSaved = text;
        renderMeta(text);
      });
    }

    function scheduleSave() {
      if (timer) {
        clearTimeout(timer);
      }
      timer = setTimeout(() => {
        timer = null;
        const value = input.value;
        if (value === lastSaved) {
          renderMeta(value);
          return;
        }
        persist(value).catch(() => {
          meta.textContent = "Couldn’t save — try again.";
        });
      }, 500);
    }

    input.addEventListener("input", () => {
      const value = input.value;
      const n = wordCount(value);
      if (n === 0) {
        meta.textContent = emptyHint;
        clearBtn.hidden = true;
      } else {
        meta.textContent = n + " word" + (n === 1 ? "" : "s") + " · saving…";
        clearBtn.hidden = false;
      }
      scheduleSave();
    });

    clearBtn.addEventListener("click", () => {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      input.value = "";
      persist("").catch(() => {
        meta.textContent = "Couldn’t clear — try again.";
      });
    });
  }

  function initThemeToggle() {
    const btn = document.getElementById("theme-toggle");
    const KEY = "cm-theme";
    const CYCLE = ["auto", "dark", "light"];
    const LABELS = {
      auto: "◐ Auto",
      dark: "● Dark",
      light: "○ Light",
    };

    function systemDark() {
      return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    }

    function effective(pref) {
      if (pref === "dark") return "dark";
      if (pref === "light") return "light";
      return systemDark() ? "dark" : "light";
    }

    function persist(pref) {
      const body = new URLSearchParams();
      body.set("theme", pref);
      fetch("/api/theme", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString(),
      }).catch(() => {
        /* ignore */
      });
    }

    function syncSettingsButtons(pref) {
      document.querySelectorAll("[data-theme-set]").forEach((el) => {
        const on = el.getAttribute("data-theme-set") === pref;
        el.classList.toggle("is-active", on);
        el.setAttribute("aria-pressed", on ? "true" : "false");
      });
    }

    function apply(pref) {
      const resolved = effective(pref);
      document.documentElement.setAttribute("data-theme", resolved);
      document.documentElement.setAttribute("data-theme-preference", pref);
      document.documentElement.style.colorScheme = resolved;
      if (btn) {
        btn.dataset.themePref = pref;
        btn.textContent = LABELS[pref] || LABELS.auto;
      }
      syncSettingsButtons(pref);
      try {
        localStorage.setItem(KEY, pref);
      } catch (_e) {
        /* ignore */
      }
    }

    let pref = (btn && btn.dataset.themePref) || "auto";
    try {
      const stored = localStorage.getItem(KEY);
      if (stored === "auto" || stored === "dark" || stored === "light") {
        pref = stored;
      }
    } catch (_e) {
      /* ignore */
    }
    apply(pref);

    if (btn) {
      btn.addEventListener("click", () => {
        const current = btn.dataset.themePref || "auto";
        const idx = CYCLE.indexOf(current);
        const next = CYCLE[(idx + 1) % CYCLE.length];
        apply(next);
        persist(next);
      });
    }

    document.querySelectorAll("[data-theme-set]").forEach((el) => {
      el.addEventListener("click", () => {
        const next = el.getAttribute("data-theme-set");
        if (next !== "auto" && next !== "dark" && next !== "light") {
          return;
        }
        apply(next);
        persist(next);
      });
    });

    if (window.matchMedia) {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const onChange = () => {
        const current = (btn && btn.dataset.themePref) || document.documentElement.getAttribute("data-theme-preference") || "auto";
        if (current === "auto") {
          apply("auto");
        }
      };
      if (typeof mq.addEventListener === "function") {
        mq.addEventListener("change", onChange);
      } else if (typeof mq.addListener === "function") {
        mq.addListener(onChange);
      }
    }
  }
})();
