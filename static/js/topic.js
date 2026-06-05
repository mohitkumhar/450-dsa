document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".show-hint-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const questionId = button.dataset.questionId;
      const container = document.getElementById(`hints-container-${questionId}`);
      const hints = document.querySelectorAll(`#hints-list-${questionId} .hint-item.hidden`);

      if (!hints.length) {
        button.disabled = true;
        button.textContent = "All hints shown";
        return;
      }

      hints[0].classList.remove("hidden");

      if (container) {
        const total = parseInt(container.dataset.hintsTotal || "0", 10);
        const remaining = document.querySelectorAll(`#hints-list-${questionId} .hint-item.hidden`).length;
        const revealed = total - remaining;
        container.dataset.hintsRevealed = revealed;
      }

      const remainingHints = document.querySelectorAll(`#hints-list-${questionId} .hint-item.hidden`);
      if (!remainingHints.length) {
        button.disabled = true;
        button.textContent = "All hints shown";
      }
    });
  });
});
