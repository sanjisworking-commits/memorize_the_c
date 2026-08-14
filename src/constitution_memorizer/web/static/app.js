/* Light progressive enhancement for the learning UI. */
(function () {
  const LEARN_MODES = new Set(["read", "cloze", "letters", "type", "recite", "card"]);
  const MOTION_KEY = "cm-motion";
  const SOUND_KEY = "cm-completion-sound";
  const DONE_SOUND_SRC = "/static/completion-done.mp3";
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

    // Mode tabs use normal <a href="?mode="> navigation so each visit is
    // recorded by GET /learn/... and Done unlocks when Card completes the set.

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
      const timer = window.setTimeout(finish, 6000);
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

  function initDoneInterceptor() {
    const form = document.querySelector("form.learn-action-done");
    if (!form) {
      return;
    }
    const btn = form.querySelector("#learn-done-btn") || form.querySelector("button[type='submit']");
    let fetchAttempted = false;
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
        const response = await fetch(form.getAttribute("action"), {
          method: "POST",
          headers: {
            Accept: "application/json",
            "X-Requested-With": "XMLHttpRequest",
          },
          body: new FormData(form),
        });
        const type = response.headers.get("content-type") || "";
        if (!type.includes("application/json")) {
          showNotConfirmed(form.closest(".learn"));
          btn.classList.remove("is-rtc-saving");
          btn.textContent = original;
          btn.disabled = false;
          return;
        }
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          const msg = payload && payload.error ? String(payload.error) : "Could not save this review.";
          showNotConfirmed(form.closest(".learn"));
          const box = document.querySelector(".rtc-not-confirmed p:not(.rtc-not-confirmed-eyebrow)");
          if (box && payload && payload.error === "modes_incomplete") {
            box.textContent = "All six methods need a visit before Done can save.";
          } else if (box && msg && payload.error !== "sign_in_required") {
            box.textContent = msg;
          }
          btn.classList.remove("is-rtc-saving");
          btn.textContent = original;
          btn.disabled = false;
          return;
        }
        btn.classList.remove("is-rtc-saving");
        btn.classList.add("is-rtc-saved");
        btn.textContent = "Saved";
        const soundP = soundEnabled() ? playCompletionSound() : Promise.resolve();
        await wait(motionEnabled() ? 120 : 0);
        const modal = buildAffirmationEl(payload);
        await presentAffirmation(modal, null);
        await soundP;
        window.location.assign(cleanDoneParam(payload.next_url));
      } catch (_err) {
        showNotConfirmed(form.closest(".learn"));
        btn.classList.remove("is-rtc-saving");
        btn.textContent = original;
        btn.disabled = false;
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

  function bootInteraction() {
    syncRtcAnim();
    getDoneAudio();
    initHeadingReveal();
    initDoneInterceptor();
    initServerAffirmation();
    initExperienceControls();
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
