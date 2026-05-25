(function () {
    const logArea = document.getElementById("admin-log-area");
    if (logArea) {
        const logsUrl = logArea.getAttribute("data-logs-url");
        const escapeHtml = function (value) {
            return String(value || "").replace(/[&<>"']/g, function (char) {
                return {
                    "&": "&amp;",
                    "<": "&lt;",
                    ">": "&gt;",
                    '"': "&quot;",
                    "'": "&#39;",
                }[char];
            });
        };

        const renderLogState = function (html, isBusy) {
            logArea.innerHTML = html;
            logArea.setAttribute("aria-busy", isBusy ? "true" : "false");
        };

        const renderLogs = function (entries) {
            if (!entries.length) {
                renderLogState(
                    '<p class="empty-state">No log files found yet. Add app logging to populate this panel.</p>',
                    false
                );
                return;
            }

                renderLogState(
                    entries
                        .map(function (entry) {
                        const source = escapeHtml(entry.source);
                        const line = escapeHtml(entry.line);
                        return '<div class="log-line"><span class="log-source">[' + source + ']</span>' + line + "</div>";
                    })
                    .join(""),
                false
            );
        };

        const loadLogs = async function () {
            try {
                const response = await fetch(logsUrl, {
                    headers: { Accept: "application/json" },
                });
                const payload = await response.json();

                if (!response.ok || !Array.isArray(payload.logs)) {
                    throw new Error("Invalid log response");
                }

                renderLogs(payload.logs);
            } catch (error) {
                renderLogState(
                    '<p class="empty-state">Could not load logs right now. Refresh to try again.</p>',
                    false
                );
            }
        };

        loadLogs();
    }
})();

(function () {
    const modal = document.getElementById("delete-modal");
    if (!modal) {
        return;
    }

    const form = document.getElementById("delete-user-form");
    const modalCopy = document.getElementById("delete-modal-copy");
    const cancelBtn = document.getElementById("cancel-delete-btn");
    const qInput = document.getElementById("delete-q");
    const pageInput = document.getElementById("delete-page");

    function openModal() {
        modal.style.display = "flex";
        modal.setAttribute("aria-hidden", "false");
    }

    function closeModal() {
        modal.style.display = "none";
        modal.setAttribute("aria-hidden", "true");
    }

    document.querySelectorAll(".js-delete-user").forEach((button) => {
        button.addEventListener("click", function () {
            const userId = this.getAttribute("data-user-id");
            const userName = this.getAttribute("data-user-name") || "this user";
            const q = this.getAttribute("data-q") || "";
            const page = this.getAttribute("data-page") || "1";

            form.action = "/admin/users/" + encodeURIComponent(userId) + "/delete";
            modalCopy.textContent = "Are you sure you want to delete " + userName + "? This action cannot be undone.";
            qInput.value = q;
            pageInput.value = page;
            openModal();
        });
    });

    cancelBtn.addEventListener("click", closeModal);

    modal.addEventListener("click", function (event) {
        if (event.target === modal) {
            closeModal();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && modal.getAttribute("aria-hidden") === "false") {
            closeModal();
        }
    });
})();
