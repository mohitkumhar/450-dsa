document.addEventListener("DOMContentLoaded", () => {
  const table = document.getElementById("questions-table");
  let activeQuestionId = null;

  const setActiveFromElement = (element) => {
    const row = element?.closest?.("tr[id^='row-']");
    if (!row) return;
    activeQuestionId = row.id.replace("row-", "");
  };

  const getRowIds = () =>
    Array.from(table?.querySelectorAll("tbody tr[id^='row-']") || []).map((row) => row.id.replace("row-", ""));

  const focusQuestion = (questionId) => {
    const checkbox = document.querySelector(`.status-checkbox[data-id="${questionId}"]`);
    if (checkbox) {
      checkbox.focus();
      activeQuestionId = questionId;
      return true;
    }
    return false;
  };

  const toggleControl = (selector, questionId) => {
    const control = document.querySelector(`${selector}[data-id="${questionId}"]`);
    if (control) {
      control.click();
      activeQuestionId = questionId;
      return true;
    }
    return false;
  };

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

  if (table) {
    table.addEventListener("focusin", (event) => setActiveFromElement(event.target));
    table.addEventListener("click", (event) => setActiveFromElement(event.target));
  }

  document.addEventListener("keydown", (event) => {
    if (!table || !activeQuestionId) return;

    const targetTag = event.target?.tagName?.toLowerCase();
    const isTyping = targetTag === "input" || targetTag === "textarea" || targetTag === "select" || event.target?.isContentEditable;
    if (isTyping && !["j", "k", "b", "n", "?", " "].includes(event.key)) return;

    const rowIds = getRowIds();
    const currentIndex = rowIds.indexOf(activeQuestionId);
    if (currentIndex === -1) return;

    if (event.key === "j") {
      event.preventDefault();
      focusQuestion(rowIds[Math.min(currentIndex + 1, rowIds.length - 1)]);
      return;
    }

    if (event.key === "k") {
      event.preventDefault();
      focusQuestion(rowIds[Math.max(currentIndex - 1, 0)]);
      return;
    }

    if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      toggleControl(".status-checkbox", activeQuestionId);
      return;
    }

    if (event.key === "b") {
      event.preventDefault();
      toggleControl(".bookmark-btn", activeQuestionId);
      return;
    }

    if (event.key === "n") {
      event.preventDefault();
      toggleControl(".notes-btn-sm", activeQuestionId);
      return;
    }

    if (event.key === "?") {
      event.preventDefault();
      if (typeof window.showToast === "function") {
        window.showToast("Shortcuts: j/k move, space or enter toggle done, b bookmark, n notes.", "info", 6000);
      }
    }
  });
});
