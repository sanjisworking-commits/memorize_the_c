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

  function initLearn() {
    const learn = document.querySelector(".learn");
    if (!learn) {
      return;
    }
    learn.classList.add("is-ready");

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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      initLearn();
      initExplainBack();
      initThemeToggle();
    });
  } else {
    initLearn();
    initExplainBack();
    initThemeToggle();
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
    if (!btn) {
      return;
    }
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

    function apply(pref) {
      const resolved = effective(pref);
      document.documentElement.setAttribute("data-theme", resolved);
      document.documentElement.setAttribute("data-theme-preference", pref);
      document.documentElement.style.colorScheme = resolved;
      btn.dataset.themePref = pref;
      btn.textContent = LABELS[pref] || LABELS.auto;
      try {
        localStorage.setItem(KEY, pref);
      } catch (_e) {
        /* ignore */
      }
    }

    let pref = btn.dataset.themePref || "auto";
    try {
      const stored = localStorage.getItem(KEY);
      if (stored === "auto" || stored === "dark" || stored === "light") {
        pref = stored;
      }
    } catch (_e) {
      /* ignore */
    }
    apply(pref);

    btn.addEventListener("click", () => {
      const current = btn.dataset.themePref || "auto";
      const idx = CYCLE.indexOf(current);
      const next = CYCLE[(idx + 1) % CYCLE.length];
      apply(next);
      const body = new URLSearchParams();
      body.set("theme", next);
      fetch("/api/theme", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString(),
      }).catch(() => {
        /* ignore */
      });
    });

    if (window.matchMedia) {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const onChange = () => {
        if ((btn.dataset.themePref || "auto") === "auto") {
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
