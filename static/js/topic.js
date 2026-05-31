(function() {
var config = JSON.parse(document.getElementById('topic-config').textContent);
var endpointConfig = config.endpointConfig;
var csrfToken = config.csrfToken;
var isAuthenticated = config.isAuthenticated;
var topicStatus = document.getElementById('topicStatus');

function showUpdateError(message) {
    message = message || 'Unable to save your change. Please try again.';
    topicStatus.textContent = message;
    window.clearTimeout(topicStatus._hideTimer);
    topicStatus._hideTimer = window.setTimeout(function() {
        topicStatus.textContent = '';
    }, 5000);
}

function setBookmarkState(btn, isBookmarked) {
    var icon = btn.querySelector('i');
    btn.dataset.bookmarked = isBookmarked ? 'true' : 'false';
    btn.setAttribute('aria-pressed', isBookmarked ? 'true' : 'false');
    btn.classList.toggle('bookmarked', isBookmarked);
    icon.className = isBookmarked ? 'bi bi-bookmark-fill' : 'bi bi-bookmark';
}

/* Offline Progress Queue */
var QUEUE_KEY = 'offlineProgressQueue';

function readQueue() {
    try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]'); }
    catch(e) { return []; }
}

function writeQueue(q) {
    try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); }
    catch(e) { /* storage full */ }
}

function enqueue(id, data) {
    var queue = readQueue();
    var idx = queue.findIndex(function(e) { return e.id === id; });
    var entry = idx >= 0 ? queue[idx] : { id: id, data: {}, ts: 0 };
    entry.data = Object.assign({}, entry.data, data);
    entry.ts = Date.now();
    if (idx >= 0) queue[idx] = entry; else queue.push(entry);
    writeQueue(queue);
}

function dequeue(id) {
    writeQueue(readQueue().filter(function(e) { return e.id !== id; }));
}

function showOfflineBanner(show) {
    var banner = document.getElementById('offlineQueueBanner');
    if (!banner) {
        banner = document.createElement('div');
        banner.id = 'offlineQueueBanner';
        banner.setAttribute('role', 'status');
        banner.setAttribute('aria-live', 'polite');
        banner.style.cssText =
            'position:fixed;bottom:16px;left:50%;transform:translateX(-50%);' +
            'background:var(--bg-secondary,#1e293b);color:var(--text-secondary,#94a3b8);' +
            'border:1px solid var(--border-color,#334155);border-radius:8px;' +
            'padding:8px 18px;font-size:0.82rem;font-weight:600;z-index:9999;' +
            'box-shadow:0 4px 16px rgba(0,0,0,0.3);transition:opacity 0.3s;';
        document.body.appendChild(banner);
    }
    if (show) {
        var count = readQueue().length;
        banner.textContent = 'Offline - ' + count + ' change' + (count !== 1 ? 's' : '') + ' queued';
        banner.style.opacity = '1';
        banner.style.display = 'block';
    } else {
        banner.style.opacity = '0';
        setTimeout(function() { banner.style.display = 'none'; }, 300);
    }
}

async function flushQueue() {
    var queue = readQueue();
    if (!queue.length) return;
    for (var i = 0; i < queue.length; i++) {
        var entry = queue[i];
        try {
            var r = await fetch(endpointConfig.updateQuestionBase.replace('__QUESTION_ID__', encodeURIComponent(entry.id)), {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                body: JSON.stringify(entry.data)
            });
            if (r.ok) {
                var res = await r.json();
                if (res.success) dequeue(entry.id);
            }
        } catch(e) {
            break;
        }
    }
    if (!readQueue().length) {
        showOfflineBanner(false);
        showUpdateError('Offline changes synced!');
    }
}

window.addEventListener('online', flushQueue);

function updateQuestion(id, data, callback) {
    if (!navigator.onLine) {
        enqueue(id, data);
        showOfflineBanner(true);
        if (callback) callback({ success: true, offline: true });
        return Promise.resolve({ success: true, offline: true });
    }

    return fetch(endpointConfig.updateQuestionBase.replace('__QUESTION_ID__', encodeURIComponent(id)), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
        body: JSON.stringify(data)
    }).then(function(r) {
        if (!r.ok) throw new Error('Request failed');
        return r.json();
    }).then(function(res) {
        if (!res.success) throw new Error(res.error || 'Update failed');
        if (callback) callback(res);
        return res;
    }).catch(function(err) {
        enqueue(id, data);
        showOfflineBanner(true);
        throw err;
    });
}

