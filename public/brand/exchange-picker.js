document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".exchange-picker").forEach((picker) => {
    const summary = picker.querySelector("summary");
    const search = picker.querySelector(".exchange-search");
    const options = Array.from(picker.querySelectorAll(".exchange-option"));
    const update = (radio) => {
      const label = radio.closest(".exchange-option");
      const text = document.createElement("span");
      text.className = "exchange-name";
      const icon = label.querySelector(".exchange-icon");
      if (icon) text.append(icon.cloneNode(true));
      const name = document.createElement("span");
      name.className = "selected-exchange-label";
      name.textContent = radio.value || "全部交易所";
      text.append(name);
      summary.replaceChildren(text);
    };
    const checked = picker.querySelector('input[type="radio"]:checked');
    if (checked) update(checked);
    picker.addEventListener("change", (event) => {
      if (event.target.matches('input[type="radio"]')) {
        update(event.target);
        picker.removeAttribute("open");
      }
    });
    search?.addEventListener("input", () => {
      const query = search.value.trim().toLowerCase();
      options.forEach((option) => {
        option.hidden = Boolean(query) && !option.dataset.search.includes(query);
      });
    });
  });
});
