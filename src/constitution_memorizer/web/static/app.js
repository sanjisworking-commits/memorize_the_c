/* Light progressive enhancement for the learning UI. */
document.addEventListener("DOMContentLoaded", () => {
  const learn = document.querySelector(".learn");
  if (!learn) {
    return;
  }
  learn.classList.add("is-ready");

  const modeTabs = learn.querySelectorAll("[data-learn-mode]");
  const panels = {
    read: learn.querySelector('[data-learn-panel="read"]'),
    card: learn.querySelector('[data-learn-panel="card"]'),
  };
  const card = learn.querySelector(".learn-card");
  const cardFront = learn.querySelector(".learn-card-front");
  const cardBack = learn.querySelector(".learn-card-back");

  function setFlipped(flipped) {
    if (!card || !cardFront || !cardBack) {
      return;
    }
    card.dataset.flipped = flipped ? "true" : "false";
    cardFront.hidden = flipped;
    cardBack.hidden = !flipped;
  }

  function setMode(mode) {
    if (!panels.read || !panels.card) {
      return;
    }
    const next = mode === "card" ? "card" : "read";
    learn.dataset.mode = next;
    panels.read.hidden = next !== "read";
    panels.card.hidden = next !== "card";
    modeTabs.forEach((tab) => {
      const active = tab.getAttribute("data-learn-mode") === next;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    if (next === "card") {
      setFlipped(false);
    }
  }

  modeTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      setMode(tab.getAttribute("data-learn-mode") || "read");
    });
  });

  if (card) {
    card.addEventListener("click", () => {
      setFlipped(card.dataset.flipped !== "true");
    });
  }
});
