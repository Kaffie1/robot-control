/* chat.js */
const CHAT_DEFAULT_PLACEHOLDER = "例如：底盘模块启动后没有速度反馈，帮我先分析可能原因";
const CHAT_MAP_SELECTION_PLACEHOLDER = "请输入序号";

function renderChatMessages() {
  if (!chatMessageList) {
    return;
  }
  chatMessageList.replaceChildren();
  if (!chatState.messages.length) {
    const empty = document.createElement("div");
    empty.className = "chat-empty-state";
    empty.innerHTML = "<strong>开始对话</strong><p>你可以先描述一个故障现象，或者直接问机器人相关问题。</p>";
    chatMessageList.appendChild(empty);
    return;
  }
  chatState.messages.forEach((message) => {
    const item = document.createElement("article");
    item.className = `chat-message-item chat-message-item-${message.role}`;
    const badge = document.createElement("div");
    badge.className = "chat-message-role";
    badge.textContent = message.role === "assistant" ? "助手" : "你";
    const body = document.createElement("div");
    body.className = "chat-message-body";
    body.textContent = message.content || "";
    item.append(badge, body);
    chatMessageList.appendChild(item);
  });
  chatMessageList.scrollTop = chatMessageList.scrollHeight;
}

function setChatPending(pending) {
  chatState.pending = Boolean(pending);
  if (chatSubmitBtn) {
    chatSubmitBtn.disabled = chatState.pending;
    chatSubmitBtn.textContent = chatState.pending ? "发送中..." : "发送";
  }
  if (chatInput) {
    chatInput.disabled = chatState.pending;
  }
}

function setChatClarifyState(clarify = null) {
  chatState.pendingClarify = clarify && typeof clarify === "object" ? clarify : null;
  if (!chatInput) {
    return;
  }
  const mode = String(chatState.pendingClarify?.mode || "").trim();
  if (mode === "map_selection") {
    chatInput.placeholder = CHAT_MAP_SELECTION_PLACEHOLDER;
    return;
  }
  chatInput.placeholder = CHAT_DEFAULT_PLACEHOLDER;
}

function clearChatClientState() {
  chatState.messages = [];
  setChatClarifyState(null);
  renderChatMessages();
}

function hydrateChatHistory(messages = []) {
  chatState.messages = (Array.isArray(messages) ? messages : [])
    .filter((item) => item && typeof item === "object")
    .map((item) => ({
      role: String(item.role || "").trim(),
      content: String(item.content || "").trim(),
    }))
    .filter((item) => (item.role === "user" || item.role === "assistant") && item.content);
  renderChatMessages();
}

async function submitChatMessage(event) {
  event.preventDefault();
  const content = String(chatInput?.value || "").trim();
  if (!content) {
    throw new Error("请输入聊天内容");
  }
  chatState.messages.push({ role: "user", content });
  renderChatMessages();
  if (chatInput) {
    chatInput.value = "";
  }
  setChatPending(true);
  try {
    const data = await request("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: content,
      }),
    });
    chatState.messages.push({
      role: "assistant",
      content: String(data.message || "").trim(),
    });
    setChatClarifyState(data.clarify || null);
    renderChatMessages();
    appendLog("聊天助手回复完成", data.model || "");
  } catch (error) {
    chatState.messages.push({
      role: "assistant",
      content: `调用失败：${error.message}`,
    });
    renderChatMessages();
    throw error;
  } finally {
    setChatPending(false);
    if (!chatState.pendingClarify && chatInput) {
      chatInput.placeholder = CHAT_DEFAULT_PLACEHOLDER;
    }
  }
}
/* chat.js */
if (chatForm) {
  chatForm.addEventListener("submit", async (event) => {
    try {
      await submitChatMessage(event);
    } catch (error) {
      appendLog("聊天发送失败", error.message);
      alert(error.message);
    }
  });
}

if (chatClearBtn) {
  chatClearBtn.addEventListener("click", async () => {
    try {
      await request("/api/chat/reset", { method: "POST" });
    } catch (error) {
      appendLog("清空聊天上下文失败", error.message);
    } finally {
      clearChatClientState();
    }
  });
}
