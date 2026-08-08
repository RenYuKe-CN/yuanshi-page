document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".exchange-picker").forEach((picker) => {
    const summary = picker.querySelector("summary");
    const search = picker.querySelector(".exchange-search");
    const options = Array.from(picker.querySelectorAll(".exchange-option"));
    const groups = Array.from(picker.querySelectorAll(".exchange-group"));
    const status = picker.querySelector(".exchange-search-status");
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
    const normalized = (value) => String(value || "")
      .toLowerCase()
      .replace(/[\s\-_./]/g, "");
    const isFuzzyMatch = (value, query) => {
      if (!query) return true;
      if (value.includes(query)) return true;
      let position = 0;
      for (const character of value) {
        if (character === query[position]) position += 1;
        if (position === query.length) return true;
      }
      return false;
    };
    const filter = () => {
      const rawQuery = search.value.trim().toLowerCase();
      const query = normalized(rawQuery);
      let matches = 0;
      options.forEach((option) => {
        const visible = isFuzzyMatch(normalized(option.dataset.search), query);
        option.hidden = !visible;
        if (visible) matches += 1;
      });
      groups.forEach((group) => {
        group.hidden = !Array.from(group.querySelectorAll(".exchange-option")).some((option) => !option.hidden);
      });
      picker.classList.toggle("is-filtering", Boolean(query));
      if (status) status.textContent = query ? (matches ? `候选结果：${matches} 个。点击名称即可选择。` : "未找到匹配交易所，请调整关键词。") : "输入名称、别名或 CEX / DEX 进行筛选。";
      return matches;
    };
    search?.addEventListener("input", filter);
    search?.addEventListener("focus", filter);
    search?.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      const visible = options.filter((option) => !option.hidden);
      const exact = visible.find((option) => option.dataset.name === search.value.trim().toLowerCase());
      if (exact || visible.length === 1) {
        const radio = (exact || visible[0]).querySelector('input[type="radio"]');
        radio.checked = true;
        radio.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    filter();
  });
});
