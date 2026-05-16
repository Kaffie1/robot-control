/* navigation.js */
function switchPage(pageName = "remote") {
  const requestedPage = String(pageName || "remote").trim() || "remote";
  const normalizedPage = pagePanels.some((panel) => panel.dataset.pagePanel === requestedPage) ? requestedPage : "remote";
  pageNavButtons.forEach((button) => {
    const isActive = button.dataset.pageTarget === normalizedPage;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  });
  pagePanels.forEach((panel) => {
    const isActive = panel.dataset.pagePanel === normalizedPage;
    panel.classList.toggle("is-active", isActive);
    panel.hidden = !isActive;
  });
  if (window.location.hash !== `#${normalizedPage}`) {
    window.history.replaceState(null, "", `#${normalizedPage}`);
  }
  if (normalizedPage === "ros") {
    ensureRosPageLoaded();
  }
}
/* navigation.js */
pageNavButtons.forEach((button) => {
  button.addEventListener("click", () => {
    switchPage(button.dataset.pageTarget || "remote");
  });
});
