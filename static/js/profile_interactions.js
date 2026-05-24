document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('profilePageRoot');
  if (!root) {
    return;
  }

  const deleteModal = document.getElementById('deleteAccountModal');
  const deletePasswordField = document.getElementById('deletePasswordField');
  const deletePasswordInput = document.getElementById('deleteAccountPassword');
  const deleteCsrfInput = document.getElementById('deleteAccountCsrfToken');

  async function prepareDeleteModal() {
    if (!deleteModal || !deleteCsrfInput || !root.dataset.deleteAccountTokenUrl) {
      if (typeof window.openDeleteModal === 'function') {
        window.openDeleteModal();
      }
      return;
    }

    const response = await fetch(root.dataset.deleteAccountTokenUrl, {
      headers: { Accept: 'application/json' },
    });
    const payload = await response.json();

    deleteCsrfInput.value = payload.csrf_token || '';
    const needsPassword = !payload.is_oauth;
    if (deletePasswordField) {
      deletePasswordField.style.display = needsPassword ? '' : 'none';
    }
    if (deletePasswordInput) {
      deletePasswordInput.required = needsPassword;
      if (!needsPassword) {
        deletePasswordInput.value = '';
      }
    }
    if (typeof window.openDeleteModal === 'function') {
      window.openDeleteModal();
    }
  }

  function replaceBrokenAwardIcon(event) {
    const img = event.currentTarget;
    const fallbackText = img.dataset.fallbackText || '🏅';
    const fallback = document.createElement('span');
    fallback.textContent = fallbackText;
    img.replaceWith(fallback);
  }

  document.querySelectorAll('.award-icon').forEach((img) => {
    img.addEventListener('error', replaceBrokenAwardIcon, { once: true });
  });

  const photoInput = document.getElementById('photoInput');
  if (photoInput && typeof window.handlePhotoUpload === 'function') {
    photoInput.addEventListener('change', window.handlePhotoUpload);
  }

  document.addEventListener('click', async (event) => {
    const trigger = event.target.closest('[data-action]');
    if (!trigger) {
      return;
    }

    switch (trigger.dataset.action) {
      case 'open-sync-modal':
        event.preventDefault();
        if (typeof window.openSyncModal === 'function') {
          window.openSyncModal();
        }
        break;
      case 'close-sync-modal':
        event.preventDefault();
        if (typeof window.closeSyncModal === 'function') {
          window.closeSyncModal();
        }
        break;
      case 'show-card-modal':
        event.preventDefault();
        if (typeof window.showCodelioCard === 'function') {
          window.showCodelioCard();
        }
        break;
      case 'close-card-modal':
        event.preventDefault();
        if (typeof window.closeCardModal === 'function') {
          window.closeCardModal();
        }
        break;
      case 'copy-progress-card-url':
        event.preventDefault();
        if (typeof window.copyProgressCardUrl === 'function') {
          window.copyProgressCardUrl();
        }
        break;
      case 'share-card':
        event.preventDefault();
        if (typeof window.showToast === 'function') {
          window.showToast('Profile card copied! 📋');
        }
        break;
      case 'open-edit-profile':
        event.preventDefault();
        if (typeof window.openEditProfile === 'function') {
          window.openEditProfile();
        }
        break;
      case 'close-edit-profile':
        event.preventDefault();
        if (typeof window.closeEditProfile === 'function') {
          window.closeEditProfile();
        }
        break;
      case 'submit-save-profile':
        event.preventDefault();
        if (typeof window.handleSaveProfile === 'function') {
          window.handleSaveProfile(trigger);
        }
        break;
      case 'quick-sync':
        event.preventDefault();
        if (typeof window.handleQuickSync === 'function') {
          window.handleQuickSync(trigger);
        }
        break;
      case 'submit-sync-profile':
        event.preventDefault();
        if (typeof window.handleSyncProfile === 'function') {
          window.handleSyncProfile(trigger);
        }
        break;
      case 'open-delete-account':
        event.preventDefault();
        await prepareDeleteModal();
        break;
      case 'close-delete-account':
        event.preventDefault();
        if (typeof window.closeDeleteModal === 'function') {
          window.closeDeleteModal();
        }
        break;
      default:
        break;
    }
  });
});
