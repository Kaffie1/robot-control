/* guide.js */
function switchGuidePage(pageName = "flow") {
  const requestedPage = String(pageName || "flow").trim() || "flow";
  const normalizedPage = guidePanels.some((panel) => panel.dataset.guidePanel === requestedPage) ? requestedPage : "flow";
  guideNavButtons.forEach((button) => {
    const isActive = button.dataset.guideTarget === normalizedPage;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  });
  guidePanels.forEach((panel) => {
    const isActive = panel.dataset.guidePanel === normalizedPage;
    panel.classList.toggle("is-active", isActive);
    panel.hidden = !isActive;
  });
}
/* guide.js */
guideNavButtons.forEach((button) => {
  button.addEventListener("click", () => {
    switchGuidePage(button.dataset.guideTarget || "flow");
  });
});
