const _notifCSS = `
.notif-wrapper{position:relative;display:flex;align-items:center;justify-content:center;width:100%}
.notif-bell{background:none;border:none;cursor:pointer;color:#888;position:relative;width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.2rem;transition:background .15s,color .15s}
.notif-bell:hover{background:rgba(255,255,255,.08);color:#fff}
.notif-badge{position:absolute;top:4px;right:4px;background:#e74c3c;color:#fff;font-size:.55rem;font-weight:700;border-radius:999px;min-width:14px;height:14px;padding:0 3px;display:flex;align-items:center;justify-content:center;pointer-events:none}
.notif-dropdown{position:fixed;top:0;left:60px;height:100vh;width:320px;background:#1a1a2e;border-right:1px solid rgba(255,255,255,.08);box-shadow:4px 0 24px rgba(0,0,0,.4);z-index:1050;display:flex;flex-direction:column;overflow:hidden}
.notif-header{display:flex;align-items:center;justify-content:space-between;padding:20px 16px 14px;border-bottom:1px solid rgba(255,255,255,.08);flex-shrink:0}
.notif-title{font-weight:600;font-size:1rem;color:#fff}
.notif-mark-all{background:none;border:none;cursor:pointer;font-size:.75rem;color:#f97316;padding:0}
.notif-list{overflow-y:auto;flex:1}
.notif-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:60px 20px;color:#555;font-size:.9rem;gap:10px}
.notif-empty i{font-size:2.5rem;opacity:.3}
.notif-item{display:flex;align-items:flex-start;gap:10px;padding:12px 16px;border-bottom:1px solid rgba(255,255,255,.05);cursor:pointer;transition:background .12s;position:relative}
.notif-item:hover{background:rgba(255,255,255,.04)}
.notif-unread{background:rgba(249,115,22,.05)}
.notif-unread::before{content:"";position:absolute;left:4px;top:50%;transform:translateY(-50%);width:4px;height:4px;border-radius:50%;background:#f97316}
.notif-icon{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0}
.notif-icon-milestone{background:rgba(249,115,22,.15);color:#f97316}
.notif-icon-streak{background:rgba(239,68,68,.15);color:#ef4444}
.notif-icon-sync_failure{background:rgba(239,68,68,.15);color:#ef4444}
.notif-icon-badge{background:rgba(34,197,94,.15);color:#22c55e}
.notif-icon-goal{background:rgba(59,130,246,.15);color:#3b82f6}
.notif-icon-account{background:rgba(168,85,247,.15);color:#a855f7}
.notif-body{flex:1;min-width:0}
.notif-item-title{font-size:.82rem;font-weight:600;color:#e0e0e0;line-height:1.3;margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.notif-item-msg{font-size:.76rem;color:#777;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.notif-item-time{font-size:.7rem;color:#555;margin-top:4px}
.notif-delete{background:none;border:none;cursor:pointer;color:#444;font-size:1rem;padding:0 2px;opacity:0;transition:opacity .15s,color .15s;flex-shrink:0;align-self:center}
.notif-item:hover .notif-delete{opacity:1}
.notif-delete:hover{color:#ef4444}
`;
const _notifStyleEl = document.createElement('style');
_notifStyleEl.textContent = _notifCSS;
document.head.appendChild(_notifStyleEl);
(function injectStyles() {
  if (document.getElementById('notif-styles')) return;
  const style = document.createElement('style');
  style.id = 'notif-styles';
  style.textContent = document.currentScript?.closest('script')?.dataset?.css || '';
  document.head.appendChild(style);
})();
class NotificationCenter {
  constructor() {
    this.unreadCount = 0;
    this.notifications = [];
    this.isOpen = false;
    this.init();
  }

  init() {
    this.render();
    this.fetchUnreadCount();
    setInterval(() => { if (!this.isOpen) this.fetchUnreadCount(); }, 60000);
  }

  render() {
    const container = document.getElementById("notification-center-mount");
    if (!container) return;
    container.innerHTML = `
      <div class="notif-wrapper" id="notif-wrapper">
        <button class="notif-bell" id="notif-bell" aria-label="Notifications">
          <i class="bi bi-bell"></i>
          <span class="notif-badge" id="notif-badge" style="display:none">0</span>
        </button>
        <div class="notif-dropdown" id="notif-dropdown" style="display:none">
          <div class="notif-header">
            <span class="notif-title">Notifications</span>
            <button class="notif-mark-all" id="notif-mark-all">Mark all read</button>
          </div>
          <div class="notif-list" id="notif-list">
            <div class="notif-empty">Loading...</div>
          </div>
        </div>
      </div>`;
    document.getElementById("notif-bell").addEventListener("click", (e) => {
      e.stopPropagation();
      this.isOpen ? this.closeDropdown() : this.openDropdown();
    });
    document.getElementById("notif-mark-all").addEventListener("click", () => this.markAllRead());
    document.addEventListener("click", (e) => {
      if (!document.getElementById("notif-wrapper").contains(e.target)) this.closeDropdown();
    });
  }

