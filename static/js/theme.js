(function () {
  const stored = localStorage.getItem("fg-theme");
  if (stored) {
    document.documentElement.setAttribute("data-theme", stored);
  }

  window.toggleTheme = function () {
    const current = document.documentElement.getAttribute("data-theme") || "dark";
    const next = current === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("fg-theme", next);
  };
})();
