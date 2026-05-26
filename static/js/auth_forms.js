(function (window) {
    function validateEmail(value) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    }

    function setFieldState(input, iconEl, errorEl, valid, empty) {
        if (empty) {
            input.classList.remove('is-valid', 'is-invalid');
            if (iconEl) iconEl.innerHTML = '';
            if (errorEl) errorEl.classList.remove('show');
            return;
        }

        input.classList.toggle('is-valid', valid);
        input.classList.toggle('is-invalid', !valid);

        if (iconEl) {
            iconEl.innerHTML = valid
                ? '<i class="bi bi-check-circle-fill" style="color:#22c55e"></i>'
                : '<i class="bi bi-x-circle-fill" style="color:#ef4444"></i>';
        }

        if (errorEl) {
            errorEl.classList.toggle('show', !valid);
        }
    }

    function setupPasswordToggle(toggleButton, passwordInput, toggleIcon) {
        toggleButton.addEventListener('click', () => {
            const show = passwordInput.type === 'password';
            passwordInput.type = show ? 'text' : 'password';
            toggleIcon.className = show ? 'bi bi-eye-slash' : 'bi bi-eye';
        });
    }

    function setSubmitLoading(button, label) {
        button.disabled = true;
        button.innerHTML = '<i class="bi bi-arrow-repeat"></i> ' + label;
    }

    window.AuthForms = {
        validateEmail,
        setFieldState,
        setupPasswordToggle,
        setSubmitLoading,
    };
})(window);
