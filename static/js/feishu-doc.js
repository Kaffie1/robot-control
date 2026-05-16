/* feishu-doc.js */
function createFeishuDocCard(docItem) {
  const item = docItem && typeof docItem === "object" ? docItem : {};
  const title = String(item.title || "").trim();
  const comment = String(item.comment || "").trim();
  const url = String(item.url || "").trim();
  if (!title || !url) {
    return null;
  }

  const card = document.createElement("div");
  card.className = "docs-link-card";

  const main = document.createElement("div");
  main.className = "docs-link-main";

  const icon = document.createElement("div");
  icon.className = "docs-link-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.innerHTML = `
    <svg viewBox="0 0 24 24">
      <path d="M8 3.5h6l4.5 4.5V20a1.5 1.5 0 0 1-1.5 1.5H8A1.5 1.5 0 0 1 6.5 20V5A1.5 1.5 0 0 1 8 3.5Z"></path>
      <path d="M14 3.5V8h4.5"></path>
      <path d="M9.5 12h5"></path>
      <path d="M9.5 15.5h5"></path>
    </svg>
  `;

  const copy = document.createElement("div");
  copy.className = "docs-link-copy";

  const titleNode = document.createElement("strong");
  titleNode.textContent = title;

  if (comment) {
    const commentNode = document.createElement("p");
    commentNode.className = "docs-link-comment";
    commentNode.textContent = comment;
    copy.append(titleNode, commentNode);
  } else {
    copy.append(titleNode);
  }

  const urlNode = document.createElement("a");
  urlNode.className = "docs-link-url";
  urlNode.href = url;
  urlNode.target = "_blank";
  urlNode.rel = "noopener noreferrer";
  urlNode.textContent = url;

  copy.append(urlNode);
  main.append(icon, copy);

  const button = document.createElement("a");
  button.className = "docs-open-button";
  button.href = url;
  button.target = "_blank";
  button.rel = "noopener noreferrer";
  button.innerHTML = `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M14 5h5v5"></path>
      <path d="M10 14 19 5"></path>
      <path d="M19 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5"></path>
    </svg>
    <span>打开链接</span>
  `;

  card.append(main, button);
  return card;
}

async function loadFeishuDocs() {
  if (!feishuDocsList) {
    return;
  }
  try {
    const response = await fetch(`/static/page_configs/feishu-doc.json?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    const items = Array.isArray(data) ? data : [];
    const cards = items.map(createFeishuDocCard).filter(Boolean);
    feishuDocsList.replaceChildren(...cards);
  } catch (error) {
    const fallback = document.createElement("p");
    fallback.className = "helper-text is-error";
    fallback.textContent = `文档链接加载失败: ${error.message}`;
    feishuDocsList.replaceChildren(fallback);
  }
}
