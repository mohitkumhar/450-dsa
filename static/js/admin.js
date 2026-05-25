(function () {
    const deleteModal = document.getElementById("delete-modal");
    const roleModal = document.getElementById("role-modal");
    if (!deleteModal && !roleModal) {
        return;
    }

    const deleteForm = document.getElementById("delete-user-form");
    const deleteModalCopy = document.getElementById("delete-modal-copy");
    const cancelBtn = document.getElementById("cancel-delete-btn");
    const qInput = document.getElementById("delete-q");
    const pageInput = document.getElementById("delete-page");
    const roleForm = document.getElementById("role-user-form");
    const roleModalCopy = document.getElementById("role-modal-copy");
    const cancelRoleBtn = document.getElementById("cancel-role-btn");
    const roleQInput = document.getElementById("role-q");
    const rolePageInput = document.getElementById("role-page");
    const roleMakeAdminInput = document.getElementById("role-make-admin");
    const confirmRoleBtn = document.getElementById("confirm-role-btn");

    function openModal(modal) {
        modal.style.display = "flex";
        modal.setAttribute("aria-hidden", "false");
    }

    function closeModal(modal) {
        if (!modal) {
            return;
        }
        modal.style.display = "none";
        modal.setAttribute("aria-hidden", "true");
    }

    document.querySelectorAll(".js-delete-user").forEach((button) => {
        button.addEventListener("click", function () {
            const userId = this.getAttribute("data-user-id");
            const userName = this.getAttribute("data-user-name") || "this user";
            const q = this.getAttribute("data-q") || "";
            const page = this.getAttribute("data-page") || "1";

            deleteForm.action = "/admin/users/" + encodeURIComponent(userId) + "/delete";
            deleteModalCopy.textContent = "Are you sure you want to delete " + userName + "? This action cannot be undone.";
            qInput.value = q;
            pageInput.value = page;
            openModal(deleteModal);
        });
    });

    document.querySelectorAll(".js-role-change").forEach((button) => {
        button.addEventListener("click", function () {
            const userId = this.getAttribute("data-user-id");
            const userName = this.getAttribute("data-user-name") || "this user";
            const q = this.getAttribute("data-q") || "";
            const page = this.getAttribute("data-page") || "1";
            const makeAdmin = this.getAttribute("data-make-admin") || "0";
            const actionLabel = this.getAttribute("data-action-label") || "Update Role";

            roleForm.action = "/admin/users/" + encodeURIComponent(userId) + "/role";
            roleModalCopy.textContent = "Are you sure you want to " + actionLabel.toLowerCase() + " for " + userName + "?";
            roleQInput.value = q;
            rolePageInput.value = page;
            roleMakeAdminInput.value = makeAdmin;
            confirmRoleBtn.innerHTML = '<i class="bi bi-shield-lock-fill"></i> ' + actionLabel;
            confirmRoleBtn.classList.toggle("danger", makeAdmin === "0");
            openModal(roleModal);
        });
    });

    if (cancelBtn) {
        cancelBtn.addEventListener("click", function () {
            closeModal(deleteModal);
        });
    }
    if (cancelRoleBtn) {
        cancelRoleBtn.addEventListener("click", function () {
            closeModal(roleModal);
        });
    }

    [deleteModal, roleModal].forEach(function (modal) {
        if (!modal) {
            return;
        }
        modal.addEventListener("click", function (event) {
            if (event.target === modal) {
                closeModal(modal);
            }
        });
    });

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") {
            return;
        }
        if (deleteModal && deleteModal.getAttribute("aria-hidden") === "false") {
            closeModal(deleteModal);
        }
        if (roleModal && roleModal.getAttribute("aria-hidden") === "false") {
            closeModal(roleModal);
        }
    });
})();
