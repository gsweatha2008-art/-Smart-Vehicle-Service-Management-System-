document.addEventListener("DOMContentLoaded", () => {
  const menuButton = document.querySelector(".menu-toggle");
  const navigation = document.querySelector(".nav-links");
  if (menuButton && navigation) {
    menuButton.addEventListener("click", () => {
      const isOpen = navigation.classList.toggle("nav-open");
      menuButton.setAttribute("aria-expanded", String(isOpen));
    });
  }

  document.querySelectorAll("form[data-validate]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const passwordField = form.querySelector("[data-match]");
      if (passwordField) {
        const original = form.elements.namedItem(passwordField.dataset.match);
        if (original && passwordField.value !== original.value) {
          passwordField.setCustomValidity("Passwords do not match.");
        } else {
          passwordField.setCustomValidity("");
        }
      }
      if (!form.reportValidity()) {
        event.preventDefault();
      }
    });
    form.querySelectorAll("[data-match]").forEach((field) => {
      field.addEventListener("input", () => field.setCustomValidity(""));
    });
  });

  const dateField = document.querySelector('input[name="service_date"]');
  if (dateField && !dateField.min) {
    dateField.min = new Date().toISOString().slice(0, 10);
  }

  const partSelect = document.querySelector("[data-part-select]");
  const quantityInput = document.querySelector("[data-part-quantity]");
  if (partSelect && quantityInput) {
    const updateStockLimit = () => {
      const option = partSelect.selectedOptions[0];
      const stock = Number(option?.dataset.stock || 999);
      quantityInput.max = String(Math.max(stock, 1));
      if (Number(quantityInput.value) > stock) quantityInput.value = String(Math.max(stock, 1));
    };
    partSelect.addEventListener("change", updateStockLimit);
    updateStockLimit();
  }

  document.querySelectorAll(".flash").forEach((message) => {
    window.setTimeout(() => message.classList.add("flash-hidden"), 5500);
  });
});
