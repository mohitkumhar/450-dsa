(function () {
  const inp = document.getElementById("ep_college");
  const dd = document.getElementById("collegeDropdown");
  if (!inp || !dd || !window.endpointConfig) return;

  let timer = null;
  let activeIdx = -1;

  function setActive(idx) {
    const children = dd.children;
    if (activeIdx >= 0 && activeIdx < children.length) children[activeIdx].style.background = "";
    activeIdx = idx;
    if (activeIdx >= 0 && activeIdx < children.length) {
      children[activeIdx].style.background = "var(--bg-secondary)";
      children[activeIdx].scrollIntoView({ block: "nearest" });
    }
  }

  function renderItems(items) {
    dd.innerHTML = "";
    activeIdx = -1;
    if (!items.length) {
      dd.style.display = "none";
      return;
    }

    items.forEach((item, i) => {
      const div = document.createElement("div");
      div.style.cssText = "padding:9px 14px;cursor:pointer;font-size:.83rem;border-bottom:1px solid var(--border-subtle);display:flex;justify-content:space-between;align-items:center;transition:background .15s";

      const spanName = document.createElement("span");
      spanName.style.cssText = "font-weight:600;color:var(--text-primary)";
      spanName.textContent = item.name;

      const spanCountry = document.createElement("span");
      spanCountry.style.cssText = "font-size:.72rem;color:var(--text-muted)";
      spanCountry.textContent = item.country;

      div.appendChild(spanName);
      div.appendChild(spanCountry);
      div.dataset.label = item.label;
      div.addEventListener("mouseenter", () => setActive(i));
      div.addEventListener("click", () => {
        inp.value = item.label;
        dd.style.display = "none";
      });
      dd.appendChild(div);
    });
    dd.style.display = "block";
  }

  inp.addEventListener("input", function () {
    clearTimeout(timer);
    const q = this.value.trim();
    if (q.length < 2) {
      dd.style.display = "none";
      return;
    }

    timer = setTimeout(() => {
      fetch(window.endpointConfig.searchUniversities + "?q=" + encodeURIComponent(q))
        .then((r) => r.json())
        .then((data) => renderItems(data))
        .catch(() => {
          dd.style.display = "none";
        });
    }, 300);
  });

  inp.addEventListener("keydown", function (e) {
    const children = dd.children;
    if (!children.length || dd.style.display === "none") return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive(Math.min(activeIdx + 1, children.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive(Math.max(activeIdx - 1, 0));
    } else if (e.key === "Enter" && activeIdx >= 0) {
      e.preventDefault();
      inp.value = children[activeIdx].dataset.label;
      dd.style.display = "none";
    } else if (e.key === "Escape") {
      dd.style.display = "none";
    }
  });

  document.addEventListener("click", function (e) {
    if (!inp.contains(e.target) && !dd.contains(e.target)) dd.style.display = "none";
  });
})();
