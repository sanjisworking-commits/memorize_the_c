/* Light progressive enhancement for the learning UI. */
(function () {
  const LEARN_MODES = new Set(["read", "cloze", "letters", "type", "recite", "card"]);
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

    function setHidden(el, hidden) {
      if (!el) {
        return;
      }
      el.hidden = hidden;
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
      setHidden(transcriptEl, true);
      setHidden(mapEl, true);
      setHidden(statsEl, true);
      setHidden(extrasEl, true);
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

    function renderAccuracyMap(spokenText) {
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
        if (heard) {
          transcriptEl.textContent = "Heard: " + heard;
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
          recognition.stop();
        } catch (_err) {
          /* ignore */
        }
        recognition = null;
      }
    }

    function finishRecite() {
      recOn = false;
      stopRecognition();
      const spoken = (finalTranscript + " " + interimTranscript).trim();
      finalTranscript = spoken;
      interimTranscript = "";
      render();
      if (spoken) {
        showStatus("Accuracy map from your recital.", null);
        renderAccuracyMap(spoken);
      } else {
        showStatus("No speech captured — try again.", "error");
        clearResults();
        setHidden(statusEl, false);
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
        if (err === "not-allowed" || err === "service-not-allowed") {
          unsupported = true;
          recOn = false;
          stopRecognition();
          showStatus(
            "Voice recite needs Chrome or Edge with microphone access.",
            "error",
          );
          if (toggle) {
            toggle.disabled = true;
          }
          render();
          return;
        }
        if (err === "no-speech") {
          showStatus("Listening… speak the Bare Act aloud.", "listening");
          return;
        }
        showStatus("Speech recognition error: " + err, "error");
      };

      recognition.onend = () => {
        if (recOn) {
          // Chrome often ends continuous sessions early — restart while active.
          try {
            recognition.start();
          } catch (_err) {
            finishRecite();
          }
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
        recOn = false;
        peeking = false;
        stopRecognition();
        clearResults();
        if (!unsupported) {
          showStatus("", null);
        } else {
          showStatus(
            "Voice recite needs Chrome or Edge with microphone access.",
            "error",
          );
        }
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
    const lettersPanel = learn.querySelector('[data-learn-panel="letters"]');
    const typePanel = learn.querySelector('[data-learn-panel="type"]');
    const recitePanel = learn.querySelector('[data-learn-panel="recite"]');
    const cloze = initCloze(clozePanel);
    const letters = initLetters(lettersPanel);
    const typeMode = initType(typePanel);
    const recite = initRecite(recitePanel);

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
      if (next === "letters" && letters) {
        letters.reset();
      }
      if (next === "type" && typeMode) {
        typeMode.reset();
      }
      if (next === "recite" && recite) {
        recite.reset();
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

    // Honor server-rendered mode (e.g. hard navigation to ?mode=…).
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