if (navigator.onLine) flushQueue();

document.querySelectorAll('.status-checkbox').forEach(function(cb) {
    cb.addEventListener('change', function() {
        if (!isAuthenticated) { 
            this.checked = !this.checked; 
            window.location.href = config.loginUrl; 
            return; 
        }
        var row = document.getElementById('row-' + this.dataset.id);
        var previousChecked = !this.checked;
        var nextChecked = this.checked;
        this.disabled = true;
        row.classList.add('row-updating');
        
        var problemName = row.querySelector('.q-name') ? row.querySelector('.q-name').textContent : 'Question';
        this.setAttribute('aria-label', nextChecked ? "Mark '" + problemName + "' as incomplete" : "Mark '" + problemName + "' as complete");
        
        row.classList.toggle('row-done', nextChecked);
        var self = this;
        updateQuestion(this.dataset.id, {done: nextChecked})
            .catch(function() {
                self.checked = previousChecked;
                row.classList.toggle('row-done', previousChecked);
                showUpdateError();
            })
            .finally(function() {
                self.disabled = false;
                row.classList.remove('row-updating');
            });
    });
});

function setSkippedState(btn, isSkipped) {
    var icon = btn.querySelector('i');
    btn.dataset.skipped = isSkipped ? 'true' : 'false';
    btn.setAttribute('aria-pressed', isSkipped ? 'true' : 'false');
    btn.classList.toggle('skipped', isSkipped);
    icon.className = isSkipped ? 'bi bi-skip-forward-fill' : 'bi bi-skip-forward';
}

document.querySelectorAll('.bookmark-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
        if (!isAuthenticated) { 
            window.location.href = config.loginUrl; 
            return; 
        }
        var isBookmarked = this.dataset.bookmarked === 'true';
        var newStatus = !isBookmarked;
        this.disabled = true;
        this.classList.add('row-updating');
        setBookmarkState(this, newStatus);
        var self = this;
        updateQuestion(this.dataset.id, {bookmark: newStatus})
            .catch(function() {
                setBookmarkState(self, isBookmarked);
                showUpdateError();
            })
            .finally(function() {
                self.disabled = false;
                self.classList.remove('row-updating');
            });
    });
});

document.querySelectorAll('.skip-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
        if (!isAuthenticated) {
            window.location.href = config.loginUrl;
            return;
        }
        var isSkipped = this.dataset.skipped === 'true';
        var nextSkipped = !isSkipped;
        var row = document.getElementById('row-' + this.dataset.id);
        var checkbox = row.querySelector('.status-checkbox');
        var previousChecked = checkbox.checked;
        this.disabled = true;
        checkbox.disabled = true;
        row.classList.add('row-updating');
        setSkippedState(this, nextSkipped);
        if (nextSkipped) {
            checkbox.checked = false;
            row.classList.remove('row-done');
        }
        var self = this;
        updateQuestion(this.dataset.id, {skipped: nextSkipped})
            .catch(function() {
                setSkippedState(self, isSkipped);
                checkbox.checked = previousChecked;
                row.classList.toggle('row-done', previousChecked);
                showUpdateError();
            })
            .finally(function() {
                self.disabled = false;
                checkbox.disabled = false;
                row.classList.remove('row-updating');
            });
    });
});

