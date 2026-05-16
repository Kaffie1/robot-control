/* bootstrap.js */
window.addEventListener("load", async () => {
  try {
    const initialPage = String(window.location.hash || "").replace(/^#/, "").trim() || "remote";
    renderChatMessages();
    switchPage(initialPage);
    switchGuidePage("flow");
    switchRosSection("topic");
    switchRosTab("publish");
    updateRosTopicSummary();
    updateRosPublishHistory();
    await loadFeishuDocs();
    await loadAutoDeployConfigs();
    await loadRosFilterConfig();
    initializeTimeSelectors();
    initializeModuleFilters();
    const data = await request("/api/status");
    syncSessionIdentity(data.session_id);
    const chatHistoryData = await request("/api/chat/history");
    hydrateChatHistory(chatHistoryData.history || []);
    hydrateConnectionCache(data.saved_connections || []);
    updateConnectionStatus(Boolean(data.connected));
    await syncRemoteDirectories({
      connected: data.connected,
      shortcuts: data.remote_shortcuts,
      preferredRoot: data.preferred_root,
      autoload: data.connected,
    });
    appendLog("页面初始化完成");
    await refreshDashboard();
    startDashboardPolling();
    startSessionHeartbeat();
  } catch (error) {
    appendLog("初始化状态失败", error.message);
  }
});
