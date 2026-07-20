/* Light progressive enhancement for the learning UI. */
document.addEventListener("DOMContentLoaded", () => {
  const learn = document.querySelector(".learn");
  if (!learn) {
    return;
  }
  learn.classList.add("is-ready");

  const modeTabs = learn.querySelectorAll("[data-learn-mode]");
  const card = learn.querySelector(".learn-card");

  function setFlipped(flipped) {
    if (!card) {
      return;
    }
    card.dataset.flipped = flipped ? "true" : "false";
    card.classList.toggle("is-flipped", flipped);
    card.setAttribute("aria-pressed", flipped ? "true" : "false");
  }

  function setMode(mode) {
    const next = mode === "card" ? "card" : "read";
    learn.dataset.mode = next;
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
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        setFlipped(card.dataset.flipped !== "true");
      }
    });
  }
});