// Difficulty Filtering
document.querySelectorAll('.filter-btn[data-difficulty]').forEach(function(btn) {
    btn.addEventListener('click', function() {
        var difficulty = this.dataset.difficulty;
        var currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set('difficulty', difficulty);
        currentUrl.searchParams.set('status', config.statusFilter);
        this.classList.add('btn-busy');
        this.setAttribute('aria-busy', 'true');
        window.location.href = currentUrl.toString();
    });
});
document.querySelectorAll('.filter-btn[data-status]').forEach(function(btn) {
    btn.addEventListener('click', function() {
        var status = this.dataset.status;
        var currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set('difficulty', config.difficultyFilter);
        currentUrl.searchParams.set('status', status);
        this.classList.add('btn-busy');
        this.setAttribute('aria-busy', 'true');
        window.location.href = currentUrl.toString();
    });
});
(function() {
    var rows = document.querySelectorAll('#questions-table tbody tr:not(#empty-state-row)');
    var emptyRow = document.getElementById('empty-state-row');
    if (rows.length === 0) {
        emptyRow.style.display = '';
    }
})();

// Notes Modal with focus trap
var modal = document.getElementById('notesModal');
var FOCUSABLE = 'button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])';

function openModal(triggerEl) {
    modal.classList.add('open');
    modal._trigger = triggerEl;
    var focusable = modal.querySelectorAll(FOCUSABLE);
    if (focusable.length) focusable[0].focus();
    modal.addEventListener('keydown', trapFocus);
    var modalTitle = document.getElementById('notesModalTitle');
    if (modalTitle) {
        modalTitle.setAttribute('aria-live', 'polite');
    }
}

function closeModal() {
    modal.classList.remove('open');
    modal.removeEventListener('keydown', trapFocus);
    if (modal._trigger) modal._trigger.focus();
}

function trapFocus(e) {
    var focusable = Array.from(modal.querySelectorAll(FOCUSABLE));
    var first = focusable[0], last = focusable[focusable.length - 1];
    if (e.key === 'Tab') {
        if (e.shiftKey) { if (document.activeElement === first) { e.preventDefault(); last.focus(); } }
        else { if (document.activeElement === last) { e.preventDefault(); first.focus(); } }
    }
    if (e.key === 'Escape') closeModal();
}

document.querySelectorAll('.notes-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
        if (!isAuthenticated) { window.location.href = config.loginUrl; return; }
        document.getElementById('currentQuestionId').value = this.dataset.id;
        document.getElementById('notesTextarea').value = this.dataset.notes || '';
        openModal(this);
    });
});

document.getElementById('modalCancel').addEventListener('click', closeModal);
modal.addEventListener('click', function(e) { if (e.target === modal) closeModal(); });

document.getElementById('saveNotesBtn').addEventListener('click', function() {
    var qId = document.getElementById('currentQuestionId').value;
    var notes = document.getElementById('notesTextarea').value;
    var previousContent = this.innerHTML;
    var self = this;
    this.disabled = true;
    this.textContent = 'Saving...';
    updateQuestion(qId, {notes: notes}, function() {
        closeModal();
        var btn = document.querySelector('.notes-btn[data-id="' + qId + '"]');
        if (btn) {
            btn.dataset.notes = notes;
            btn.classList.toggle('has-notes', notes.trim() !== '');
            var label = notes.trim() ? 'Edit' : 'Add';
            btn.innerHTML = '<i class="bi bi-journal-text" aria-hidden="true"></i> ' + label;
            btn.setAttribute('aria-label', label + ' notes for this question');
        }
    }).catch(function() {
        showUpdateError('Unable to save notes. Please try again.');
    }).finally(function() {
        self.disabled = false;
        self.innerHTML = previousContent;
    });
});

// Practice Random Button
document.getElementById('practiceRandomBtn').addEventListener('click', function() {
    this.classList.add('btn-busy');
    this.setAttribute('aria-busy', 'true');
    var rows = Array.from(document.querySelectorAll('#questions-table tbody tr:not(#empty-state-row)'))
        .filter(function(row) { return row.style.display !== 'none'; });
    
    if (rows.length === 0) {
        this.classList.remove('btn-busy');
        this.removeAttribute('aria-busy');
        alert('No questions available!');
        return;
    }
    
    var randomRow = rows[Math.floor(Math.random() * rows.length)];
    randomRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
    randomRow.style.outline = '2px solid var(--accent)';
    var self = this;
    setTimeout(function() {
        randomRow.style.outline = '';
        self.classList.remove('btn-busy');
        self.removeAttribute('aria-busy');
    }, 2000);
});

})();
