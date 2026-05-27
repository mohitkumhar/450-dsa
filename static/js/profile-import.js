window.openImportModal = function() {
  document.getElementById('importModal').classList.add('open');
  document.getElementById('importFile').value = '';
  document.getElementById('importPreviewContainer').style.display = 'none';
  const btn = document.getElementById('btnConfirmImport');
  btn.disabled = true;
  btn.style.opacity = '0.6';
  btn.style.cursor = 'not-allowed';
};

window.closeImportModal = function() {
  document.getElementById('importModal').classList.remove('open');
};

let selectedImportFile = null;

window.handleImportFileSelect = function(event) {
  const file = event.target.files[0];
  if (!file) return;
  selectedImportFile = file;

  const formData = new FormData();
  formData.append('file', file);

  const container = document.getElementById('importPreviewContainer');
  container.style.display = 'none';

  showToast('⏳ Analyzing file...', 'info');

  fetch(endpointConfig.importPreview, {
    method: 'POST',
    headers: {
      'X-CSRFToken': csrfToken
    },
    body: formData
  })
  .then(r => r.json())
  .then(res => {
    if (res.success) {
      document.getElementById('previewTotal').textContent = res.summary.total_records;
      document.getElementById('previewMatched').textContent = res.summary.matched_records;
      document.getElementById('previewUnmatched').textContent = res.summary.unmatched_records;
      document.getElementById('previewChanges').textContent = res.summary.changes_detected;
      document.getElementById('previewConflicts').textContent = res.summary.conflicts_detected;

      const listEl = document.getElementById('previewList');
      listEl.innerHTML = '';
      if (res.changes.length > 0) {
        res.changes.forEach(item => {
          const li = document.createElement('li');
          li.style.marginBottom = '4px';
          li.innerHTML = `<strong>${item.problem}</strong>: ${item.change}`;
          listEl.appendChild(li);
        });
        document.getElementById('previewItemsList').style.display = 'block';
      } else {
        document.getElementById('previewItemsList').style.display = 'none';
      }

      container.style.display = 'block';
      const btn = document.getElementById('btnConfirmImport');
      btn.disabled = false;
      btn.style.opacity = '1';
      btn.style.cursor = 'pointer';
      showToast('✅ File analyzed successfully!', 'success');
    } else {
      showToast('❌ Analysis failed: ' + (res.error || 'unknown error'), 'danger');
    }
  })
  .catch(err => {
    showToast('❌ Network error analyzing file', 'danger');
    console.error(err);
  });
};

window.handleConfirmImport = function(btn) {
  if (!selectedImportFile) return;
  const contentEl = document.getElementById('confirmImportBtnContent');
  
  const mode = document.querySelector('input[name="importMode"]:checked').value;
  
  const formData = new FormData();
  formData.append('file', selectedImportFile);
  formData.append('mode', mode);

  window.setButtonBusyState(btn, contentEl, { busy: true, busyLabel: 'Importing...' });

  fetch(endpointConfig.importCommit, {
    method: 'POST',
    headers: {
      'X-CSRFToken': csrfToken
    },
    body: formData
  })
  .then(r => r.json())
  .then(res => {
    if (res.success) {
      showToast('✅ Progress imported successfully! Reloading...', 'success');
      setTimeout(() => window.location.reload(), 1500);
    } else {
      showToast('❌ Import failed: ' + (res.error || 'unknown error'), 'danger');
      window.setButtonBusyState(btn, contentEl, { busy: false });
    }
  })
  .catch(err => {
    showToast('❌ Network error importing progress', 'danger');
    window.setButtonBusyState(btn, contentEl, { busy: false });
    console.error(err);
  });
};
