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
