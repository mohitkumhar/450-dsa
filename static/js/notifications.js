/**
 * Browser Notifications API Integration
 * Handles permission requests, preference management, and notification display
 */

const NotificationManager = {
  // Check if browser supports Notifications API
  isSupported() {
    return "Notification" in window;
  },

  // Check if service worker is supported
  isServiceWorkerSupported() {
    return "serviceWorker" in navigator;
  },

  // Get current permission status
  getPermissionStatus() {
    if (!this.isSupported()) return "unsupported";
    return Notification.permission;
  },

  // Request browser notification permission
  async requestPermission() {
    if (!this.isSupported()) {
      console.warn("Notifications not supported in this browser");
      return false;
    }

    try {
      const permission = await Notification.requestPermission();
      await this.updatePermissionStatus(permission);

      if (permission === "granted") {
        await this.registerServiceWorker();
      }

      return permission === "granted";
    } catch (error) {
      console.error("Error requesting notification permission:", error);
      return false;
    }
  },

  // Register service worker for background notifications
  async registerServiceWorker() {
    if (!this.isServiceWorkerSupported()) {
      console.warn("Service Workers not supported");
      return;
    }

    try {
      const registration = await navigator.serviceWorker.register(
        "/static/js/notification-worker.js"
      );
      console.log("Service Worker registered:", registration);
    } catch (error) {
      console.error("Service Worker registration failed:", error);
    }
  },

  // Send notification to backend
  async updatePermissionStatus(status) {
    try {
      const response = await fetch("/notifications/permission", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.getCsrfToken(),
        },
        body: JSON.stringify({ permission_status: status }),
      });

      if (!response.ok) {
        console.error("Failed to update permission status");
      }
    } catch (error) {
      console.error("Error updating permission status:", error);
    }
  },

  // Fetch user's notification preferences
  async getPreferences() {
    try {
      const response = await fetch("/notifications/preferences", {
        method: "GET",
        headers: { "X-CSRFToken": this.getCsrfToken() },
      });

      if (!response.ok) throw new Error("Failed to fetch preferences");
      return await response.json();
    } catch (error) {
      console.error("Error fetching preferences:", error);
      return null;
    }
  },

  // Update a specific notification type preference
  async updateNotificationType(type, enabled) {
    try {
      const response = await fetch(`/notifications/preferences/${type}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.getCsrfToken(),
        },
        body: JSON.stringify({ enabled }),
      });

      if (!response.ok) throw new Error("Failed to update preference");
      return await response.json();
    } catch (error) {
      console.error("Error updating notification preference:", error);
      return null;
    }
  },

  // Show local notification immediately
  showNotification(title, options = {}) {
    if (!this.isSupported() || Notification.permission !== "granted") {
      return;
    }

    const defaultOptions = {
      icon: "/static/img/favicon.ico",
      badge: "/static/img/badge.png",
      ...options,
    };

    return new Notification(title, defaultOptions);
  },

  // Trigger notification for goal reminder
  async notifyGoalReminder(goalData) {
    const prefs = await this.getPreferences();
    if (!prefs || !prefs.notification_types.due_goals) return;

    this.showNotification("Goal Reminder", {
      body: `Your goal "${goalData.title}" is due soon!`,
      tag: `goal-${goalData.id}`,
      requireInteraction: true,
    });
  },

  // Trigger notification for practice challenge
  async notifyChallengeDeadline(challengeData) {
    const prefs = await this.getPreferences();
    if (!prefs || !prefs.notification_types.challenges) return;

    this.showNotification("Challenge Deadline", {
      body: `Challenge "${challengeData.title}" deadline: ${challengeData.dueDate}`,
      tag: `challenge-${challengeData.id}`,
      requireInteraction: true,
    });
  },

  // Initialize notification system on page load
  async init() {
    if (!this.isSupported()) {
      console.warn("Browser notifications not supported");
      return;
    }

    const currentStatus = this.getPermissionStatus();
    if (currentStatus === "granted") {
      await this.registerServiceWorker();
      await this.fetchAndUpdatePreferences();
    }
  },

  // Fetch preferences and store in session storage for quick access
  async fetchAndUpdatePreferences() {
    const prefs = await this.getPreferences();
    if (prefs) {
      sessionStorage.setItem("notificationPrefs", JSON.stringify(prefs));
    }
  },

  // Get CSRF token from page
  getCsrfToken() {
    return document.querySelector('[name="csrf_token"]')?.value || "";
  },
};

// Initialize on page load
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    NotificationManager.init();
  });
} else {
  NotificationManager.init();
}
