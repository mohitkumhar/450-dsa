document.addEventListener('DOMContentLoaded', () => {
  const dismissAlert = (alert) => {
    if (alert) {
      alert.remove();
    }
  };

  document.querySelectorAll('.dismissible-flash-alert').forEach((alert) => {
    alert.addEventListener('click', () => dismissAlert(alert));
    alert.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        dismissAlert(alert);
      }
    });
  });
});
