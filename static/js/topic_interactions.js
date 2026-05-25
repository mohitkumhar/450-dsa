document.addEventListener('DOMContentLoaded', () => {
  const clearFilterBtn = document.querySelector('[data-action="clear-difficulty-filter"]');
  if (!clearFilterBtn) {
    return;
  }

  clearFilterBtn.addEventListener('click', () => {
    const allFilterBtn = document.querySelector('.filter-btn[data-difficulty="all"]');
    if (allFilterBtn) {
      allFilterBtn.click();
    }
  });
});