  async fetchUnreadCount() {
    try {
      const res = await fetch("/notifications/unread-count", { headers: { "X-Requested-With": "XMLHttpRequest" } });
      const data = await res.json();
      if (data.success) this.updateBadge(data.unread_count);
    } catch (e) { console.error("Notification count error", e); }
  }

  async fetchNotifications() {
    try {
      const res = await fetch("/notifications/?limit=20", { headers: { "X-Requested-With": "XMLHttpRequest" } });
      const data = await res.json();
      if (data.success) { this.notifications = data.notifications; this.updateBadge(data.unread_count); this.renderList(); }
    } catch (e) { console.error("Notification fetch error", e); }
  }

  renderList() {
    const list = document.getElementById("notif-list");
    if (!list) return;
    if (this.notifications.length === 0) {
      list.innerHTML = `<div class="notif-empty"><i class="bi bi-bell-slash"></i><p>No notifications yet</p></div>`;
      return;
    }
    list.innerHTML = this.notifications.map(n => `
      <div class="notif-item ${n.is_read ? "" : "notif-unread"}" data-id="${n._id}">
        <div class="notif-icon notif-icon-${n.type}">${this.getIcon(n.type)}</div>
        <div class="notif-body">
          <div class="notif-item-title">${this.esc(n.title)}</div>
          <div class="notif-item-msg">${this.esc(n.message)}</div>
          <div class="notif-item-time">${this.timeAgo(n.created_at)}</div>
        </div>
        <button class="notif-delete" data-id="${n._id}" title="Dismiss"><i class="bi bi-x"></i></button>
      </div>`).join("");
    list.querySelectorAll(".notif-item").forEach(el => {
      el.addEventListener("click", (e) => {
        if (e.target.closest(".notif-delete")) return;
        const notif = this.notifications.find(n => n._id === el.dataset.id);
        this.markRead(el.dataset.id);
        if (notif && notif.link) window.location.href = notif.link;
      });
    });
    list.querySelectorAll(".notif-delete").forEach(btn => {
      btn.addEventListener("click", (e) => { e.stopPropagation(); this.deleteNotification(btn.dataset.id); });
    });
  }

  async markRead(id) {
    try {
      const res = await fetch(`/notifications/mark-read/${id}`, { method: "POST", headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": this.csrf() } });
      const data = await res.json();
      if (data.success) { const n = this.notifications.find(n => n._id === id); if (n) n.is_read = true; this.updateBadge(data.unread_count); this.renderList(); }
    } catch (e) { console.error(e); }
  }

  async markAllRead() {
    try {
      const res = await fetch("/notifications/mark-all-read", { method: "POST", headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": this.csrf() } });
      const data = await res.json();
      if (data.success) { this.notifications.forEach(n => n.is_read = true); this.updateBadge(0); this.renderList(); }
    } catch (e) { console.error(e); }
  }

  async deleteNotification(id) {
    try {
      const res = await fetch(`/notifications/${id}`, { method: "DELETE", headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": this.csrf() } });
      const data = await res.json();
      if (data.success) { this.notifications = this.notifications.filter(n => n._id !== id); this.updateBadge(data.unread_count); this.renderList(); }
    } catch (e) { console.error(e); }
  }

  updateBadge(count) {
    this.unreadCount = count;
    const badge = document.getElementById("notif-badge");
    if (!badge) return;
    badge.style.display = count > 0 ? "flex" : "none";
    badge.textContent = count > 99 ? "99+" : count;
  }

  openDropdown() { this.isOpen = true; document.getElementById("notif-dropdown").style.display = "block"; this.fetchNotifications(); }
  closeDropdown() { this.isOpen = false; const d = document.getElementById("notif-dropdown"); if (d) d.style.display = "none"; }

  getIcon(type) {
    return { milestone: '<i class="bi bi-trophy"></i>', streak: '<i class="bi bi-fire"></i>',
      sync_failure: '<i class="bi bi-exclamation-triangle"></i>', badge: '<i class="bi bi-award"></i>',
      goal: '<i class="bi bi-check-circle"></i>', account: '<i class="bi bi-person-circle"></i>' }[type] || '<i class="bi bi-bell"></i>';
  }

  timeAgo(iso) {
    const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
    return `${Math.floor(diff/86400)}d ago`;
  }

  esc(str) { const d = document.createElement("div"); d.textContent = str; return d.innerHTML; }
  csrf() { return document.querySelector('meta[name="csrf-token"]')?.content || ""; }
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("notification-center-mount")) {
    window.notificationCenter = new NotificationCenter();
  }
});