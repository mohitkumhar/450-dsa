function loadUnreadCount() {
    fetch('/api/notifications/unread-count')
        .then(r => r.json())
        .then(data => {
            const badge = document.getElementById('notif-badge');
            if (!badge) return;
            if (data.count > 0) {
                badge.textContent = data.count;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        }).catch(() => {});
}

function loadNotifications() {
    fetch('/api/notifications')
        .then(r => r.json())
        .then(notifications => {
            const list = document.getElementById('notif-list');
            if (!list) return;
            if (notifications.length === 0) {
                list.innerHTML = '<p style="padding:16px; color:var(--text-muted);">No notifications yet.</p>';
                return;
            }
            function loadNotifications() {
    fetch('/api/notifications')
        .then(r => r.json())
        .then(notifications => {
            const list = document.getElementById('notif-list');
            if (!list) return;
            list.innerHTML = '';
            if (notifications.length === 0) {
                const p = document.createElement('p');
                p.style.cssText = 'padding:16px;color:var(--text-muted)';
                p.textContent = 'No notifications yet.';
                list.appendChild(p);
                return;
            }
            notifications.forEach(n => {
                const div = document.createElement('div');
                div.style.cssText = `padding:12px 16px;border-bottom:1px solid var(--border);background:${n.read ? 'transparent' : 'var(--hover-bg)'};cursor:pointer;`;
                div.onclick = () => markRead(n.id, div);

                const msg = document.createElement('div');
                msg.style.fontSize = '0.9rem';
                msg.textContent = n.message;

                const time = document.createElement('div');
                time.style.cssText = 'font-size:0.75rem;color:var(--text-muted);margin-top:4px';
                time.textContent = new Date(n.created_at).toLocaleString();

                div.appendChild(msg);
                div.appendChild(time);
                list.appendChild(div);
            });
        }).catch(() => {});
}
        }).catch(() => {});
}

function markAllRead() {
    const token = document.querySelector('meta[name="csrf-token"]');
    fetch('/api/notifications/mark-all-read', {
        method: 'POST',
        headers: {
            'X-CSRFToken': token ? token.content : '',
            'X-Requested-With': 'XMLHttpRequest'
        }
    }).then(() => { loadUnreadCount(); loadNotifications(); });
}

function markRead(id, el) {
    const token = document.querySelector('meta[name="csrf-token"]');
    fetch(`/api/notifications/${id}/read`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': token ? token.content : '',
            'X-Requested-With': 'XMLHttpRequest'
        }
    }).then(() => {
        el.style.background = 'transparent';
        loadUnreadCount();
    });
}

document.addEventListener('DOMContentLoaded', function () {
    const notifBtn = document.getElementById('notif-btn');
    const notifDropdown = document.getElementById('notif-dropdown');
    if (!notifBtn || !notifDropdown) return;

    notifBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (notifDropdown.style.display === 'none') {
            notifDropdown.style.display = 'block';
            loadNotifications();
            markAllRead();
        } else {
            notifDropdown.style.display = 'none';
        }
    });

    document.addEventListener('click', function (e) {
        if (!notifBtn.contains(e.target) && !notifDropdown.contains(e.target)) {
            notifDropdown.style.display = 'none';
        }
    });

    loadUnreadCount();
    setInterval(loadUnreadCount, 60000);
});
