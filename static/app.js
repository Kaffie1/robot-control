const statusText = document.getElementById("connectionStatus");
const statusDot = document.querySelector(".status-dot");
const logOutput = document.getElementById("logOutput");
const connectForm = document.getElementById("connectForm");
const savedConnectionSelect = document.getElementById("savedConnectionSelect");
const savedConnectionSummary = document.getElementById("savedConnectionSummary");
const clearConnectionCacheBtn = document.getElementById("clearConnectionCacheBtn");
const remoteCacheSelectShell = document.querySelector(".remote-cache-select-main");
const packageDeployForm = document.getElementById("packageDeployForm");
const packageMachineType = document.getElementById("packageMachineType");
const packageDeviceType = document.getElementById("packageDeviceType");
const packageAutoDeploySelect = document.getElementById("packageAutoDeploySelect");
const packageAutoDeployHint = document.getElementById("packageAutoDeployHint");
const packageDeployDropzone = document.getElementById("packageDeployDropzone");
const packageDeployFileInput = document.getElementById("packageDeployFileInput");
const packageDeployFileMeta = document.getElementById("packageDeployFileMeta");
const packageDeploySubmitBtn = document.getElementById("packageDeploySubmitBtn");
const packageDeployStageHint = document.getElementById("packageDeployStageHint");
const moduleDeployForm = document.getElementById("moduleDeployForm");
const moduleAutoDeploySelect = document.getElementById("moduleAutoDeploySelect");
const moduleAutoDeployHint = document.getElementById("moduleAutoDeployHint");
const moduleDeployDropzone = document.getElementById("moduleDeployDropzone");
const moduleDeployFileInput = document.getElementById("moduleDeployFileInput");
const moduleDeployFileMeta = document.getElementById("moduleDeployFileMeta");
const moduleSelect = document.getElementById("moduleSelect");
const taskList = document.getElementById("taskList");
const taskDetailOutput = document.getElementById("taskDetailOutput");
const copyTaskDetailBtn = document.getElementById("copyTaskDetailBtn");
const passwordToggleButtons = Array.from(document.querySelectorAll("[data-password-toggle]"));
const pageNavButtons = Array.from(document.querySelectorAll("[data-page-target]"));
const pagePanels = Array.from(document.querySelectorAll("[data-page-panel]"));
const guideNavButtons = Array.from(document.querySelectorAll("[data-guide-target]"));
const guidePanels = Array.from(document.querySelectorAll("[data-guide-panel]"));
const configNavButtons = Array.from(document.querySelectorAll("[data-config-target]"));
const configPanels = Array.from(document.querySelectorAll("[data-config-panel]"));
const refreshAudioConfigBtn = document.getElementById("refreshAudioConfigBtn");
const enableAllAudioConfigBtn = document.getElementById("enableAllAudioConfigBtn");
const disableAllAudioConfigBtn = document.getElementById("disableAllAudioConfigBtn");
const saveAudioConfigBtn = document.getElementById("saveAudioConfigBtn");
const audioConfigStatus = document.getElementById("audioConfigStatus");
const audioConfigToggleList = document.getElementById("audioConfigToggleList");
const rosNavButtons = Array.from(document.querySelectorAll("[data-ros-target]"));
const rosPanels = Array.from(document.querySelectorAll("[data-ros-panel]"));
const feishuDocsList = document.getElementById("feishuDocsList");
const orinLogModuleSelect = document.getElementById("orinLogModuleSelect");
const orinLogStatus = document.getElementById("orinLogStatus");
const downloadOrinLogBtn = document.getElementById("downloadOrinLogBtn");
const picoLogModuleSelect = document.getElementById("picoLogModuleSelect");
const picoLogStatus = document.getElementById("picoLogStatus");
const downloadPicoLogBtn = document.getElementById("downloadPicoLogBtn");
const refreshRosTopicsBtn = document.getElementById("refreshRosTopicsBtn");
const refreshRosServicesBtn = document.getElementById("refreshRosServicesBtn");
const rosPageHint = document.getElementById("rosPageHint");
const rosTopicSearchInput = document.getElementById("rosTopicSearchInput");
const rosServiceSearchInput = document.getElementById("rosServiceSearchInput");
const rosTopicList = document.getElementById("rosTopicList");
const rosServiceList = document.getElementById("rosServiceList");
const rosTopicListCount = document.getElementById("rosTopicListCount");
const rosServiceListCount = document.getElementById("rosServiceListCount");
const rosSelectedTopicName = document.getElementById("rosSelectedTopicName");
const rosSelectedTopicType = document.getElementById("rosSelectedTopicType");
const rosSelectedTopicDirection = document.getElementById("rosSelectedTopicDirection");
const rosTopicAvailabilityBadge = document.getElementById("rosTopicAvailabilityBadge");
const rosSelectedServiceName = document.getElementById("rosSelectedServiceName");
const rosSelectedServiceType = document.getElementById("rosSelectedServiceType");
const rosPublishTabBtn = document.getElementById("rosPublishTabBtn");
const rosSubscribeTabBtn = document.getElementById("rosSubscribeTabBtn");
const rosPublishPanel = document.getElementById("rosPublishPanel");
const rosSubscribePanel = document.getElementById("rosSubscribePanel");
const rosTopicInfoBtn = document.getElementById("rosTopicInfoBtn");
const rosTopicTypeBtn = document.getElementById("rosTopicTypeBtn");
const rosTopicEchoBtn = document.getElementById("rosTopicEchoBtn");
const rosTopicPubBtn = document.getElementById("rosTopicPubBtn");
const rosTopicPubPythonBtn = document.getElementById("rosTopicPubPythonBtn");
const rosTopicPubPythonCopyBtn = document.getElementById("rosTopicPubPythonCopyBtn");
const rosTopicSubPythonBtn = document.getElementById("rosTopicSubPythonBtn");
const rosTopicSubPythonCopyBtn = document.getElementById("rosTopicSubPythonCopyBtn");
const rosTopicPubTypeInput = document.getElementById("rosTopicPubTypeInput");
const rosTopicPubMessageInput = document.getElementById("rosTopicPubMessageInput");
const rosTopicPublishHistory = document.getElementById("rosTopicPublishHistory");
const rosTopicPublishOutput = document.getElementById("rosTopicPublishOutput");
const rosTopicDefinitionOutput = document.getElementById("rosTopicDefinitionOutput");
const rosTopicDetailOutput = document.getElementById("rosTopicDetailOutput");
const rosServiceInfoBtn = document.getElementById("rosServiceInfoBtn");
const rosServiceTypeBtn = document.getElementById("rosServiceTypeBtn");
const rosServicePythonBtn = document.getElementById("rosServicePythonBtn");
const rosServicePythonCopyBtn = document.getElementById("rosServicePythonCopyBtn");
const rosServiceCallBtn = document.getElementById("rosServiceCallBtn");
const rosServiceCallRequestInput = document.getElementById("rosServiceCallRequestInput");
const rosServiceDefinitionOutput = document.getElementById("rosServiceDefinitionOutput");
const rosServiceDetailOutput = document.getElementById("rosServiceDetailOutput");
const timeSelectContainers = Array.from(document.querySelectorAll(".log-time-selects"));
const moduleFilterRoots = Array.from(document.querySelectorAll("[data-module-filter]"));
const remoteDirSelects = Array.from(document.querySelectorAll("[data-remote-dir-select]"));
const remoteDirLoadButtons = Array.from(document.querySelectorAll("[data-load-remote-dir]"));
const DEFAULT_PROJECT_ROOT = "/naviai/home/navi_project";
const PACKAGE_DEPLOY_DIR = "/tmp";
const DEFAULT_CONNECTION_FORM = {
  host: "",
  port: "22",
  username: "naviai",
  pico_host: "192.168.217.66",
  pico_port: "22",
  pico_username: "nav01",
  pico_password: " ",
};

const uploadProgressViews = {
  packageDeploy: createUploadProgressView("packageDeployUploadProgress"),
  moduleDeploy: createUploadProgressView("moduleDeployUploadProgress"),
};
const deployFlowViews = {
  package: createDeployFlowView("packageDeployFlow"),
  module: createDeployFlowView("moduleDeployFlow"),
};

let selectedTaskId = "";
let dashboardTimer = null;
let heartbeatTimer = null;
let dashboardErrorShown = false;
let remoteShortcutsCache = [];
let preferredRootCache = "/tmp";
const rememberedRemoteDirs = new Map();
let savedConnectionsCache = [];
let currentTaskDetailText = "";
const currentDeployTaskIds = {
  package: "",
  module: "",
};
const deployProgressSnapshots = {
  package: null,
  module: null,
};
const DEFAULT_PACKAGE_MACHINE_OPTIONS = [
  { value: "WA1", label: "WA1" },
  { value: "WA2", label: "WA2" },
  { value: "I2", label: "I2" },
];
const packageDeployStageState = {
  stage: "upload",
  fileName: "",
  remotePath: "",
  remoteDir: "",
  deviceType: "ORIN",
  machineOptions: [],
};
let packageAutoDeployConfigs = [];
let moduleAutoDeployConfigs = [];
let manualPackageServerFilePath = "";
let manualModuleServerFilePath = "";
let pendingPackageAutoDeployUrls = [];
const DEFAULT_SERVER_FILE_PLACEHOLDER = "填写服务器包路径；留空时使用本地上传";
const rosState = {
  topics: [],
  services: [],
  selectedTopic: "",
  selectedService: "",
  selectedTopicType: "",
  selectedTopicDefinition: "",
  selectedTopicDirection: "",
  topicAvailable: false,
  selectedServiceType: "",
  selectedServiceDefinition: "",
  activeTab: "publish",
  activeSection: "topic",
  lastPublishRecord: null,
  hasLoadedTopics: false,
  hasLoadedServices: false,
};
const rosFilterConfig = {
  topicPrefixes: [],
  servicePrefixes: [],
  topicNames: [],
  serviceNames: [],
};
const audioMonitorState = {
  entries: [],
  hasLoaded: false,
  isSaving: false,
};

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
  if (normalizedPage === "config") {
    ensureAudioMonitorConfigLoaded();
  }
}

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

function switchConfigPage(pageName = "voice") {
  const requestedPage = String(pageName || "voice").trim() || "voice";
  const normalizedPage = configPanels.some((panel) => panel.dataset.configPanel === requestedPage) ? requestedPage : "voice";
  configNavButtons.forEach((button) => {
    const isActive = button.dataset.configTarget === normalizedPage;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  });
  configPanels.forEach((panel) => {
    const isActive = panel.dataset.configPanel === normalizedPage;
    panel.classList.toggle("is-active", isActive);
    panel.hidden = !isActive;
  });
  if (normalizedPage === "voice") {
    ensureAudioMonitorConfigLoaded();
  }
}

function setAudioConfigStatus(message, isError = false) {
  if (!audioConfigStatus) {
    return;
  }
  audioConfigStatus.textContent = message;
  audioConfigStatus.classList.toggle("is-error", Boolean(isError));
}

function setAllAudioMonitorEntries(enabled) {
  if (!audioMonitorState.entries.length) {
    setAudioConfigStatus("当前没有可批量设置的语音监控模块。", true);
    return;
  }
  audioMonitorState.entries.forEach((entry) => {
    entry.enable = Boolean(enabled);
  });
  renderAudioMonitorConfig();
  setAudioConfigStatus(enabled ? "已将当前页面中的全部模块设置为开启。记得点击“保存并重载”。" : "已将当前页面中的全部模块设置为关闭。记得点击“保存并重载”。");
}

function renderAudioMonitorConfig() {
  if (!audioConfigToggleList) {
    return;
  }
  audioConfigToggleList.replaceChildren();
  if (!audioMonitorState.entries.length) {
    const placeholder = document.createElement("div");
    placeholder.className = "config-placeholder";
    placeholder.innerHTML = "<strong>当前状态</strong><p>未读取到任何语音监控模块。</p>";
    audioConfigToggleList.appendChild(placeholder);
    return;
  }
  audioMonitorState.entries.forEach((entry) => {
    const item = document.createElement("label");
    item.className = "config-toggle-item";

    const info = document.createElement("div");
    info.className = "config-toggle-copy";

    const title = document.createElement("strong");
    title.textContent = entry.module || "-";

    const meta = document.createElement("div");
    meta.className = "config-toggle-meta";
    meta.textContent = entry.topic || "未配置 topic";

    info.append(title, meta);

    const toggle = document.createElement("input");
    toggle.type = "checkbox";
    toggle.checked = Boolean(entry.enable);
    toggle.disabled = Boolean(audioMonitorState.isSaving);
    toggle.addEventListener("change", () => {
      entry.enable = toggle.checked;
    });

    const switchShell = document.createElement("span");
    switchShell.className = "config-switch";
    switchShell.appendChild(toggle);

    const switchTrack = document.createElement("span");
    switchTrack.className = "config-switch-track";
    switchShell.appendChild(switchTrack);

    item.append(info, switchShell);
    audioConfigToggleList.appendChild(item);
  });
}

async function loadAudioMonitorConfig() {
  setAudioConfigStatus("正在从远端读取语音监控配置...");
  const data = await request("/api/config/audio-monitor");
  audioMonitorState.entries = Array.isArray(data.entries)
    ? data.entries.map((entry) => ({
      module: String(entry?.module || "").trim(),
      enable: Boolean(entry?.enable),
      audio_error_path: String(entry?.audio_error_path || "").trim(),
      audio_normal_path: String(entry?.audio_normal_path || "").trim(),
      topic: String(entry?.topic || "").trim(),
    }))
    : [];
  audioMonitorState.hasLoaded = true;
  renderAudioMonitorConfig();
  setAudioConfigStatus(`已加载 ${audioMonitorState.entries.length} 个语音监控模块。`);
}

async function ensureAudioMonitorConfigLoaded() {
  if (audioMonitorState.hasLoaded) {
    return;
  }
  try {
    await loadAudioMonitorConfig();
  } catch (error) {
    setAudioConfigStatus(`加载语音监控配置失败：${error.message}`, true);
    appendLog("加载语音监控配置失败", error.message);
  }
}

async function saveAudioMonitorConfig() {
  if (!audioMonitorState.entries.length) {
    throw new Error("当前没有可保存的语音监控配置");
  }
  audioMonitorState.isSaving = true;
  renderAudioMonitorConfig();
  setAudioConfigStatus("正在保存远端语音监控配置并执行重载...");
  try {
    const data = await request("/api/config/audio-monitor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        entries: audioMonitorState.entries.map((entry) => ({
          module: entry.module,
          enable: Boolean(entry.enable),
        })),
      }),
    });
    audioMonitorState.entries = Array.isArray(data.entries)
      ? data.entries.map((entry) => ({
        module: String(entry?.module || "").trim(),
        enable: Boolean(entry?.enable),
        audio_error_path: String(entry?.audio_error_path || "").trim(),
        audio_normal_path: String(entry?.audio_normal_path || "").trim(),
        topic: String(entry?.topic || "").trim(),
      }))
      : audioMonitorState.entries;
    renderAudioMonitorConfig();
    setAudioConfigStatus(data.reload_output ? `保存成功，重载结果：${data.reload_output}` : "保存成功，配置已重载。");
    appendLog("语音监控配置已保存", data.reload_output || String(data.remote_path || ""));
  } catch (error) {
    audioMonitorState.hasLoaded = false;
    try {
      await loadAudioMonitorConfig();
    } catch (reloadError) {
      appendLog("保存失败后刷新语音监控配置失败", reloadError.message);
    }
    throw error;
  } finally {
    audioMonitorState.isSaving = false;
    renderAudioMonitorConfig();
  }
}

function switchRosSection(pageName = "topic") {
  const requestedPage = String(pageName || "topic").trim() || "topic";
  const normalizedPage = rosPanels.some((panel) => panel.dataset.rosPanel === requestedPage) ? requestedPage : "topic";
  rosState.activeSection = normalizedPage;
  rosNavButtons.forEach((button) => {
    const isActive = button.dataset.rosTarget === normalizedPage;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  });
  rosPanels.forEach((panel) => {
    const isActive = panel.dataset.rosPanel === normalizedPage;
    panel.classList.toggle("is-active", isActive);
    panel.hidden = !isActive;
  });
}

function setPackageAutoDeployHint(message, isError = false) {
  if (!packageAutoDeployHint) {
    return;
  }
  packageAutoDeployHint.textContent = message;
  packageAutoDeployHint.classList.toggle("is-error", Boolean(isError));
}

function setModuleAutoDeployHint(message, isError = false) {
  if (!moduleAutoDeployHint) {
    return;
  }
  moduleAutoDeployHint.textContent = message;
  moduleAutoDeployHint.classList.toggle("is-error", Boolean(isError));
}

function normalizeAutoDeployUrls(urls = []) {
  return Array.isArray(urls)
    ? urls.map((url) => String(url || "").trim()).filter(Boolean)
    : [];
}

function normalizeAutoDeployModules(modules = []) {
  if (!Array.isArray(modules)) {
    return [];
  }
  return modules
    .map((moduleItem) => ({
      module: String(moduleItem?.module || "").trim(),
      urls: normalizeAutoDeployUrls(moduleItem?.urls),
    }))
    .filter((moduleItem) => moduleItem.module && moduleItem.urls.length);
}

function getSelectedPackageAutoDeployConfig() {
  const selectedVersion = String(packageAutoDeploySelect?.value || "").trim();
  if (!selectedVersion) {
    return null;
  }
  return packageAutoDeployConfigs.find((item) => item.version === selectedVersion) || null;
}

function getSelectedModuleAutoDeployConfig() {
  const selectedVersion = String(moduleAutoDeploySelect?.value || "").trim();
  const selectedModuleName = String(moduleSelect?.value || "").trim().toUpperCase();
  if (!selectedVersion || !selectedModuleName) {
    return { versionConfig: null, moduleConfig: null };
  }
  const versionConfig = moduleAutoDeployConfigs.find((item) => item.version === selectedVersion) || null;
  const moduleConfig = versionConfig?.modules?.find((item) => String(item?.module || "").trim().toUpperCase() === selectedModuleName) || null;
  return { versionConfig, moduleConfig };
}

function applyPackageAutoDeploySelection() {
  const serverPathInput = packageDeployForm?.elements?.namedItem("server_file_path");
  if (!(serverPathInput instanceof HTMLInputElement)) {
    return;
  }
  const selectedConfig = getSelectedPackageAutoDeployConfig();
  if (!selectedConfig) {
    serverPathInput.readOnly = false;
    serverPathInput.value = manualPackageServerFilePath;
    serverPathInput.placeholder = DEFAULT_SERVER_FILE_PLACEHOLDER;
    setPackageAutoDeployHint("注：选择自动部署版本后，不需要再上传 firmware 文件");
    pendingPackageAutoDeployUrls = [];
    return;
  }
  if (!manualPackageServerFilePath) {
    manualPackageServerFilePath = String(serverPathInput.value || "").trim();
  }
  serverPathInput.value = "";
  serverPathInput.readOnly = true;
  serverPathInput.placeholder = `已选择 ${selectedConfig.version}，共 ${selectedConfig.urls.length} 个包，将自动依次部署`;
  setPackageDeployFile(null);
  pendingPackageAutoDeployUrls = [];
  setPackageAutoDeployHint(`已选择自动部署版本：${selectedConfig.version}，将依次执行 ${selectedConfig.urls.length} 个包。`);
}

function applyModuleAutoDeploySelection() {
  const serverPathInput = moduleDeployForm?.elements?.namedItem("server_file_path");
  if (!(serverPathInput instanceof HTMLInputElement)) {
    return;
  }
  const { versionConfig: selectedVersionConfig, moduleConfig: selectedModuleConfig } = getSelectedModuleAutoDeployConfig();
  if (!selectedVersionConfig) {
    serverPathInput.readOnly = false;
    serverPathInput.value = manualModuleServerFilePath;
    serverPathInput.placeholder = DEFAULT_SERVER_FILE_PLACEHOLDER;
    setModuleAutoDeployHint("注：选择自动部署版本后，不需要再上传模块 deb 文件");
    return;
  }
  if (!selectedModuleConfig) {
    serverPathInput.readOnly = false;
    serverPathInput.value = manualModuleServerFilePath;
    serverPathInput.placeholder = DEFAULT_SERVER_FILE_PLACEHOLDER;
    setModuleAutoDeployHint(`版本 ${selectedVersionConfig.version} 下未配置当前模块的包路径。`, true);
    return;
  }
  if (!manualModuleServerFilePath) {
    manualModuleServerFilePath = String(serverPathInput.value || "").trim();
  }
  serverPathInput.value = "";
  serverPathInput.readOnly = true;
  serverPathInput.placeholder = `已选择 ${selectedVersionConfig.version} / ${selectedModuleConfig.module}，共 ${selectedModuleConfig.urls.length} 个包`;
  setModuleDeployFile(null);
  setModuleAutoDeployHint(`已选择自动部署版本：${selectedVersionConfig.version}，模块 ${selectedModuleConfig.module} 将依次执行 ${selectedModuleConfig.urls.length} 个包。`);
}

function renderPackageAutoDeployOptions(items = []) {
  if (!packageAutoDeploySelect) {
    return;
  }
  packageAutoDeployConfigs = Array.isArray(items)
    ? items.filter((item) => item && item.version && Array.isArray(item.urls) && item.urls.length)
    : [];
  const currentValue = String(packageAutoDeploySelect.value || "").trim();
  packageAutoDeploySelect.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "不使用自动部署，改为手动上传或填写服务器路径";
  packageAutoDeploySelect.appendChild(placeholder);
  packageAutoDeployConfigs.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.version;
    option.textContent = item.version;
    if (currentValue && currentValue === option.value) {
      option.selected = true;
    }
    packageAutoDeploySelect.appendChild(option);
  });
  applyPackageAutoDeploySelection();
}

function renderModuleAutoDeployOptions(items = []) {
  if (!moduleAutoDeploySelect) {
    return;
  }
  moduleAutoDeployConfigs = Array.isArray(items)
    ? items.filter((item) => item && item.version && Array.isArray(item.modules) && item.modules.length)
    : [];
  const currentValue = String(moduleAutoDeploySelect.value || "").trim();
  moduleAutoDeploySelect.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "不使用自动部署，改为手动上传或填写服务器路径";
  moduleAutoDeploySelect.appendChild(placeholder);
  moduleAutoDeployConfigs.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.version;
    option.textContent = item.version;
    if (currentValue && currentValue === option.value) {
      option.selected = true;
    }
    moduleAutoDeploySelect.appendChild(option);
  });
  applyModuleAutoDeploySelection();
}

async function loadAutoDeployConfigs() {
  if (!packageAutoDeploySelect && !moduleAutoDeploySelect) {
    return;
  }
  try {
    const response = await fetch(`/static/page_configs/deploy.auto.json?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    const packageItems = Array.isArray(data?.package) ? data.package.map((item) => ({
      version: String(item?.version || "").trim(),
      urls: normalizeAutoDeployUrls(item?.urls),
    })) : [];
    const moduleItems = Array.isArray(data?.module) ? data.module.map((item) => ({
      version: String(item?.version || "").trim(),
      modules: normalizeAutoDeployModules(item?.modules),
    })) : [];
    renderPackageAutoDeployOptions(packageItems);
    renderModuleAutoDeployOptions(moduleItems);
  } catch (error) {
    renderPackageAutoDeployOptions([]);
    renderModuleAutoDeployOptions([]);
    setPackageAutoDeployHint(`自动部署配置加载失败：${error.message}`, true);
    setModuleAutoDeployHint(`自动部署配置加载失败：${error.message}`, true);
  }
}

function normalizeRosFilterPrefixes(items = []) {
  return Array.isArray(items)
    ? items.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
}

async function loadRosFilterConfig() {
  try {
    const response = await fetch(`/static/page_configs/ros.filters.json?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    rosFilterConfig.topicPrefixes = normalizeRosFilterPrefixes(data?.topic_prefixes);
    rosFilterConfig.servicePrefixes = normalizeRosFilterPrefixes(data?.service_prefixes);
    rosFilterConfig.topicNames = normalizeRosFilterPrefixes(data?.topic_names);
    rosFilterConfig.serviceNames = normalizeRosFilterPrefixes(data?.service_names);
  } catch (error) {
    rosFilterConfig.topicPrefixes = [];
    rosFilterConfig.servicePrefixes = [];
    rosFilterConfig.topicNames = [];
    rosFilterConfig.serviceNames = [];
    appendLog("ROS 过滤配置加载失败", error.message);
  }
}

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

function setLogStatus(node, message, isError = false) {
  if (!node) {
    return;
  }
  node.textContent = message;
  node.classList.toggle("is-error", Boolean(isError));
}

function setPackageDeployHint(message, isError = false) {
  if (!packageDeployStageHint) {
    return;
  }
  packageDeployStageHint.textContent = message;
  packageDeployStageHint.classList.toggle("is-error", Boolean(isError));
  packageDeployStageHint.classList.toggle("is-attention", !isError && packageDeployStageState.stage === "continue");
}

function setPackageMachineAttention(active) {
  if (!packageMachineType) {
    return;
  }
  packageMachineType.classList.toggle("is-attention", Boolean(active));
}

function renderPackageMachineOptions(options = [], selectedValue = "", requireExplicitSelection = false) {
  if (!packageMachineType) {
    return;
  }
  packageMachineType.replaceChildren();
  if (!options.length) {
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "请先上传 firmware 并识别机型";
    packageMachineType.appendChild(placeholder);
    packageMachineType.value = "";
    packageMachineType.disabled = true;
    return;
  }
  if (requireExplicitSelection && !selectedValue) {
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "请选择机型";
    placeholder.selected = true;
    packageMachineType.appendChild(placeholder);
  }
  options.forEach((option, index) => {
    const item = document.createElement("option");
    item.value = String(option.value || "").trim();
    item.textContent = String(option.label || option.value || "").trim();
    if (!item.value) {
      return;
    }
    if ((selectedValue && item.value === selectedValue) || (!selectedValue && !requireExplicitSelection && index === 0)) {
      item.selected = true;
    }
    packageMachineType.appendChild(item);
  });
  packageMachineType.disabled = false;
}

function resetPackageDeployStage({ keepHint = false, keepMachineOptions = false, selectedMachineType = "" } = {}) {
  packageDeployStageState.stage = "upload";
  packageDeployStageState.fileName = "";
  packageDeployStageState.remotePath = "";
  packageDeployStageState.remoteDir = "";
  packageDeployStageState.deviceType = String(packageDeviceType?.value || "ORIN").trim().toUpperCase() || "ORIN";
  pendingPackageAutoDeployUrls = [];
  if (!keepMachineOptions) {
    packageDeployStageState.machineOptions = [];
    renderPackageMachineOptions([]);
  } else {
    renderPackageMachineOptions(packageDeployStageState.machineOptions, selectedMachineType);
  }
  setPackageMachineAttention(false);
  if (packageDeploySubmitBtn) {
    packageDeploySubmitBtn.textContent = "创建整包部署任务";
  }
  if (!keepHint) {
    setPackageDeployHint("请先上传 firmware，上传完成后将自动识别可选机型。");
  }
}

function activatePackageDeployContinueStage({ fileName = "", remotePath = "", remoteDir = "", deviceType = "ORIN", machineOptions = [], selectedMachineType = "" } = {}) {
  packageDeployStageState.stage = "continue";
  packageDeployStageState.fileName = String(fileName || "").trim();
  packageDeployStageState.remotePath = String(remotePath || "").trim();
  packageDeployStageState.remoteDir = String(remoteDir || "").trim();
  packageDeployStageState.deviceType = String(deviceType || "ORIN").trim().toUpperCase() || "ORIN";
  packageDeployStageState.machineOptions = Array.isArray(machineOptions) ? machineOptions : [];
  const normalizedSelectedMachineType = String(selectedMachineType || "").trim();
  renderPackageMachineOptions(packageDeployStageState.machineOptions, normalizedSelectedMachineType);
  setPackageMachineAttention(false);
  if (packageDeploySubmitBtn) {
    packageDeploySubmitBtn.textContent = "继续部署";
  }
  if (normalizedSelectedMachineType) {
    setPackageDeployHint(`已读取远端 ROBOT_TYPE=${normalizedSelectedMachineType}，将直接复用该机型，确认后点击“继续部署”。`);
  } else {
    setPackageDeployHint("未读取到 ROBOT_TYPE，已默认选中第一个机型，请确认后点击“继续部署”。");
  }
  window.setTimeout(() => {
    if (!packageMachineType) {
      return;
    }
    packageMachineType.focus();
    if (typeof packageMachineType.showPicker === "function") {
      try {
        packageMachineType.showPicker();
      } catch {
        // ignore browsers that require stricter user activation timing
      }
    }
  }, 0);
}

function buildTimeSelect(prefix, suffix, start, end, pad = true) {
  const select = document.createElement("select");
  select.dataset.timeField = `${prefix}-${suffix}`;
  for (let value = start; value <= end; value += 1) {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = pad ? String(value).padStart(2, "0") : String(value);
    select.appendChild(option);
  }
  return select;
}

function createTimeSelectField(prefix, suffix, start, end, pad = true) {
  const unitMap = {
    month: "月",
    day: "日",
    hour: "时",
    minute: "分",
    second: "秒",
  };
  const wrapper = document.createElement("div");
  wrapper.className = "time-select-field";
  const select = buildTimeSelect(prefix, suffix, start, end, pad);
  const unit = document.createElement("span");
  unit.className = "time-select-unit";
  unit.textContent = unitMap[suffix] || "";
  wrapper.append(select, unit);
  return { wrapper, select };
}

function initializeTimeSelectors() {
  const now = new Date();
  timeSelectContainers.forEach((container) => {
    const prefix = container.dataset.timePrefix;
    if (!prefix || container.childElementCount) {
      return;
    }
    const fields = [
      createTimeSelectField(prefix, "month", 1, 12),
      createTimeSelectField(prefix, "day", 1, 31),
      createTimeSelectField(prefix, "hour", 0, 23),
      createTimeSelectField(prefix, "minute", 0, 59),
    ];
    fields[0].select.value = String(now.getMonth() + 1);
    fields[1].select.value = String(now.getDate());
    fields[2].select.value = String(now.getHours());
    fields[3].select.value = String(now.getMinutes());
    fields.forEach((field) => container.appendChild(field.wrapper));
  });
}

function readTimeRange(prefix) {
  const year = new Date().getFullYear();
  const getValue = (name) => {
    const node = document.querySelector(`[data-time-field="${prefix}-${name}"]`);
    return Number(node?.value || 0);
  };
  const month = getValue("month");
  const day = getValue("day");
  const hour = getValue("hour");
  const minute = getValue("minute");
  const second = prefix.endsWith("end") ? 59 : 0;
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")} ${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}:${String(second).padStart(2, "0")}`;
}

function readSelectedModuleNames(selectNode) {
  if (!selectNode) {
    return [];
  }
  return Array.from(selectNode.selectedOptions || [])
    .map((option) => String(option.value || "").trim())
    .filter(Boolean);
}

function setModuleFilterOpen(root, open) {
  if (!root) {
    return;
  }
  const trigger = root.querySelector("[data-module-filter-trigger]");
  const dropdown = root.querySelector("[data-module-filter-dropdown]");
  const isOpen = Boolean(open);
  trigger?.classList.toggle("is-open", isOpen);
  if (trigger) {
    trigger.setAttribute("aria-expanded", String(isOpen));
  }
  if (dropdown) {
    dropdown.hidden = !isOpen;
  }
}

function updateModuleSelection(selectNode, option, selected) {
  if (!selectNode || !option) {
    return;
  }
  option.selected = Boolean(selected);
  selectNode.dispatchEvent(new Event("change", { bubbles: true }));
}

function updateAllModuleSelections(selectNode, selected) {
  if (!selectNode) {
    return;
  }
  Array.from(selectNode.options || []).forEach((option) => {
    option.selected = Boolean(selected);
  });
  selectNode.dispatchEvent(new Event("change", { bubbles: true }));
}

function renderModuleFilter(root, selectNode) {
  if (!root || !selectNode) {
    return;
  }
  const trigger = root.querySelector("[data-module-filter-trigger]");
  const selectedNode = root.querySelector("[data-module-filter-selected]");
  const optionsNode = root.querySelector("[data-module-filter-options]");
  if (!trigger || !selectedNode || !optionsNode) {
    return;
  }

  const options = Array.from(selectNode.options || []);
  const selectedOptions = options.filter((option) => option.selected);
  selectedNode.replaceChildren();
  optionsNode.replaceChildren();
  const allSelected = options.length > 0 && selectedOptions.length === options.length;
  const toggleAllButton = document.createElement("button");
  toggleAllButton.type = "button";
  toggleAllButton.className = "module-filter-option module-filter-option-toggle-all";
  toggleAllButton.classList.toggle("is-selected", allSelected);

  const toggleAllLabel = document.createElement("span");
  toggleAllLabel.className = "module-filter-option-label";
  toggleAllLabel.textContent = "一键全选";

  const toggleAllCheck = document.createElement("span");
  toggleAllCheck.className = "module-filter-option-check";
  toggleAllCheck.textContent = allSelected ? "全不选" : "全选";

  toggleAllButton.disabled = !options.length;
  toggleAllButton.addEventListener("click", () => {
    updateAllModuleSelections(selectNode, !allSelected);
    renderModuleFilter(root, selectNode);
  });

  toggleAllButton.append(toggleAllLabel, toggleAllCheck);
  optionsNode.appendChild(toggleAllButton);

  if (!selectedOptions.length) {
    const placeholder = document.createElement("span");
    placeholder.className = "module-filter-placeholder";
    placeholder.textContent = "选择模块";
    selectedNode.appendChild(placeholder);
  } else {
    selectedOptions.forEach((option) => {
      const tag = document.createElement("span");
      tag.className = "module-filter-tag";

      const text = document.createElement("span");
      text.className = "module-filter-tag-text";
      text.textContent = option.textContent;

      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "module-filter-tag-remove";
      remove.textContent = "×";
      remove.setAttribute("aria-label", `删除 ${option.textContent}`);
      remove.addEventListener("click", (event) => {
        event.stopPropagation();
        updateModuleSelection(selectNode, option, false);
        renderModuleFilter(root, selectNode);
      });

      tag.append(text, remove);
      selectedNode.appendChild(tag);
    });
  }

  options.forEach((option) => {
    const optionButton = document.createElement("button");
    optionButton.type = "button";
    optionButton.className = "module-filter-option";
    optionButton.classList.toggle("is-selected", option.selected);

    const label = document.createElement("span");
    label.className = "module-filter-option-label";
    label.textContent = option.textContent;

    const check = document.createElement("span");
    check.className = "module-filter-option-check";
    check.textContent = option.selected ? "已选" : "未选";

    optionButton.addEventListener("click", () => {
      updateModuleSelection(selectNode, option, !option.selected);
      renderModuleFilter(root, selectNode);
    });

    optionButton.append(label, check);
    optionsNode.appendChild(optionButton);
  });
}

function initializeModuleFilters() {
  moduleFilterRoots.forEach((root) => {
    const nativeSelect = root.nextElementSibling;
    if (!(nativeSelect instanceof HTMLSelectElement)) {
      return;
    }
    const trigger = root.querySelector("[data-module-filter-trigger]");
    trigger?.addEventListener("click", (event) => {
      event.preventDefault();
      const shouldOpen = trigger.getAttribute("aria-expanded") !== "true";
      moduleFilterRoots.forEach((item) => {
        if (item !== root) {
          setModuleFilterOpen(item, false);
        }
      });
      setModuleFilterOpen(root, shouldOpen);
    });
    trigger?.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setModuleFilterOpen(root, false);
        return;
      }
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      event.preventDefault();
      const shouldOpen = trigger.getAttribute("aria-expanded") !== "true";
      moduleFilterRoots.forEach((item) => {
        if (item !== root) {
          setModuleFilterOpen(item, false);
        }
      });
      setModuleFilterOpen(root, shouldOpen);
    });
    nativeSelect.addEventListener("change", () => {
      renderModuleFilter(root, nativeSelect);
    });
    renderModuleFilter(root, nativeSelect);
  });

  document.addEventListener("click", (event) => {
    moduleFilterRoots.forEach((root) => {
      if (!root.contains(event.target)) {
        setModuleFilterOpen(root, false);
      }
    });
  });
}

function buildLogArchiveName(deviceType, startAt, endAt) {
  const compact = (value) => {
    const text = String(value || "").trim();
    if (!text) {
      return "00000000";
    }
    const [datePart = "", timePart = ""] = text.split(" ");
    const [, month = "00", day = "00"] = datePart.split("-");
    const [hour = "00", minute = "00"] = timePart.split(":");
    return `${month.padStart(2, "0")}${day.padStart(2, "0")}${hour.padStart(2, "0")}${minute.padStart(2, "0")}`;
  };
  const prefix = String(deviceType || "log").trim().toLowerCase() || "log";
  return `${prefix}-${compact(startAt)}-${compact(endAt)}.zip`;
}

function parseDownloadFilename(contentDisposition, fallbackName) {
  const source = String(contentDisposition || "");
  const utf8Match = source.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const basicMatch = source.match(/filename="([^"]+)"/i) || source.match(/filename=([^;]+)/i);
  if (basicMatch?.[1]) {
    return basicMatch[1].trim();
  }
  return fallbackName;
}

async function chooseLocalSaveTarget(suggestedName) {
  const picker = window.showSaveFilePicker;
  if (typeof picker !== "function") {
    return { supported: false, handle: null };
  }
  const handle = await picker({
    suggestedName,
    types: [
      {
        description: "ZIP 压缩包",
        accept: { "application/zip": [".zip"] },
      },
    ],
  });
  return { supported: true, handle };
}

async function saveBlobToLocalFile(blob, suggestedName, fileHandle = null) {
  if (fileHandle) {
    const writable = await fileHandle.createWritable();
    await writable.write(blob);
    await writable.close();
    return { method: "file-system-access", fileName: fileHandle.name || suggestedName };
  }
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = suggestedName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return { method: "browser-download", fileName: suggestedName };
}

async function downloadLogArchive({ deviceType, moduleSelectNode, statusNode, startPrefix, endPrefix, requireModuleSelection = true }) {
  const moduleNames = readSelectedModuleNames(moduleSelectNode);
  if (requireModuleSelection && !moduleNames.length) {
    throw new Error("请先在“模块筛选”中至少选择一个模块，再导出日志");
  }
  const startAt = readTimeRange(startPrefix);
  const endAt = readTimeRange(endPrefix);
  const fallbackName = buildLogArchiveName(deviceType, startAt, endAt);
  const saveTarget = await chooseLocalSaveTarget(fallbackName);
  const fileHandle = saveTarget?.handle || null;
  const params = new URLSearchParams({
    device_type: deviceType,
    start_at: startAt,
    end_at: endAt,
  });
  if (moduleNames.length) {
    params.set("module_names", moduleNames.join(","));
  }

  setLogStatus(
    statusNode,
    saveTarget?.supported
      ? "已选择保存位置，正在准备日志压缩包..."
      : "当前浏览器环境不支持本地路径选择框，将转为浏览器下载...",
  );
  const response = await fetch(`/api/download-log-archive?${params.toString()}`);
  if (!response.ok) {
    let errorMessage = `下载失败 (${response.status})`;
    try {
      const data = await response.json();
      errorMessage = (data && data.error) || errorMessage;
    } catch {
      const text = await response.text();
      if (text) {
        errorMessage = text;
      }
    }
    throw new Error(errorMessage);
  }

  const blob = await response.blob();
  const finalName = parseDownloadFilename(response.headers.get("Content-Disposition"), fallbackName);
  const result = await saveBlobToLocalFile(blob, finalName, fileHandle);
  setLogStatus(
    statusNode,
    result.method === "file-system-access"
      ? `日志压缩包已保存：${result.fileName}`
      : `日志压缩包已开始下载：${result.fileName}`,
  );
}

function appendLog(message, detail = "") {
  const timestamp = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  const block = [`[${timestamp}] ${message}`];
  if (detail) {
    block.push(detail);
  }
  const text = block.join("\n");
  console.info(text);
  if (!logOutput) {
    return;
  }
  logOutput.textContent = `${text}\n\n${logOutput.textContent}`.trim();
}

function buildRequestError(data, fallbackMessage = "请求失败") {
  const error = new Error((data && data.error) || fallbackMessage);
  if (data && typeof data === "object") {
    Object.assign(error, data);
  }
  return error;
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!data.ok) {
    throw buildRequestError(data);
  }
  return data;
}

function setRosOutput(node, text) {
  if (!node) {
    return;
  }
  node.textContent = text;
}

function setRosPageHint(message) {
  if (!rosPageHint) {
    return;
  }
  rosPageHint.textContent = message;
}

function updateRosTopicSummary() {
  if (rosSelectedTopicName) {
    rosSelectedTopicName.textContent = rosState.selectedTopic || "未选择 Topic";
  }
  if (rosSelectedTopicType) {
    rosSelectedTopicType.textContent = rosState.selectedTopicType || "-";
  }
  if (rosSelectedTopicDirection) {
    rosSelectedTopicDirection.textContent = rosState.selectedTopicDirection || "-";
  }
  if (rosTopicAvailabilityBadge) {
    rosTopicAvailabilityBadge.textContent = rosState.selectedTopic ? (rosState.topicAvailable ? "可用" : "未查询") : "未选择";
    rosTopicAvailabilityBadge.classList.toggle("is-available", Boolean(rosState.selectedTopic && rosState.topicAvailable));
  }
}

function updateRosPublishHistory() {
  if (!rosTopicPublishHistory) {
    return;
  }
  const record = rosState.lastPublishRecord;
  if (!record) {
    rosTopicPublishHistory.textContent = "暂无发布记录";
    return;
  }
  rosTopicPublishHistory.textContent = `${record.message}\n${record.time} · ${record.status}`;
}

function switchRosTab(tabName = "publish") {
  const normalizedTab = tabName === "subscribe" ? "subscribe" : "publish";
  rosState.activeTab = normalizedTab;
  if (rosPublishTabBtn) {
    const active = normalizedTab === "publish";
    rosPublishTabBtn.classList.toggle("is-active", active);
    rosPublishTabBtn.setAttribute("aria-selected", active ? "true" : "false");
  }
  if (rosSubscribeTabBtn) {
    const active = normalizedTab === "subscribe";
    rosSubscribeTabBtn.classList.toggle("is-active", active);
    rosSubscribeTabBtn.setAttribute("aria-selected", active ? "true" : "false");
  }
  if (rosPublishPanel) {
    rosPublishPanel.classList.toggle("is-active", normalizedTab === "publish");
    rosPublishPanel.hidden = normalizedTab !== "publish";
  }
  if (rosSubscribePanel) {
    rosSubscribePanel.classList.toggle("is-active", normalizedTab === "subscribe");
    rosSubscribePanel.hidden = normalizedTab !== "subscribe";
  }
}

function parseTopicDirection(infoText = "") {
  const normalizedText = String(infoText || "");
  const publisherMatches = normalizedText.match(/Publishers:\s*(?:\n|\r\n?)([\s\S]*?)(?:Subscribers:|$)/i);
  const subscriberMatches = normalizedText.match(/Subscribers:\s*(?:\n|\r\n?)([\s\S]*?)(?:$)/i);
  const publisherCount = publisherMatches?.[1] ? (publisherMatches[1].match(/^\s*\*/gm) || []).length : 0;
  const subscriberCount = subscriberMatches?.[1] ? (subscriberMatches[1].match(/^\s*\*/gm) || []).length : 0;
  if (publisherCount > 0 && subscriberCount > 0) {
    return "pub/sub";
  }
  if (publisherCount > 0) {
    return "pub";
  }
  if (subscriberCount > 0) {
    return "sub";
  }
  return "-";
}

function buildRosStatusDot(index) {
  const palette = ["#18a06f", "#7c5cff", "#2f76ff", "#f0b429", "#5b95d6"];
  return palette[index % palette.length];
}

function rosDefaultValueForType(typeName, childValue) {
  const normalizedType = String(typeName || "").trim();
  const baseType = normalizedType.replace(/\[[^\]]*\]$/, "");
  const isArray = /\[[^\]]*\]$/.test(normalizedType);
  const complexValue = childValue && typeof childValue === "object" ? childValue : null;
  let value;
  if (baseType === "string") {
    value = "";
  } else if (baseType === "bool") {
    value = false;
  } else if (/^(u?int|byte|char)/.test(baseType)) {
    value = 0;
  } else if (/^(float|double)/.test(baseType)) {
    value = 0.0;
  } else if (baseType === "time" || baseType === "duration") {
    value = { secs: 0, nsecs: 0 };
  } else if (complexValue) {
    value = complexValue;
  } else if (baseType.includes("/")) {
    value = {};
  } else {
    value = "";
  }
  if (isArray) {
    if (complexValue) {
      return [complexValue];
    }
    return [];
  }
  return value;
}

function parseRosDefinitionObject(definitionText, { requestOnly = false } = {}) {
  const rawLines = String(definitionText || "").split(/\r?\n/);
  const effectiveLines = [];
  for (const rawLine of rawLines) {
    const trimmed = rawLine.trimEnd();
    if (!trimmed.trim()) {
      continue;
    }
    if (requestOnly && trimmed.trim() === "---") {
      break;
    }
    if (trimmed.trim().startsWith("MSG:")) {
      continue;
    }
    effectiveLines.push(trimmed);
  }
  const lines = effectiveLines
    .map((line) => ({
      indent: line.match(/^ */)?.[0]?.length || 0,
      text: line.trim(),
    }))
    .filter((entry) => entry.text && entry.text !== "---");

  function parseBlock(startIndex, indentLevel) {
    const result = {};
    let index = startIndex;
    while (index < lines.length) {
      const entry = lines[index];
      if (entry.indent < indentLevel) {
        break;
      }
      if (entry.indent > indentLevel) {
        index += 1;
        continue;
      }
      if (entry.text.includes("=")) {
        index += 1;
        continue;
      }
      const match = entry.text.match(/^([A-Za-z][A-Za-z0-9_/]*(?:\[[^\]]*\])?)\s+([A-Za-z][A-Za-z0-9_]*)$/);
      if (!match) {
        index += 1;
        continue;
      }
      const [, fieldType, fieldName] = match;
      index += 1;
      let childValue = null;
      if (index < lines.length && lines[index].indent > indentLevel) {
        const parsedChild = parseBlock(index, lines[index].indent);
        childValue = parsedChild.value;
        index = parsedChild.nextIndex;
      }
      result[fieldName] = rosDefaultValueForType(fieldType, childValue);
    }
    return { value: result, nextIndex: index };
  }

  return parseBlock(0, 0).value;
}

function buildRosTemplateFromDefinition(definitionText, options = {}) {
  const parsedObject = parseRosDefinitionObject(definitionText, options);
  return JSON.stringify(parsedObject, null, 2);
}

function toPythonStringLiteral(value) {
  return JSON.stringify(String(value ?? ""));
}

function splitRosTypeName(typeName) {
  const normalized = String(typeName || "").trim();
  const [packageName = "", kind = "", type = ""] = normalized.split("/");
  return {
    packageName,
    kind,
    type: type || kind || normalized,
  };
}

function buildPythonCommentBlock(text = "", prefix = "# ") {
  const normalizedText = String(text || "").trim();
  if (!normalizedText) {
    return `${prefix}TODO: 按实际消息字段补充内容`;
  }
  return normalizedText
    .split(/\r?\n/)
    .map((line) => `${prefix}${line}`)
    .join("\n");
}

function buildRosTopicPythonExample(mode) {
  const topicName = requireSelectedRosName("topic");
  const typeName = String(rosState.selectedTopicType || rosTopicPubTypeInput?.value || "").trim();
  if (!typeName) {
    throw new Error("当前 Topic 还没有可用的消息类型");
  }
  const { packageName, type } = splitRosTypeName(typeName);
  if (!packageName || !type) {
    throw new Error(`无法解析 Topic 类型：${typeName}`);
  }

  if (mode === "subscribe") {
    return `#!/usr/bin/env python3
import rospy
from ${packageName}.msg import ${type}


def callback(msg):
    rospy.loginfo(msg)


def main():
    rospy.init_node("topic_subscriber_demo", anonymous=True)
    rospy.Subscriber(${toPythonStringLiteral(topicName)}, ${type}, callback)
    rospy.loginfo("subscribing ${topicName}")
    rospy.spin()


if __name__ == "__main__":
    main()
`;
  }

  const messageTemplate = String(rosTopicPubMessageInput?.value || "").trim();
  return `#!/usr/bin/env python3
import rospy
from ${packageName}.msg import ${type}


def main():
    rospy.init_node("topic_publisher_demo", anonymous=True)
    publisher = rospy.Publisher(${toPythonStringLiteral(topicName)}, ${type}, queue_size=1)
    rospy.sleep(0.5)

    msg = ${type}()
${buildPythonCommentBlock(messageTemplate, "    # ")}
    publisher.publish(msg)
    rospy.loginfo("published ${topicName}")


if __name__ == "__main__":
    main()
`;
}

function buildRosServicePythonExample() {
  const serviceName = requireSelectedRosName("service");
  const typeName = String(rosState.selectedServiceType || "").trim();
  if (!typeName) {
    throw new Error("当前 Service 还没有可用的类型");
  }
  const { packageName, type } = splitRosTypeName(typeName);
  if (!packageName || !type) {
    throw new Error(`无法解析 Service 类型：${typeName}`);
  }
  const requestTemplate = String(rosServiceCallRequestInput?.value || "").trim();
  return `#!/usr/bin/env python3
import rospy
from ${packageName}.srv import ${type}, ${type}Request


def main():
    rospy.init_node("service_client_demo", anonymous=True)
    rospy.wait_for_service(${toPythonStringLiteral(serviceName)})
    client = rospy.ServiceProxy(${toPythonStringLiteral(serviceName)}, ${type})

    request = ${type}Request()
${buildPythonCommentBlock(requestTemplate, "    # ")}
    response = client(request)
    print(response)


if __name__ == "__main__":
    main()
`;
}

function shouldKeepRosName(name, kind) {
  const normalizedName = String(name || "").trim();
  const prefixes = kind === "topic" ? rosFilterConfig.topicPrefixes : rosFilterConfig.servicePrefixes;
  const exactNames = kind === "topic" ? rosFilterConfig.topicNames : rosFilterConfig.serviceNames;
  if (!normalizedName) {
    return false;
  }
  if (!prefixes.length && !exactNames.length) {
    return true;
  }
  if (exactNames.includes(normalizedName)) {
    return true;
  }
  return prefixes.some((prefix) => normalizedName.startsWith(prefix));
}

async function loadSelectedTopicSummary(topicName) {
  if (!topicName) {
    rosState.selectedTopicType = "";
    rosState.selectedTopicDefinition = "";
    rosState.selectedTopicDirection = "";
    rosState.topicAvailable = false;
    setRosOutput(rosTopicDefinitionOutput, "选择 Topic 后，这里会显示对应的 msg 定义。");
    updateRosTopicSummary();
    renderRosNameList("topic");
    return;
  }
  rosState.selectedTopic = topicName;
  rosState.selectedTopicType = "";
  rosState.selectedTopicDirection = "";
  rosState.topicAvailable = false;
  updateRosTopicSummary();
  renderRosNameList("topic");
  try {
    const [typeData, infoData] = await Promise.all([
      request(`/api/ros/topic-type?name=${encodeURIComponent(topicName)}`),
      request(`/api/ros/topic-info?name=${encodeURIComponent(topicName)}`),
    ]);
    rosState.selectedTopicType = String(typeData.output || "").split(/\r?\n/, 1)[0].trim();
    rosState.selectedTopicDirection = parseTopicDirection(infoData.output || "");
    rosState.topicAvailable = true;
    if (rosTopicPubTypeInput) {
      rosTopicPubTypeInput.value = rosState.selectedTopicType;
    }
    if (rosState.selectedTopicType && rosTopicPubMessageInput) {
      try {
        const definitionData = await request(`/api/ros/message-definition?type_name=${encodeURIComponent(rosState.selectedTopicType)}`);
        rosState.selectedTopicDefinition = String(definitionData.output || "");
        setRosOutput(rosTopicDefinitionOutput, rosState.selectedTopicDefinition || "未获取到消息定义");
        rosTopicPubMessageInput.value = buildRosTemplateFromDefinition(definitionData.template_output || definitionData.output || "");
      } catch (definitionError) {
        setRosOutput(rosTopicDefinitionOutput, `加载消息定义失败：${definitionError.message}`);
        appendLog("加载 Topic 消息模板失败", definitionError.message);
      }
    } else {
      setRosOutput(rosTopicDefinitionOutput, "当前 Topic 没有可用的消息类型。");
    }
    setRosOutput(rosTopicDetailOutput, infoData.output || "命令无输出");
  } catch (error) {
    setRosOutput(rosTopicDefinitionOutput, `Topic 定义加载失败：${error.message}`);
    setRosOutput(rosTopicDetailOutput, `Topic 摘要加载失败：${error.message}`);
  } finally {
    updateRosTopicSummary();
  }
}

function renderRosNameList(kind) {
  const isTopic = kind === "topic";
  const listNode = isTopic ? rosTopicList : rosServiceList;
  const searchNode = isTopic ? rosTopicSearchInput : rosServiceSearchInput;
  const selectedName = isTopic ? rosState.selectedTopic : rosState.selectedService;
  const items = isTopic ? rosState.topics : rosState.services;
  if (!listNode) {
    return;
  }
  const keyword = String(searchNode?.value || "").trim().toLowerCase();
  const filteredItems = items.filter((name) => !keyword || name.toLowerCase().includes(keyword));
  if (isTopic && rosTopicListCount) {
    rosTopicListCount.textContent = `共 ${items.length} 个 Topics`;
  }
  if (!isTopic && rosServiceListCount) {
    rosServiceListCount.textContent = `共 ${items.length} 个 Services`;
  }
  listNode.replaceChildren();
  if (!filteredItems.length) {
    const empty = document.createElement("div");
    empty.className = "ros-name-empty";
    empty.textContent = keyword ? "没有匹配的接口" : "暂无接口数据";
    listNode.appendChild(empty);
    return;
  }
  filteredItems.forEach((name, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ros-name-item";
    if (name === selectedName) {
      button.classList.add("is-active");
    }
    if (isTopic) {
      const label = document.createElement("span");
      label.className = "ros-name-item-label";
      label.textContent = name;
      const dot = document.createElement("span");
      dot.className = "ros-name-item-dot";
      dot.style.backgroundColor = buildRosStatusDot(index);
      button.append(label, dot);
    } else {
      button.textContent = name;
    }
    button.addEventListener("click", () => {
      if (isTopic) {
        loadSelectedTopicSummary(name);
      } else {
        rosState.selectedService = name;
        rosState.selectedServiceType = "";
        rosState.selectedServiceDefinition = "";
        if (rosSelectedServiceName) {
          rosSelectedServiceName.textContent = name;
        }
        if (rosSelectedServiceType) {
          rosSelectedServiceType.textContent = "-";
        }
        setRosOutput(rosServiceDefinitionOutput, `已选中 Service：${name}\n正在加载 srv 定义...`);
        setRosOutput(rosServiceDetailOutput, `已选中 Service：${name}\n正在准备 call 模板...`);
        request(`/api/ros/service-definition?name=${encodeURIComponent(name)}`)
          .then((data) => {
            rosState.selectedServiceType = String(data.type_name || "").trim();
            rosState.selectedServiceDefinition = String(data.output || "");
            if (rosSelectedServiceType) {
              rosSelectedServiceType.textContent = rosState.selectedServiceType || "-";
            }
            setRosOutput(rosServiceDefinitionOutput, rosState.selectedServiceDefinition || "未获取到服务定义");
            if (rosServiceCallRequestInput) {
              rosServiceCallRequestInput.value = buildRosTemplateFromDefinition(data.template_output || data.output || "", { requestOnly: true });
            }
            setRosOutput(rosServiceDetailOutput, `已选中 Service：${name}\n点击上方按钮查看 info / type 或执行 call。`);
          })
          .catch((error) => {
            appendLog("加载 Service 请求模板失败", error.message);
            setRosOutput(rosServiceDefinitionOutput, `加载服务定义失败：${error.message}`);
            setRosOutput(rosServiceDetailOutput, `已选中 Service：${name}\n加载 call 模板失败：${error.message}`);
          });
      }
      renderRosNameList(kind);
    });
    listNode.appendChild(button);
  });
}

async function loadRosNames(kind, { silent = false } = {}) {
  const isTopic = kind === "topic";
  const url = isTopic ? "/api/ros/topics" : "/api/ros/services";
  const loadingText = isTopic ? "正在加载 Topic 列表..." : "正在加载 Service 列表...";
  const outputNode = isTopic ? rosTopicDetailOutput : rosServiceDetailOutput;
  if (!silent) {
    setRosOutput(outputNode, loadingText);
  }
  const data = await request(url);
  const items = (Array.isArray(data.items) ? data.items : []).filter((name) => shouldKeepRosName(name, kind));
  if (isTopic) {
    rosState.topics = items;
    rosState.hasLoadedTopics = true;
    if (!items.includes(rosState.selectedTopic)) {
      rosState.selectedTopic = "";
      rosState.selectedTopicType = "";
      rosState.selectedTopicDefinition = "";
      rosState.selectedTopicDirection = "";
      rosState.topicAvailable = false;
      if (rosSelectedTopicName) {
        rosSelectedTopicName.textContent = "未选择 Topic";
      }
      setRosOutput(rosTopicDefinitionOutput, "选择 Topic 后，这里会显示对应的 msg 定义。");
    }
  } else {
    rosState.services = items;
    rosState.hasLoadedServices = true;
    if (!items.includes(rosState.selectedService)) {
      rosState.selectedService = "";
      rosState.selectedServiceType = "";
      rosState.selectedServiceDefinition = "";
      if (rosSelectedServiceName) {
        rosSelectedServiceName.textContent = "未选择 Service";
      }
      if (rosSelectedServiceType) {
        rosSelectedServiceType.textContent = "-";
      }
      setRosOutput(rosServiceDefinitionOutput, "选择 Service 后，这里会显示对应的 srv 定义。");
    }
  }
  renderRosNameList(kind);
  if (!silent) {
    setRosOutput(outputNode, `${isTopic ? "Topic" : "Service"} 列表已刷新，共 ${items.length} 项。`);
  }
  if (isTopic) {
    setRosPageHint(`提示：已加载 ${items.length} 个 Topics，Services 缓存 ${rosState.services.length} 项`);
  } else {
    setRosPageHint(`提示：Topics 缓存 ${rosState.topics.length} 项，已加载 ${items.length} 个 Services`);
  }
}

async function ensureRosPageLoaded() {
  if (!rosState.hasLoadedTopics) {
    try {
      await loadRosNames("topic", { silent: true });
    } catch (error) {
      setRosOutput(rosTopicDetailOutput, `加载 Topic 列表失败：${error.message}`);
    }
  }
  if (!rosState.hasLoadedServices) {
    try {
      await loadRosNames("service", { silent: true });
    } catch (error) {
      setRosOutput(rosServiceDetailOutput, `加载 Service 列表失败：${error.message}`);
    }
  }
}

function requireSelectedRosName(kind) {
  const isTopic = kind === "topic";
  const selectedName = isTopic ? rosState.selectedTopic : rosState.selectedService;
  if (!selectedName) {
    throw new Error(`请先选择${isTopic ? " Topic" : " Service"}`);
  }
  return selectedName;
}

async function runRosTopicAction(action) {
  const topicName = requireSelectedRosName("topic");
  const outputNode = action === "pub" ? rosTopicPublishOutput : rosTopicDetailOutput;
  setRosOutput(outputNode, `正在执行 ${action}：${topicName}`);
  let data;
  if (action === "info") {
    data = await request(`/api/ros/topic-info?name=${encodeURIComponent(topicName)}`);
  } else if (action === "type") {
    data = await request(`/api/ros/topic-type?name=${encodeURIComponent(topicName)}`);
  } else if (action === "echo") {
    data = await request(`/api/ros/topic-echo?name=${encodeURIComponent(topicName)}`);
  } else if (action === "pub") {
    const messageType = String(rosTopicPubTypeInput?.value || "").trim();
    if (!messageType) {
      throw new Error("请先填写 pub 消息类型");
    }
    const messageText = String(rosTopicPubMessageInput?.value || "").trim();
    data = await request("/api/ros/topic-pub", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: topicName,
        message_type: messageType,
        message: messageText,
      }),
    });
    rosState.lastPublishRecord = {
      message: messageText || "(空消息)",
      time: new Date().toLocaleString("zh-CN", { hour12: false }),
      status: "成功",
    };
    updateRosPublishHistory();
  } else {
    throw new Error(`不支持的 Topic 动作: ${action}`);
  }
  setRosOutput(outputNode, data.output || "命令无输出");
  appendLog(`ROS Topic ${action}`, topicName);
}

async function runRosServiceAction(action) {
  const serviceName = requireSelectedRosName("service");
  setRosOutput(rosServiceDetailOutput, `正在执行 ${action}：${serviceName}`);
  let data;
  if (action === "info") {
    data = await request(`/api/ros/service-info?name=${encodeURIComponent(serviceName)}`);
  } else if (action === "type") {
    data = await request(`/api/ros/service-type?name=${encodeURIComponent(serviceName)}`);
  } else if (action === "call") {
    data = await request("/api/ros/service-call", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: serviceName,
        request: String(rosServiceCallRequestInput?.value || ""),
      }),
    });
  } else {
    throw new Error(`不支持的 Service 动作: ${action}`);
  }
  setRosOutput(rosServiceDetailOutput, data.output || "命令无输出");
  appendLog(`ROS Service ${action}`, serviceName);
}

function xhrRequest(url, options = {}) {
  const { method = "GET", headers = {}, body = null, onUploadProgress = null } = options;
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url, true);
    xhr.responseType = "json";
    Object.entries(headers).forEach(([key, value]) => {
      xhr.setRequestHeader(key, value);
    });
    xhr.onload = () => {
      let data = xhr.response;
      if (!data && xhr.responseText) {
        try {
          data = JSON.parse(xhr.responseText);
        } catch {
          data = null;
        }
      }
      if (xhr.status >= 200 && xhr.status < 300 && data && data.ok !== false) {
        resolve(data);
        return;
      }
      reject(buildRequestError(data, `请求失败 (${xhr.status})`));
    };
    xhr.onerror = () => reject(new Error("网络请求失败"));
    if (xhr.upload && onUploadProgress) {
      xhr.upload.onprogress = (event) => {
        onUploadProgress(event.loaded, event.total, event.lengthComputable);
      };
    }
    xhr.send(body);
  });
}

function updateConnectionStatus(connected) {
  statusText.textContent = connected ? "已连接" : "未连接";
  statusDot.classList.toggle("online", connected);
  statusDot.classList.toggle("offline", !connected);
}

function getConnectField(name) {
  return connectForm.elements.namedItem(name);
}

function normalizeConnectionCacheItem(item) {
  if (!item || typeof item !== "object") {
    return null;
  }
  const host = String(item.host || "").trim();
  const port = String(item.port || "").trim() || DEFAULT_CONNECTION_FORM.port;
  const username = String(item.username || "").trim();
  const password = typeof item.password === "string" ? item.password : String(item.password || "");
  const picoHost = String(item.pico_host || "").trim();
  const picoPort = String(item.pico_port || "").trim() || DEFAULT_CONNECTION_FORM.pico_port;
  const picoUsername = String(item.pico_username || "").trim();
  const picoPassword = typeof item.pico_password === "string" ? item.pico_password : String(item.pico_password || "");
  if (!host || !username) {
    return null;
  }
  return {
    id: `${host}|${port}|${username}`,
    host,
    port,
    username,
    password,
    pico_host: picoHost,
    pico_port: picoPort,
    pico_username: picoUsername,
    pico_password: picoPassword,
    savedAt: String(item.savedAt || item.saved_at || ""),
  };
}

function buildSavedConnectionLabel(connection) {
  const picoPart = connection.pico_host
    ? ` · PICO ${connection.pico_host}:${connection.pico_port} · ${connection.pico_username || "-"}`
    : "";
  return `ORIN ${connection.host}:${connection.port} · ${connection.username}${picoPart}`;
}

function renderSavedConnectionSummary() {
  if (!savedConnectionSummary) {
    return;
  }
  const selectedConnection = savedConnectionsCache.find((connection) => connection.id === savedConnectionSelect?.value);
  const fallbackConnection = selectedConnection || savedConnectionsCache[0];
  if (!fallbackConnection) {
    savedConnectionSummary.textContent = "暂无缓存连接";
    return;
  }
  savedConnectionSummary.textContent = `最近使用 · ${buildSavedConnectionLabel(fallbackConnection)}`;
}

function setSavedConnections(connections, { selectedId = "" } = {}) {
  savedConnectionsCache = (Array.isArray(connections) ? connections : [])
    .map((item) => normalizeConnectionCacheItem(item))
    .filter(Boolean);
  renderSavedConnectionSelect(selectedId);
  renderSavedConnectionSummary();
}

function renderSavedConnectionSelect(selectedId = "") {
  if (!savedConnectionSelect) {
    return;
  }
  const currentValue = selectedId || savedConnectionsCache[0]?.id || savedConnectionSelect.value || "";
  savedConnectionSelect.replaceChildren();

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = savedConnectionsCache.length ? "选择已缓存连接" : "暂无缓存连接";
  savedConnectionSelect.appendChild(placeholder);

  savedConnectionsCache.forEach((connection, index) => {
    const option = document.createElement("option");
    option.value = connection.id;
    option.textContent = `${index === 0 ? "最近使用 · " : ""}${buildSavedConnectionLabel(connection)}`;
    savedConnectionSelect.appendChild(option);
  });

  if (savedConnectionsCache.some((connection) => connection.id === currentValue)) {
    savedConnectionSelect.value = currentValue;
  } else {
    savedConnectionSelect.value = "";
  }
  renderSavedConnectionSummary();
}

function readConnectionForm() {
  return {
    host: String(getConnectField("host").value || "").trim(),
    port: String(getConnectField("port").value || "").trim() || DEFAULT_CONNECTION_FORM.port,
    username: String(getConnectField("username").value || "").trim(),
    password: String(getConnectField("password").value || ""),
    pico_host: String(getConnectField("pico_host").value || "").trim(),
    pico_port: String(getConnectField("pico_port").value || "").trim() || DEFAULT_CONNECTION_FORM.pico_port,
    pico_username: String(getConnectField("pico_username").value || "").trim(),
    pico_password: String(getConnectField("pico_password").value || ""),
  };
}

function applyConnectionToForm(connection, { preservePassword = false } = {}) {
  if (!connection) {
    return;
  }
  getConnectField("host").value = connection.host;
  getConnectField("port").value = connection.port;
  getConnectField("username").value = connection.username;
  if (!preservePassword || !getConnectField("password").value) {
    getConnectField("password").value = connection.password;
  }
  getConnectField("pico_host").value = connection.pico_host || "";
  getConnectField("pico_port").value = connection.pico_port || DEFAULT_CONNECTION_FORM.pico_port;
  getConnectField("pico_username").value = connection.pico_username || "";
  if (!preservePassword || !getConnectField("pico_password").value) {
    getConnectField("pico_password").value = connection.pico_password || "";
  }
  if (savedConnectionSelect) {
    savedConnectionSelect.value = connection.id;
  }
  renderSavedConnectionSummary();
}

function isDefaultConnectionForm(connection) {
  return (
    connection.host === DEFAULT_CONNECTION_FORM.host &&
    connection.port === DEFAULT_CONNECTION_FORM.port &&
    connection.username === DEFAULT_CONNECTION_FORM.username &&
    connection.pico_host === DEFAULT_CONNECTION_FORM.pico_host &&
    connection.pico_port === DEFAULT_CONNECTION_FORM.pico_port &&
    connection.pico_username === DEFAULT_CONNECTION_FORM.pico_username &&
    !connection.password &&
    !connection.pico_password
  );
}

function hydrateConnectionCache(savedConnections = []) {
  setSavedConnections(savedConnections);

  if (!savedConnectionsCache.length) {
    return;
  }
  applyConnectionToForm(savedConnectionsCache[0], { preservePassword: true });
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  if (value < 1024 * 1024 * 1024) {
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function setPackageDeployFileMeta(file = null) {
  if (!packageDeployDropzone || !packageDeployFileMeta) {
    return;
  }
  if (!file) {
    packageDeployDropzone.classList.remove("has-file");
    packageDeployFileMeta.textContent = "当前未选择文件";
    return;
  }
  packageDeployDropzone.classList.add("has-file");
  packageDeployFileMeta.textContent = `${file.name} · ${formatBytes(file.size)}`;
}

function setPackageDeployFile(file = null) {
  if (!packageDeployFileInput) {
    return;
  }
  if (!file) {
    packageDeployFileInput.value = "";
    setPackageDeployFileMeta(null);
    return;
  }

  const transfer = new DataTransfer();
  transfer.items.add(file);
  packageDeployFileInput.files = transfer.files;
  setPackageDeployFileMeta(file);
}

function setModuleDeployFileMeta(file = null) {
  if (!moduleDeployDropzone || !moduleDeployFileMeta) {
    return;
  }
  if (!file) {
    moduleDeployDropzone.classList.remove("has-file");
    moduleDeployFileMeta.textContent = "当前未选择文件";
    return;
  }
  moduleDeployDropzone.classList.add("has-file");
  moduleDeployFileMeta.textContent = `${file.name} · ${formatBytes(file.size)}`;
}

function setModuleDeployFile(file = null) {
  if (!moduleDeployFileInput) {
    return;
  }
  if (!file) {
    moduleDeployFileInput.value = "";
    setModuleDeployFileMeta(null);
    return;
  }

  const transfer = new DataTransfer();
  transfer.items.add(file);
  moduleDeployFileInput.files = transfer.files;
  setModuleDeployFileMeta(file);
}

function createUploadProgressView(id) {
  const root = document.getElementById(id);
  if (!root) {
    return null;
  }
  return {
    root,
    bar: root.querySelector(".upload-progress-bar"),
    percent: root.querySelector(".upload-progress-percent"),
    text: root.querySelector(".upload-progress-text"),
    meta: root.querySelector(".upload-progress-meta"),
  };
}

function createDeployFlowView(id) {
  const root = document.getElementById(id);
  if (!root) {
    return null;
  }
  const steps = {};
  root.querySelectorAll("[data-flow-step]").forEach((item) => {
    steps[item.dataset.flowStep] = item;
  });
  return {
    root,
    status: root.querySelector(".deploy-flow-status"),
    steps,
  };
}

function deployActionLabel(deployMode = "package") {
  return "安装";
}

function deployFileNoun(deployMode = "package") {
  if (deployMode === "package") {
    return "firmware 文件";
  }
  if (deployMode === "module") {
    return "模块 deb 文件";
  }
  return "部署文件";
}

function setDeployFlowStepState(step, state = "pending") {
  if (!step) {
    return;
  }
  step.classList.toggle("is-active", state === "active");
  step.classList.toggle("is-done", state === "done");
  step.classList.toggle("is-error", state === "error");
}

function renderDeployFlow(view, { summary = "等待开始", stepStates = {} } = {}) {
  if (!view || !view.root) {
    return;
  }
  if (view.status) {
    view.status.textContent = summary;
  }
  ["uploading", "installing", "succeeded", "failed"].forEach((stepKey) => {
    setDeployFlowStepState(view.steps[stepKey], stepStates[stepKey] || "pending");
  });
}

function isDeployTask(task, deployMode) {
  return task && task.type === "deployment" && task.metadata && task.metadata.deploy_mode === deployMode;
}

function findCurrentDeployTask(tasks = [], deployMode) {
  if (currentDeployTaskIds[deployMode]) {
    const currentTask = tasks.find((task) => task.id === currentDeployTaskIds[deployMode]);
    if (currentTask) {
      return currentTask;
    }
  }
  const latestTask = tasks.find((task) => isDeployTask(task, deployMode));
  if (latestTask) {
    currentDeployTaskIds[deployMode] = latestTask.id;
    return latestTask;
  }
  return null;
}

function deriveDeployFlow(task = null, progress = null, deployMode = "package") {
  const actionLabel = deployActionLabel(deployMode);
  const stepStates = {
    uploading: "pending",
    installing: "pending",
    succeeded: "pending",
    failed: "pending",
  };
  let summary = "等待开始";

  const taskStatus = String(task && task.status ? task.status : "");
  const taskError = String(task && task.error ? task.error : "");
  const taskResult = task && task.result && typeof task.result === "object" ? task.result : {};
  const uploadDone = Boolean(progress && progress.done);
  const usedExistingRemote = Boolean(task && task.metadata && task.metadata.used_existing_remote);
  const progressMessage = String(progress && progress.message ? progress.message : "");
  const progressError = String(progress && progress.error ? progress.error : "");
  const installStarted =
    taskStatus === "succeeded" ||
    Boolean(taskResult.install_result) ||
    taskError.includes("安装") ||
    taskError.includes("健康检查") ||
    taskError.includes("启动") ||
    progressMessage.includes("识别机型") ||
    progressError.includes("识别") ||
    progressError.includes("安装");

  if (progress && progress.phase === "failed") {
    if (installStarted) {
      stepStates.uploading = "done";
      stepStates.installing = "error";
      stepStates.failed = "error";
      summary = `${actionLabel}失败`;
    } else {
      stepStates.uploading = "error";
      stepStates.failed = "error";
      summary = "上传失败";
    }
    return { summary, stepStates };
  }

  if (taskStatus === "succeeded" || taskStatus === "warning") {
    stepStates.uploading = "done";
    stepStates.installing = "done";
    stepStates.succeeded = "done";
    summary = taskStatus === "warning" ? `${actionLabel}成功（有告警）` : `${actionLabel}成功`;
    return { summary, stepStates };
  }

  if (taskStatus === "failed") {
    if (usedExistingRemote || uploadDone || installStarted) {
      stepStates.uploading = "done";
      stepStates.installing = "error";
      stepStates.failed = "error";
      summary = `${actionLabel}失败`;
    } else {
      stepStates.uploading = "error";
      stepStates.failed = "error";
      summary = "上传失败";
    }
    return { summary, stepStates };
  }

  if (taskStatus === "running") {
    if (usedExistingRemote || uploadDone) {
      stepStates.uploading = "done";
      stepStates.installing = "active";
      summary = `${actionLabel}中`;
    } else {
      stepStates.uploading = "active";
      summary = "上传中";
    }
    return { summary, stepStates };
  }

  if (taskStatus === "pending") {
    if (usedExistingRemote || uploadDone) {
      stepStates.uploading = "done";
      stepStates.installing = "active";
      summary = `${actionLabel}中`;
    } else {
      stepStates.uploading = "active";
      summary = "上传中";
    }
    return { summary, stepStates };
  }

  if (progress) {
    if (progress.done) {
      stepStates.uploading = "done";
      summary = "上传完成";
    } else {
      stepStates.uploading = "active";
      summary = "上传中";
    }
  }
  return { summary, stepStates };
}

function syncDeployFlow(deployMode, { tasks = null, task = null, progress } = {}) {
  if (progress !== undefined) {
    deployProgressSnapshots[deployMode] = progress;
  }

  let resolvedTask = task;
  if (!resolvedTask && Array.isArray(tasks)) {
    resolvedTask = findCurrentDeployTask(tasks, deployMode);
  }
  if (resolvedTask && isDeployTask(resolvedTask, deployMode)) {
    currentDeployTaskIds[deployMode] = resolvedTask.id;
  }

  renderDeployFlow(deployFlowViews[deployMode], deriveDeployFlow(resolvedTask, deployProgressSnapshots[deployMode], deployMode));
}

function renderUploadProgress(view, { percent = 0, text = "等待开始", meta = "", state = "active" }) {
  if (!view || !view.root) {
    return;
  }
  const safePercent = Math.max(0, Math.min(100, Number(percent || 0)));
  view.root.hidden = false;
  view.root.classList.toggle("is-success", state === "success");
  view.root.classList.toggle("is-error", state === "error");
  view.bar.style.width = `${safePercent}%`;
  view.percent.textContent = `${Math.round(safePercent)}%`;
  view.text.textContent = text;
  view.meta.textContent = meta;
}

function resetUploadProgress(view, title) {
  if (!view) {
    return;
  }
  renderUploadProgress(view, { percent: 0, text: title, meta: "等待开始", state: "active" });
}

Object.values(uploadProgressViews)
  .filter(Boolean)
  .forEach((view) => {
    resetUploadProgress(view, "等待上传");
  });
renderDeployFlow(deployFlowViews.package, deriveDeployFlow(null, null, "package"));
renderDeployFlow(deployFlowViews.module, deriveDeployFlow(null, null, "module"));
setPackageDeployFileMeta(packageDeployFileInput && packageDeployFileInput.files ? packageDeployFileInput.files[0] : null);
resetPackageDeployStage({ keepHint: true });
setModuleDeployFileMeta(moduleDeployFileInput && moduleDeployFileInput.files ? moduleDeployFileInput.files[0] : null);

if (packageDeployDropzone && packageDeployFileInput) {
  packageDeployDropzone.addEventListener("click", () => {
    packageDeployFileInput.click();
  });

  packageDeployDropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      packageDeployFileInput.click();
    }
  });

  packageDeployFileInput.addEventListener("change", () => {
    setPackageDeployFileMeta(packageDeployFileInput.files && packageDeployFileInput.files[0] ? packageDeployFileInput.files[0] : null);
    resetPackageDeployStage();
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    packageDeployDropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      packageDeployDropzone.classList.add("is-dragover");
    });
  });

  ["dragleave", "dragend"].forEach((eventName) => {
    packageDeployDropzone.addEventListener(eventName, () => {
      packageDeployDropzone.classList.remove("is-dragover");
    });
  });

  packageDeployDropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    packageDeployDropzone.classList.remove("is-dragover");
    const droppedFiles = event.dataTransfer && event.dataTransfer.files ? Array.from(event.dataTransfer.files) : [];
    const selectedFile = droppedFiles.find((file) => file && file.name);
    if (!selectedFile) {
      return;
    }
    setPackageDeployFile(selectedFile);
    resetPackageDeployStage();
    appendLog("已拖入整包部署文件", selectedFile.name);
  });
}

packageDeviceType?.addEventListener("change", () => {
  resetPackageDeployStage();
});

const packageServerFilePathInput = packageDeployForm?.elements?.namedItem("server_file_path");
if (packageServerFilePathInput instanceof HTMLInputElement) {
  packageServerFilePathInput.addEventListener("input", () => {
    if (!packageAutoDeploySelect || !packageAutoDeploySelect.value) {
      manualPackageServerFilePath = String(packageServerFilePathInput.value || "").trim();
    }
    resetPackageDeployStage();
  });
}

packageAutoDeploySelect?.addEventListener("change", () => {
  applyPackageAutoDeploySelection();
  resetPackageDeployStage();
});

const moduleServerFilePathInput = moduleDeployForm?.elements?.namedItem("server_file_path");
if (moduleServerFilePathInput instanceof HTMLInputElement) {
  moduleServerFilePathInput.addEventListener("input", () => {
    if (!moduleAutoDeploySelect || !moduleAutoDeploySelect.value) {
      manualModuleServerFilePath = String(moduleServerFilePathInput.value || "").trim();
    }
  });
}

moduleAutoDeploySelect?.addEventListener("change", () => {
  applyModuleAutoDeploySelection();
});

moduleSelect?.addEventListener("change", () => {
  if (moduleAutoDeploySelect?.value) {
    applyModuleAutoDeploySelection();
  }
});

if (moduleDeployDropzone && moduleDeployFileInput) {
  moduleDeployDropzone.addEventListener("click", () => {
    moduleDeployFileInput.click();
  });

  moduleDeployDropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      moduleDeployFileInput.click();
    }
  });

  moduleDeployFileInput.addEventListener("change", () => {
    setModuleDeployFileMeta(moduleDeployFileInput.files && moduleDeployFileInput.files[0] ? moduleDeployFileInput.files[0] : null);
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    moduleDeployDropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      moduleDeployDropzone.classList.add("is-dragover");
    });
  });

  ["dragleave", "dragend"].forEach((eventName) => {
    moduleDeployDropzone.addEventListener(eventName, () => {
      moduleDeployDropzone.classList.remove("is-dragover");
    });
  });

  moduleDeployDropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    moduleDeployDropzone.classList.remove("is-dragover");
    const droppedFiles = event.dataTransfer && event.dataTransfer.files ? Array.from(event.dataTransfer.files) : [];
    const selectedFile = droppedFiles.find((file) => file && file.name);
    if (!selectedFile) {
      return;
    }
    setModuleDeployFile(selectedFile);
    appendLog("已拖入模块部署文件", selectedFile.name);
  });
}

function buildUploadToken(prefix) {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return `${prefix}-${window.crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function buildShortcutLabel(shortcut) {
  const suffix = shortcut.display_path && shortcut.display_path !== shortcut.path ? ` · ${shortcut.display_path}` : "";
  const existsText = shortcut.exists === false ? "（未找到）" : "";
  return `${shortcut.label}${suffix}${existsText}`;
}

function buildDirectoryOptions() {
  const options = [];
  const seen = new Set();

  function pushOption(path, label) {
    if (!path || seen.has(path)) {
      return;
    }
    seen.add(path);
    options.push({ path, label });
  }

  remoteShortcutsCache.filter((shortcut) => shortcut.exists !== false).forEach((shortcut) => {
    pushOption(shortcut.path, buildShortcutLabel(shortcut));
  });
  rememberedRemoteDirs.forEach((label, path) => {
    pushOption(path, label);
  });
  pushOption(DEFAULT_PROJECT_ROOT, `项目默认目录 · ${DEFAULT_PROJECT_ROOT}`);
  pushOption("/tmp", "临时目录 /tmp");
  pushOption("/", "根目录 /");
  return options;
}

function renderRemoteDirectorySelects() {
  const options = buildDirectoryOptions();
  remoteDirSelects.forEach((select) => {
    const currentValue = select.value || select.dataset.defaultValue || preferredRootCache || "/tmp";
    select.replaceChildren();
    options.forEach((option) => {
      const item = document.createElement("option");
      item.value = option.path;
      item.textContent = option.label;
      select.appendChild(item);
    });
    if (!options.some((option) => option.path === currentValue)) {
      const customOption = document.createElement("option");
      customOption.value = currentValue;
      customOption.textContent = `当前目录 · ${currentValue}`;
      select.appendChild(customOption);
    }
    select.value = currentValue;
  });
}

function rememberRemoteDirectory(path, label = path) {
  if (!path) {
    return;
  }
  rememberedRemoteDirs.set(path, label);
  renderRemoteDirectorySelects();
}

function rememberLoadedDirectoryOptions(rootPath, entries = []) {
  rememberRemoteDirectory(rootPath, `当前目录 · ${rootPath}`);
  entries
    .filter((entry) => entry && entry.is_dir)
    .forEach((entry) => {
      rememberRemoteDirectory(entry.path, `子目录 · ${entry.path}`);
    });
}

function selectRemoteDirectory(path, label = `浏览目录 · ${path}`) {
  rememberRemoteDirectory(path, label);
  remoteDirSelects.forEach((select) => {
    select.value = path;
  });
}

async function syncRemoteDirectories({ connected, shortcuts = null, preferredRoot = null, autoload = false } = {}) {
  if (!connected) {
    remoteShortcutsCache = [];
    preferredRootCache = "/tmp";
    rememberedRemoteDirs.clear();
    renderRemoteDirectorySelects();
    return;
  }

  let nextShortcuts = shortcuts;
  let nextPreferredRoot = preferredRoot;
  if (!nextShortcuts) {
    const data = await request("/api/remote-shortcuts");
    nextShortcuts = data.shortcuts || [];
    nextPreferredRoot = data.preferred_root || "/tmp";
  }

  remoteShortcutsCache = nextShortcuts;
  preferredRootCache = nextPreferredRoot || "/tmp";
  renderRemoteDirectorySelects();

  if (autoload && preferredRootCache) {
    try {
      await loadRemoteDirectoryOptions(preferredRootCache);
    } catch (error) {
      appendLog("默认部署目录加载失败", error.message);
    }
  }
}

function uploadPhaseLabel(phase) {
  const map = {
    pending: "等待开始",
    queued: "部署任务已创建，等待上传",
    preparing: "正在准备上传",
    downloading_from_server: "正在从文件服务器下载",
    backing_up: "正在备份远端文件",
    uploading_to_robot: "正在上传到机器人",
    installing: "上传完成，正在执行安装",
    completed: "上传流程已完成",
    failed: "上传失败",
  };
  return map[phase] || "处理中";
}

function syncDeployFlowForUploadView(view, progress) {
  if (view === uploadProgressViews.packageDeploy) {
    syncDeployFlow("package", { progress });
  } else if (view === uploadProgressViews.moduleDeploy) {
    syncDeployFlow("module", { progress });
  }
}

function applyServerProgress(view, progress) {
  if (!progress) {
    return false;
  }
  syncDeployFlowForUploadView(view, progress);
  const percent = progress.phase === "completed" ? 100 : Number(progress.percent || 0);
  const detailParts = [];
  if (progress.total_bytes) {
    detailParts.push(`${formatBytes(progress.transferred_bytes)} / ${formatBytes(progress.total_bytes)}`);
  }
  if (progress.file_name) {
    detailParts.push(progress.file_name);
  }
  renderUploadProgress(view, {
    percent,
    text: progress.message || uploadPhaseLabel(progress.phase),
    meta: detailParts.join(" · "),
    state: progress.phase === "failed" ? "error" : progress.done ? "success" : "active",
  });
  return Boolean(progress.done);
}

function startUploadProgressPolling(token, view) {
  let stopped = false;

  async function poll() {
    while (!stopped) {
      try {
        const data = await request(`/api/upload-progress/${encodeURIComponent(token)}`);
        if (applyServerProgress(view, data.progress)) {
          break;
        }
      } catch {
        // ignore transient polling issues
      }
      await new Promise((resolve) => window.setTimeout(resolve, 450));
    }
  }

  poll();
  return () => {
    stopped = true;
  };
}

async function finalizeUploadProgress(view, uploadToken, successText, stopPolling) {
  stopPolling();
  try {
    const progressData = await request(`/api/upload-progress/${encodeURIComponent(uploadToken)}`);
    if (applyServerProgress(view, progressData.progress)) {
      return;
    }
  } catch {
    // fall through to client-side success state
  }
  renderUploadProgress(view, {
    percent: 100,
    text: successText || "上传流程已完成",
    meta: "",
    state: "success",
  });
}

async function submitUploadWithProgress(
  url,
  formData,
  view,
  tokenPrefix,
  {
    skipBrowserUpload = false,
    reuseRemoteText = "准备直接安装远端文件",
    browserCompleteText = "浏览器上传已完成，等待后台继续处理",
    remoteReuseProgressText = "已复用远端安装包，正在进入安装流程",
  } = {},
) {
  const uploadToken = buildUploadToken(tokenPrefix);
  formData.set("upload_token", uploadToken);
  resetUploadProgress(view, skipBrowserUpload ? reuseRemoteText : "等待上传");
  syncDeployFlowForUploadView(view, {
    phase: skipBrowserUpload ? "preparing" : "queued",
    done: false,
    message: skipBrowserUpload ? reuseRemoteText : "浏览器正在上传到控制台",
  });
  const stopPolling = startUploadProgressPolling(uploadToken, view);

  try {
    const data = await xhrRequest(url, {
      method: "POST",
      body: formData,
      onUploadProgress: (loaded, total, lengthComputable) => {
        if (skipBrowserUpload) {
          return;
        }
        const percent = lengthComputable && total > 0 ? (loaded / total) * 100 : 0;
        const meta = lengthComputable && total > 0 ? `${formatBytes(loaded)} / ${formatBytes(total)}` : formatBytes(loaded);
        syncDeployFlowForUploadView(view, {
          phase: "queued",
          done: false,
          percent,
          transferred_bytes: loaded,
          total_bytes: total,
          message: loaded >= total && total > 0 ? "浏览器上传完成，等待机器人上传" : "浏览器正在上传到控制台",
        });
        renderUploadProgress(view, {
          percent,
          text: loaded >= total && total > 0 ? "浏览器上传完成，等待机器人上传" : "浏览器正在上传到控制台",
          meta,
          state: "active",
        });
      },
    });
    if (data.task) {
      renderUploadProgress(view, {
        percent: 100,
        text: skipBrowserUpload ? remoteReuseProgressText : browserCompleteText,
        meta: `${data.task.title} (${data.task.id})`,
        state: "active",
      });
    } else {
      await finalizeUploadProgress(view, uploadToken, data.message || "上传流程已完成", stopPolling);
    }
    return data;
  } catch (error) {
    stopPolling();
    renderUploadProgress(view, {
      percent: 0,
      text: "上传失败",
      meta: error.message,
      state: "error",
    });
    throw error;
  }
}

function isTaskFinished(task) {
  const status = String(task?.status || "").trim().toLowerCase();
  return status === "succeeded" || status === "warning" || status === "failed";
}

async function waitForTaskCompletion(taskId, { pollMs = 1500 } = {}) {
  const resolvedTaskId = String(taskId || "").trim();
  if (!resolvedTaskId) {
    throw new Error("任务 ID 为空，无法等待任务完成");
  }
  while (true) {
    const data = await request(`/api/tasks/${resolvedTaskId}`);
    const task = data?.task || null;
    if (!task) {
      throw new Error(`未找到任务: ${resolvedTaskId}`);
    }
    selectedTaskId = resolvedTaskId;
    renderTaskDetail(task);
    if (task.type === "deployment") {
      const deployMode = String(task?.metadata?.deploy_mode || "").trim();
      if (deployMode === "package" || deployMode === "module") {
        syncDeployFlow(deployMode, { task });
      }
    }
    if (isTaskFinished(task)) {
      await refreshDashboard();
      return task;
    }
    await refreshDashboard();
    await new Promise((resolve) => window.setTimeout(resolve, pollMs));
  }
}

function finalizeUploadProgressFromTask(view, task) {
  const status = String(task?.status || "").trim().toLowerCase();
  if (!view || !status) {
    return;
  }
  if (status === "failed") {
    renderUploadProgress(view, {
      percent: 100,
      text: "任务执行失败",
      meta: String(task?.error || "请查看后台日志"),
      state: "error",
    });
    return;
  }
  if (status === "succeeded" || status === "warning") {
    renderUploadProgress(view, {
      percent: 100,
      text: status === "warning" ? "任务执行完成（有告警）" : "任务执行完成",
      meta: String(task?.id || ""),
      state: "success",
    });
  }
}

function extractFileNameFromServerPath(rawPath) {
  const text = String(rawPath || "").trim().replaceAll("\\", "/");
  if (!text) {
    return "";
  }
  const normalized = text.split("?")[0].split("#")[0];
  const segments = normalized.split("/").filter(Boolean);
  return segments.length ? segments[segments.length - 1] : "";
}

async function resolveDeployConflict(
  formData,
  deployMode,
  progressView,
  {
    fileFieldName = "deb_file",
    serverPathFieldName = "server_file_path",
  } = {},
) {
  const selectedFile = formData.get(fileFieldName);
  const serverFilePath = String(formData.get(serverPathFieldName) || "").trim();
  const autoDeploy = String(formData.get("auto_deploy") || "").trim().toLowerCase() === "true";
  const selectedFileName =
    selectedFile instanceof File && selectedFile.name ? selectedFile.name : extractFileNameFromServerPath(serverFilePath);
  if (!selectedFileName) {
    throw new Error(`请选择${deployFileNoun(deployMode)}`);
  }

  const params = new URLSearchParams({
    file_name: selectedFileName,
    machine_type: String(formData.get("machine_type") || "").trim(),
  });
  if (deployMode === "package") {
    params.set("device_type", String(formData.get("device_type") || "ORIN").trim() || "ORIN");
  }
  const target = await request(`/api/deploy-target?${params.toString()}`);
  formData.set("file_name", target.file_name || selectedFileName);

  if (!target.exists) {
    return { cancelled: false, skipBrowserUpload: Boolean(serverFilePath) };
  }

  if (autoDeploy) {
    formData.set("use_existing_remote", "true");
    formData.delete("replace_existing");
    formData.delete(fileFieldName);
    renderUploadProgress(progressView, {
      percent: 100,
      text: `检测到远端同名文件，自动跳过上传并继续${deployActionLabel(deployMode)}`,
      meta: target.remote_path,
      state: "active",
    });
    appendLog("自动部署检测到远端同名文件，已跳过替换", target.remote_path);
    return { cancelled: false, skipBrowserUpload: true };
  }

  const replaceExisting = window.confirm(
    `远端已存在同名文件：\n${target.remote_path}\n\n是否替换该文件并继续执行后续部署？`,
  );
  if (replaceExisting) {
    formData.set("replace_existing", "true");
    appendLog("检测到远端同名文件，用户选择替换", target.remote_path);
    return { cancelled: false, skipBrowserUpload: Boolean(serverFilePath) };
  }

  const installExisting = window.confirm(
    `已保留远端现有文件：\n${target.remote_path}\n\n是否直接使用这个远端文件继续执行${deployActionLabel(deployMode)}？`,
  );
  if (!installExisting) {
    renderUploadProgress(progressView, {
      percent: 0,
      text: "已取消部署",
      meta: `保留远端文件：${target.remote_path}`,
      state: "active",
    });
    appendLog("部署已取消", `远端同名文件未替换，且未继续${deployActionLabel(deployMode)}：${target.remote_path}`);
    return { cancelled: true, skipBrowserUpload: true };
  }

  formData.set("use_existing_remote", "true");
  formData.delete(fileFieldName);
  renderUploadProgress(progressView, {
    percent: 100,
    text: `已跳过上传，准备直接${deployActionLabel(deployMode)}远端同名文件`,
    meta: target.remote_path,
    state: "active",
  });
  appendLog(`检测到远端同名文件，用户选择直接${deployActionLabel(deployMode)}`, target.remote_path);
  return { cancelled: false, skipBrowserUpload: true };
}

async function resolveDeployConflictFromError(
  formData,
  progressView,
  error,
  {
    fileFieldName = "deb_file",
    serverPathFieldName = "server_file_path",
    deployMode = "package",
  } = {},
) {
  const conflict = error && error.conflict;
  const autoDeploy = String(formData.get("auto_deploy") || "").trim().toLowerCase() === "true";
  if (!conflict || !conflict.remote_path) {
    return { handled: false };
  }

  if (autoDeploy) {
    formData.set("use_existing_remote", "true");
    formData.delete("replace_existing");
    formData.delete(fileFieldName);
    renderUploadProgress(progressView, {
      percent: 100,
      text: `检测到远端同名文件，自动跳过上传并继续${deployActionLabel(deployMode)}`,
      meta: conflict.remote_path,
      state: "active",
    });
    appendLog("自动部署检测到远端同名文件，已跳过替换", conflict.remote_path);
    return { handled: true, cancelled: false, skipBrowserUpload: true };
  }

  const replaceExisting = window.confirm(
    `远端已存在同名文件：\n${conflict.remote_path}\n\n是否替换该文件并继续执行后续部署？`,
  );
  if (replaceExisting) {
    formData.set("replace_existing", "true");
    formData.delete("use_existing_remote");
    appendLog("后端检测到远端同名文件，用户选择替换", conflict.remote_path);
    return { handled: true, cancelled: false, skipBrowserUpload: Boolean(formData.get(serverPathFieldName)) };
  }

  const installExisting = window.confirm(
    `已保留远端现有文件：\n${conflict.remote_path}\n\n是否直接使用这个远端文件继续执行${deployActionLabel(deployMode)}？`,
  );
  if (!installExisting) {
    renderUploadProgress(progressView, {
      percent: 0,
      text: "已取消部署",
      meta: `保留远端文件：${conflict.remote_path}`,
      state: "active",
    });
    appendLog("部署已取消", `远端同名文件未替换，且未继续${deployActionLabel(deployMode)}：${conflict.remote_path}`);
    return { handled: true, cancelled: true, skipBrowserUpload: true };
  }

  formData.set("use_existing_remote", "true");
  formData.delete("replace_existing");
  formData.delete(fileFieldName);
  renderUploadProgress(progressView, {
    percent: 100,
    text: `已跳过上传，准备直接${deployActionLabel(deployMode)}远端同名文件`,
    meta: conflict.remote_path,
    state: "active",
  });
  appendLog(`后端检测到远端同名文件，用户选择直接${deployActionLabel(deployMode)}`, conflict.remote_path);
  return { handled: true, cancelled: false, skipBrowserUpload: true };
}

function createActionButton(text, className, handler) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = text;
  button.addEventListener("click", handler);
  return button;
}

function createStatusPill(status) {
  const pill = document.createElement("span");
  const labelMap = {
    pending: "等待中",
    running: "执行中",
    warning: "成功（有告警）",
    succeeded: "成功",
    failed: "失败",
  };
  pill.className = `status-pill status-${status}`;
  pill.textContent = labelMap[status] || status;
  return pill;
}

function createEmptyState(text) {
  const empty = document.createElement("div");
  empty.className = "record-empty";
  empty.textContent = text;
  return empty;
}

function resolveRemoteDirectoryTarget(selectedPath) {
  if (selectedPath && selectedPath !== "/tmp" && selectedPath !== "/") {
    return selectedPath;
  }
  return (
    remoteShortcutsCache.find((shortcut) => shortcut.path === DEFAULT_PROJECT_ROOT && shortcut.exists !== false)?.path ||
    (preferredRootCache && preferredRootCache !== "/" ? preferredRootCache : DEFAULT_PROJECT_ROOT)
  );
}

async function loadRemoteDirectoryOptions(path) {
  appendLog("加载部署目录", path);
  const data = await request(`/api/list-dir?path=${encodeURIComponent(path)}`);
  const resolvedPath = data.resolved_path || path;
  rememberLoadedDirectoryOptions(resolvedPath, data.entries || []);
  selectRemoteDirectory(resolvedPath, `当前目录 · ${resolvedPath}`);
  const childDirectoryCount = (data.entries || []).filter((entry) => entry && entry.is_dir).length;
  appendLog("部署目录下拉已更新", `${resolvedPath}（已加入 ${childDirectoryCount} 个一级子目录）`);
  return data;
}

async function loadRemoteDirectoryFromSelect(selectId) {
  const select = document.getElementById(selectId);
  if (!select) {
    return;
  }
  const selectedPath = select.value.trim();
  if (!selectedPath) {
    throw new Error("请先选择远程目录");
  }
  const targetPath = resolveRemoteDirectoryTarget(selectedPath);
  const data = await loadRemoteDirectoryOptions(targetPath);
  const resolvedTargetPath = data.resolved_path || targetPath;
  selectRemoteDirectory(resolvedTargetPath, `当前目录 · ${resolvedTargetPath}`);
  appendLog("已加载部署目录", resolvedTargetPath);
}

function renderTasks(tasks) {
  taskList.replaceChildren();
  if (!tasks.length) {
    taskList.appendChild(createEmptyState("还没有后台任务。创建部署任务后会显示在这里。"));
    taskDetailOutput.textContent = "暂无任务详情。";
    selectedTaskId = "";
    return;
  }

  if (selectedTaskId && !tasks.some((task) => task.id === selectedTaskId)) {
    selectedTaskId = "";
  }
  if (!selectedTaskId) {
    const runningTask = tasks.find((task) => task.status === "running");
    selectedTaskId = (runningTask || tasks[0]).id;
  }

  tasks.forEach((task) => {
    const item = document.createElement("div");
    item.className = `record-item ${task.id === selectedTaskId ? "selected" : ""}`;

    const header = document.createElement("div");
    header.className = "record-header";

    const title = document.createElement("strong");
    title.textContent = task.title;

    header.append(title, createStatusPill(task.status));

    const meta = document.createElement("div");
    meta.className = "record-meta";
    meta.textContent = `${task.type} · 创建于 ${task.created_at}${task.finished_at ? ` · 完成于 ${task.finished_at}` : ""}`;

    const actions = document.createElement("div");
    actions.className = "record-actions";
    actions.appendChild(
      createActionButton(task.id === selectedTaskId ? "已选中" : "查看详情", task.id === selectedTaskId ? "secondary" : "ghost", async () => {
        selectedTaskId = task.id;
        await refreshTaskDetail();
        renderTasks(tasks);
      }),
    );

    item.append(header, meta, actions);
    taskList.appendChild(item);
  });
}

function formatObject(value) {
  if (!value || (typeof value === "object" && !Object.keys(value).length)) {
    return "无";
  }
  return JSON.stringify(value, null, 2);
}

function taskStatusLabel(status) {
  const labelMap = {
    pending: "等待中",
    running: "执行中",
    warning: "成功（有告警）",
    succeeded: "成功",
    failed: "失败",
  };
  return labelMap[status] || status;
}

function setTaskDetailCopyState({ enabled, text = "复制日志" } = {}) {
  if (!copyTaskDetailBtn) {
    return;
  }
  copyTaskDetailBtn.disabled = !enabled;
  copyTaskDetailBtn.textContent = text;
}

function buildTaskDetailText(task) {
  if (!task) {
    return "暂无任务详情。";
  }
  const lines = [
    `任务: ${task.title}`,
    `ID: ${task.id}`,
    `状态: ${taskStatusLabel(task.status)}`,
    `创建时间: ${task.created_at || "-"}`,
    `开始时间: ${task.started_at || "-"}`,
    `完成时间: ${task.finished_at || "-"}`,
    "",
    "结果:",
    formatObject(task.result),
  ];

  if (task.error) {
    lines.push("", `错误: ${task.error}`);
  }

  lines.push("", "后台日志:");
  if (task.logs.length) {
    lines.push(...task.logs);
  } else {
    lines.push("暂无日志");
  }
  return lines.join("\n");
}

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "readonly");
  textarea.style.position = "fixed";
  textarea.style.top = "-9999px";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  const successful = document.execCommand("copy");
  document.body.removeChild(textarea);
  if (!successful) {
    throw new Error("复制失败，请手动选择日志内容复制");
  }
}

async function copyRosExample(button, outputNode, successMessage) {
  const text = String(outputNode?.textContent || "").trim();
  if (!text) {
    throw new Error("当前没有可复制的示例内容");
  }
  const originalText = button?.textContent || "复制示例";
  await copyText(text);
  if (button) {
    button.textContent = "已复制";
    window.setTimeout(() => {
      button.textContent = originalText;
    }, 1600);
  }
  appendLog(successMessage);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderTaskDetailLine(line) {
  const text = String(line ?? "");
  let className = "task-log-line";
  if (text.startsWith("[stdout] ")) {
    className += " is-stdout";
  } else if (text.startsWith("[stderr] ")) {
    className += " is-stderr";
  } else if (text.startsWith("错误:")) {
    className += " is-error";
  } else if (text.endsWith("标准输出:") || text.endsWith("错误输出:")) {
    className += " is-stream-title";
  } else if (text.startsWith("后台日志:") || text.startsWith("结果:")) {
    className += " is-section";
  } else if (/^(任务|ID|状态|创建时间|开始时间|完成时间):/.test(text)) {
    className += " is-meta";
  }
  return `<div class="${className}">${escapeHtml(text)}</div>`;
}

function renderTaskDetail(task) {
  if (!task) {
    currentTaskDetailText = "";
    setTaskDetailCopyState({ enabled: false });
    taskDetailOutput.textContent = "暂无任务详情。";
    return;
  }
  const text = buildTaskDetailText(task);
  const lines = text.split("\n");
  currentTaskDetailText = text;
  setTaskDetailCopyState({ enabled: true });
  taskDetailOutput.innerHTML = lines.map(renderTaskDetailLine).join("");
}

async function refreshTaskDetail() {
  if (!selectedTaskId) {
    currentTaskDetailText = "";
    setTaskDetailCopyState({ enabled: false });
    taskDetailOutput.textContent = "暂无任务详情。";
    return;
  }
  const data = await request(`/api/tasks/${selectedTaskId}`);
  renderTaskDetail(data.task);
}

async function refreshDashboard() {
  try {
    const taskData = await request("/api/tasks");
    renderTasks(taskData.tasks);
    syncDeployFlow("package", { tasks: taskData.tasks });
    syncDeployFlow("module", { tasks: taskData.tasks });
    await refreshTaskDetail();
    dashboardErrorShown = false;
  } catch (error) {
    if (!dashboardErrorShown) {
      appendLog("刷新后台状态失败", error.message);
      dashboardErrorShown = true;
    }
  }
}

function startDashboardPolling() {
  if (dashboardTimer) {
    window.clearInterval(dashboardTimer);
  }
  dashboardTimer = window.setInterval(() => {
    refreshDashboard();
  }, 4000);
}

function startSessionHeartbeat() {
  if (heartbeatTimer) {
    window.clearInterval(heartbeatTimer);
  }
  heartbeatTimer = window.setInterval(() => {
    request("/api/ping").catch(() => {
      // ignore heartbeat failures and let user-facing requests surface issues
    });
  }, 60000);
}

if (copyTaskDetailBtn) {
  copyTaskDetailBtn.addEventListener("click", async () => {
    if (!currentTaskDetailText) {
      return;
    }
    try {
      await copyText(currentTaskDetailText);
      setTaskDetailCopyState({ enabled: true, text: "已复制" });
      appendLog("已复制后台任务日志");
      window.setTimeout(() => {
        setTaskDetailCopyState({ enabled: true, text: "复制日志" });
      }, 1600);
    } catch (error) {
      appendLog("复制后台任务日志失败", error.message);
      alert(error.message);
    }
  });
}

passwordToggleButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const field = button.closest(".password-field");
    const input = field ? field.querySelector('input[type="password"], input[type="text"]') : null;
    if (!input) {
      return;
    }
    const isHidden = input.type === "password";
    input.type = isHidden ? "text" : "password";
    button.classList.toggle("is-visible", isHidden);
    button.setAttribute("aria-label", isHidden ? "隐藏密码" : "显示密码");
    button.setAttribute("title", isHidden ? "隐藏密码" : "显示密码");
  });
});

pageNavButtons.forEach((button) => {
  button.addEventListener("click", () => {
    switchPage(button.dataset.pageTarget || "remote");
  });
});

if (refreshRosTopicsBtn) {
  refreshRosTopicsBtn.addEventListener("click", async () => {
    try {
      await loadRosNames("topic");
    } catch (error) {
      setRosOutput(rosTopicDetailOutput, `刷新 Topic 列表失败：${error.message}`);
      appendLog("刷新 Topic 列表失败", error.message);
    }
  });
}

if (refreshRosServicesBtn) {
  refreshRosServicesBtn.addEventListener("click", async () => {
    try {
      await loadRosNames("service");
    } catch (error) {
      setRosOutput(rosServiceDetailOutput, `刷新 Service 列表失败：${error.message}`);
      appendLog("刷新 Service 列表失败", error.message);
    }
  });
}

if (rosPublishTabBtn) {
  rosPublishTabBtn.addEventListener("click", () => switchRosTab("publish"));
}

if (rosSubscribeTabBtn) {
  rosSubscribeTabBtn.addEventListener("click", () => switchRosTab("subscribe"));
}

if (rosTopicSearchInput) {
  rosTopicSearchInput.addEventListener("input", () => renderRosNameList("topic"));
}

if (rosServiceSearchInput) {
  rosServiceSearchInput.addEventListener("input", () => renderRosNameList("service"));
}

if (rosTopicInfoBtn) {
  rosTopicInfoBtn.addEventListener("click", async () => {
    try {
      await runRosTopicAction("info");
    } catch (error) {
      setRosOutput(rosTopicDetailOutput, error.message);
      appendLog("rostopic info 失败", error.message);
    }
  });
}

if (rosTopicTypeBtn) {
  rosTopicTypeBtn.addEventListener("click", async () => {
    try {
      await runRosTopicAction("type");
    } catch (error) {
      setRosOutput(rosTopicDetailOutput, error.message);
      appendLog("rostopic type 失败", error.message);
    }
  });
}

if (rosTopicEchoBtn) {
  rosTopicEchoBtn.addEventListener("click", async () => {
    try {
      await runRosTopicAction("echo");
    } catch (error) {
      setRosOutput(rosTopicDetailOutput, error.message);
      appendLog("rostopic echo 失败", error.message);
    }
  });
}

if (rosTopicPubBtn) {
  rosTopicPubBtn.addEventListener("click", async () => {
    try {
      await runRosTopicAction("pub");
    } catch (error) {
      setRosOutput(rosTopicPublishOutput, error.message);
      appendLog("rostopic pub 失败", error.message);
    }
  });
}

if (rosTopicPubPythonBtn) {
  rosTopicPubPythonBtn.addEventListener("click", () => {
    try {
      setRosOutput(rosTopicPublishOutput, buildRosTopicPythonExample("publish"));
    } catch (error) {
      setRosOutput(rosTopicPublishOutput, error.message);
      appendLog("生成 Topic Python 发布示例失败", error.message);
    }
  });
}

if (rosTopicPubPythonCopyBtn) {
  rosTopicPubPythonCopyBtn.addEventListener("click", async () => {
    try {
      await copyRosExample(rosTopicPubPythonCopyBtn, rosTopicPublishOutput, "已复制 Topic Python 发布示例");
    } catch (error) {
      appendLog("复制 Topic Python 发布示例失败", error.message);
      alert(error.message);
    }
  });
}

if (rosServiceInfoBtn) {
  rosServiceInfoBtn.addEventListener("click", async () => {
    try {
      await runRosServiceAction("info");
    } catch (error) {
      setRosOutput(rosServiceDetailOutput, error.message);
      appendLog("rosservice info 失败", error.message);
    }
  });
}

if (rosServiceTypeBtn) {
  rosServiceTypeBtn.addEventListener("click", async () => {
    try {
      await runRosServiceAction("type");
    } catch (error) {
      setRosOutput(rosServiceDetailOutput, error.message);
      appendLog("rosservice type 失败", error.message);
    }
  });
}

if (rosTopicSubPythonBtn) {
  rosTopicSubPythonBtn.addEventListener("click", () => {
    try {
      setRosOutput(rosTopicDetailOutput, buildRosTopicPythonExample("subscribe"));
    } catch (error) {
      setRosOutput(rosTopicDetailOutput, error.message);
      appendLog("生成 Topic Python 订阅示例失败", error.message);
    }
  });
}

if (rosTopicSubPythonCopyBtn) {
  rosTopicSubPythonCopyBtn.addEventListener("click", async () => {
    try {
      await copyRosExample(rosTopicSubPythonCopyBtn, rosTopicDetailOutput, "已复制 Topic Python 订阅示例");
    } catch (error) {
      appendLog("复制 Topic Python 订阅示例失败", error.message);
      alert(error.message);
    }
  });
}

if (rosServiceCallBtn) {
  rosServiceCallBtn.addEventListener("click", async () => {
    try {
      await runRosServiceAction("call");
    } catch (error) {
      setRosOutput(rosServiceDetailOutput, error.message);
      appendLog("rosservice call 失败", error.message);
    }
  });
}

if (rosServicePythonBtn) {
  rosServicePythonBtn.addEventListener("click", () => {
    try {
      setRosOutput(rosServiceDetailOutput, buildRosServicePythonExample());
    } catch (error) {
      setRosOutput(rosServiceDetailOutput, error.message);
      appendLog("生成 Service Python 调用示例失败", error.message);
    }
  });
}

if (rosServicePythonCopyBtn) {
  rosServicePythonCopyBtn.addEventListener("click", async () => {
    try {
      await copyRosExample(rosServicePythonCopyBtn, rosServiceDetailOutput, "已复制 Service Python 调用示例");
    } catch (error) {
      appendLog("复制 Service Python 调用示例失败", error.message);
      alert(error.message);
    }
  });
}

guideNavButtons.forEach((button) => {
  button.addEventListener("click", () => {
    switchGuidePage(button.dataset.guideTarget || "flow");
  });
});

configNavButtons.forEach((button) => {
  button.addEventListener("click", () => {
    switchConfigPage(button.dataset.configTarget || "voice");
  });
});

if (refreshAudioConfigBtn) {
  refreshAudioConfigBtn.addEventListener("click", async () => {
    try {
      audioMonitorState.hasLoaded = false;
      await loadAudioMonitorConfig();
    } catch (error) {
      setAudioConfigStatus(`刷新语音监控配置失败：${error.message}`, true);
      appendLog("刷新语音监控配置失败", error.message);
    }
  });
}

if (enableAllAudioConfigBtn) {
  enableAllAudioConfigBtn.addEventListener("click", () => {
    setAllAudioMonitorEntries(true);
  });
}

if (disableAllAudioConfigBtn) {
  disableAllAudioConfigBtn.addEventListener("click", () => {
    setAllAudioMonitorEntries(false);
  });
}

if (saveAudioConfigBtn) {
  saveAudioConfigBtn.addEventListener("click", async () => {
    try {
      await saveAudioMonitorConfig();
    } catch (error) {
      setAudioConfigStatus(`保存语音监控配置失败：${error.message}`, true);
      appendLog("保存语音监控配置失败", error.message);
      alert(error.message);
    }
  });
}

rosNavButtons.forEach((button) => {
  button.addEventListener("click", () => {
    switchRosSection(button.dataset.rosTarget || "topic");
  });
});

if (downloadOrinLogBtn) {
  downloadOrinLogBtn.addEventListener("click", async () => {
    try {
      await downloadLogArchive({
        deviceType: "ORIN",
        moduleSelectNode: orinLogModuleSelect,
        statusNode: orinLogStatus,
        startPrefix: "orin-start",
        endPrefix: "orin-end",
      });
    } catch (error) {
      if (error?.name === "AbortError") {
        setLogStatus(orinLogStatus, "已取消保存日志压缩包");
        return;
      }
      setLogStatus(orinLogStatus, error.message, true);
      appendLog("导出 ORIN 日志失败", error.message);
    }
  });
}

if (downloadPicoLogBtn) {
  downloadPicoLogBtn.addEventListener("click", async () => {
    try {
      await downloadLogArchive({
        deviceType: "PICO",
        moduleSelectNode: picoLogModuleSelect,
        statusNode: picoLogStatus,
        startPrefix: "pico-start",
        endPrefix: "pico-end",
        requireModuleSelection: false,
      });
    } catch (error) {
      if (error?.name === "AbortError") {
        setLogStatus(picoLogStatus, "已取消保存日志压缩包");
        return;
      }
      setLogStatus(picoLogStatus, error.message, true);
      appendLog("导出 PICO 日志失败", error.message);
    }
  });
}

connectForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const payload = Object.fromEntries(formData.entries());
  try {
    const data = await request("/api/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const selectedConnection = normalizeConnectionCacheItem(payload);
    setSavedConnections(data.saved_connections || [], { selectedId: selectedConnection ? selectedConnection.id : "" });
    updateConnectionStatus(true);
    rosState.hasLoadedTopics = false;
    rosState.hasLoadedServices = false;
    setRosPageHint("提示：点击右上角按钮可刷新列表");
    appendLog(
      "SSH 连接成功",
      `ORIN ${payload.username}@${payload.host}:${payload.port}${payload.pico_host ? `\nPICO ${payload.pico_username || "-"}@${payload.pico_host}:${payload.pico_port || DEFAULT_CONNECTION_FORM.pico_port}` : ""}`,
    );
    await syncRemoteDirectories({
      connected: true,
      shortcuts: data.remote_shortcuts,
      preferredRoot: data.preferred_root,
      autoload: true,
    });
  } catch (error) {
    appendLog("SSH 连接失败", error.message);
    alert(error.message);
  }
});

savedConnectionSelect.addEventListener("change", () => {
  const selectedConnection = savedConnectionsCache.find((connection) => connection.id === savedConnectionSelect.value);
  renderSavedConnectionSummary();
  if (!selectedConnection) {
    return;
  }
  applyConnectionToForm(selectedConnection);
  appendLog("已填充缓存连接", buildSavedConnectionLabel(selectedConnection));
});

clearConnectionCacheBtn.addEventListener("click", async () => {
  try {
    const data = await request("/api/connection-cache/clear", { method: "POST" });
    setSavedConnections(data.saved_connections || []);
    appendLog("已清空连接缓存");
  } catch (error) {
    appendLog("清空连接缓存失败", error.message);
    alert(error.message);
  }
});

if (remoteCacheSelectShell && savedConnectionSelect) {
  const openSavedConnectionSelect = () => {
    savedConnectionSelect.focus();
    if (typeof savedConnectionSelect.showPicker === "function") {
      savedConnectionSelect.showPicker();
    } else {
      savedConnectionSelect.click();
    }
  };
  remoteCacheSelectShell.addEventListener("click", openSavedConnectionSelect);
  remoteCacheSelectShell.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openSavedConnectionSelect();
    }
  });
}

document.getElementById("disconnectBtn").addEventListener("click", async () => {
  try {
    await request("/api/disconnect", { method: "POST" });
    updateConnectionStatus(false);
    rosState.topics = [];
    rosState.services = [];
    rosState.selectedTopic = "";
    rosState.selectedService = "";
    rosState.selectedTopicType = "";
    rosState.selectedTopicDirection = "";
    rosState.topicAvailable = false;
    rosState.lastPublishRecord = null;
    rosState.hasLoadedTopics = false;
    rosState.hasLoadedServices = false;
    renderRosNameList("topic");
    renderRosNameList("service");
    updateRosTopicSummary();
    updateRosPublishHistory();
    if (rosSelectedServiceName) {
      rosSelectedServiceName.textContent = "未选择 Service";
    }
    setRosPageHint("提示：请先连接机器人或确保 rosbridge 容器已启动");
    setRosOutput(rosTopicDetailOutput, "连接已断开，请重新连接机器人后再加载 Topic 列表。");
    setRosOutput(rosServiceDetailOutput, "连接已断开，请重新连接机器人后再加载 Service 列表。");
    await syncRemoteDirectories({ connected: false });
    appendLog("连接已断开");
  } catch (error) {
    appendLog("断开连接失败", error.message);
    alert(error.message);
  }
});

async function submitDeployForm(event, { deployMode, progressView, tokenPrefix }) {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  if (deployMode === "package") {
    const deviceType = String(formData.get("device_type") || "ORIN").trim().toUpperCase() || "ORIN";
    formData.set("device_type", deviceType);
  }
  const conflictResolution = await resolveDeployConflict(formData, deployMode, progressView);
  if (conflictResolution.cancelled) {
    return;
  }
  currentDeployTaskIds.package = "";
  syncDeployFlow("package", {
    task: {
      id: "",
      type: "deployment",
      status: conflictResolution.skipBrowserUpload ? "pending" : "running",
      metadata: {
        deploy_mode: "package",
        used_existing_remote: conflictResolution.skipBrowserUpload,
      },
      result: {},
      error: "",
    },
    progress: conflictResolution.skipBrowserUpload ? { phase: "completed", done: true } : { phase: "preparing", done: false },
  });
  let data;
  try {
    data = await submitUploadWithProgress("/api/deploy", formData, progressView, tokenPrefix, {
      skipBrowserUpload: conflictResolution.skipBrowserUpload,
    });
  } catch (error) {
    const retryResolution = await resolveDeployConflictFromError(formData, progressView, error);
    if (!retryResolution.handled) {
      throw error;
    }
    if (retryResolution.cancelled) {
      return;
    }
    data = await submitUploadWithProgress("/api/deploy", formData, progressView, tokenPrefix, {
      skipBrowserUpload: retryResolution.skipBrowserUpload,
    });
  }
  selectedTaskId = data.task.id;
  currentDeployTaskIds.package = data.task.id;
  syncDeployFlow("package", { task: data.task });
  appendLog("部署任务已创建", `${data.task.title} (${data.task.id})`);
  await refreshDashboard();
}

async function createPackageDeployTask(formData, { progressView, tokenPrefix = "package-deploy" } = {}) {
  const useExistingRemote = String(formData.get("use_existing_remote") || "").trim().toLowerCase() === "true";
  let skipBrowserUpload = useExistingRemote;
  if (!useExistingRemote) {
    const conflictResolution = await resolveDeployConflict(formData, "package", progressView);
    if (conflictResolution.cancelled) {
      return null;
    }
    skipBrowserUpload = conflictResolution.skipBrowserUpload;
  }
  currentDeployTaskIds.package = "";
  syncDeployFlow("package", {
    task: {
      id: "",
      type: "deployment",
      status: skipBrowserUpload ? "pending" : "running",
      metadata: {
        deploy_mode: "package",
        used_existing_remote: skipBrowserUpload,
      },
      result: {},
      error: "",
    },
    progress: skipBrowserUpload ? { phase: "completed", done: true } : { phase: "preparing", done: false },
  });
  let data;
  try {
    data = await submitUploadWithProgress("/api/deploy", formData, progressView, tokenPrefix, {
      skipBrowserUpload,
    });
  } catch (error) {
    const retryResolution = await resolveDeployConflictFromError(formData, progressView, error, { deployMode: "package" });
    if (!retryResolution.handled) {
      throw error;
    }
    if (retryResolution.cancelled) {
      return null;
    }
    data = await submitUploadWithProgress("/api/deploy", formData, progressView, tokenPrefix, {
      skipBrowserUpload: retryResolution.skipBrowserUpload,
    });
  }
  selectedTaskId = data.task.id;
  currentDeployTaskIds.package = data.task.id;
  syncDeployFlow("package", { task: data.task });
  appendLog("整包部署任务已创建", `${data.task.title} (${data.task.id})`);
  await refreshDashboard();
  return data.task;
}

async function createModuleDeployTask(formData) {
  currentDeployTaskIds.module = "";
  syncDeployFlow("module", {
    task: {
      id: "",
      type: "deployment",
      status: "running",
      metadata: {
        deploy_mode: "module",
      },
      result: {},
      error: "",
    },
    progress: { phase: "preparing", done: false },
  });

  const data = await submitUploadWithProgress("/api/deploy-module", formData, uploadProgressViews.moduleDeploy, "module-deploy", {
    skipBrowserUpload: Boolean(formData.get("server_file_path")),
  });
  selectedTaskId = data.task.id;
  currentDeployTaskIds.module = data.task.id;
  syncDeployFlow("module", { task: data.task });
  appendLog("模块部署任务已创建", `${data.task.title} (${data.task.id})`);
  await refreshDashboard();
  return data.task;
}

async function submitPackageUploadProbe(event) {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const deviceType = String(formData.get("device_type") || "ORIN").trim().toUpperCase() || "ORIN";
  const autoDeployConfig = getSelectedPackageAutoDeployConfig();
  const autoDeployUrls = autoDeployConfig?.urls || [];
  if (autoDeployUrls.length) {
    formData.set("auto_deploy", "true");
    formData.set("server_file_path", autoDeployUrls[0]);
    formData.delete("deb_file");
  } else {
    formData.delete("auto_deploy");
  }
  formData.set("device_type", deviceType);
  const conflictResolution = await resolveDeployConflict(formData, "package", uploadProgressViews.packageDeploy);
  if (conflictResolution.cancelled) {
    return;
  }
  let data;
  try {
    data = await submitUploadWithProgress("/api/package-upload-probe", formData, uploadProgressViews.packageDeploy, "package-probe", {
      skipBrowserUpload: conflictResolution.skipBrowserUpload,
    });
  } catch (error) {
    const retryResolution = await resolveDeployConflictFromError(formData, uploadProgressViews.packageDeploy, error);
    if (!retryResolution.handled) {
      throw error;
    }
    if (retryResolution.cancelled) {
      return;
    }
    data = await submitUploadWithProgress("/api/package-upload-probe", formData, uploadProgressViews.packageDeploy, "package-probe", {
      skipBrowserUpload: retryResolution.skipBrowserUpload,
    });
  }
  const machineOptions = Array.isArray(data.machine_options) && data.machine_options.length
    ? data.machine_options
    : DEFAULT_PACKAGE_MACHINE_OPTIONS;
  const selectedMachineType = String(data.selected_machine_type || "").trim();
  activatePackageDeployContinueStage({
    fileName: data.file_name || String(formData.get("file_name") || "").trim(),
    remotePath: data.remote_path || "",
    remoteDir: data.remote_dir || "",
    deviceType,
    machineOptions,
    selectedMachineType,
  });
  pendingPackageAutoDeployUrls = autoDeployUrls.length ? [...autoDeployUrls] : [];
  appendLog(
    "整包上传完成，已识别可选机型",
    `${data.remote_path || ""}\n机型: ${machineOptions.map((item) => item.label || item.value).join(", ")}`,
  );
  if (selectedMachineType) {
    appendLog("已复用远端 ROBOT_TYPE", selectedMachineType);
  }
  if (autoDeployUrls.length > 1) {
    if (selectedMachineType) {
      setPackageDeployHint(`已复用 ROBOT_TYPE=${selectedMachineType}，点击“继续部署”后系统会按顺序执行当前版本下的 ${autoDeployUrls.length} 个包。`);
    } else {
      setPackageDeployHint(`未读取到 ROBOT_TYPE，请先选择机型后点击“继续部署”，系统会按顺序执行当前版本下的 ${autoDeployUrls.length} 个包。`);
    }
  }
  if (data.probe_warning) {
    appendLog("机型识别提示", data.probe_warning);
    setPackageDeployHint(`${data.probe_warning}，请确认机型后点击“继续部署”，将直接复用远端安装包进入安装流程。`);
  }
}

async function submitPackageContinueDeployForm(formNode) {
  const formData = new FormData(formNode);
  const deviceType = String(formData.get("device_type") || packageDeployStageState.deviceType || "ORIN").trim().toUpperCase() || "ORIN";
  const machineType = String(formData.get("machine_type") || "").trim();
  if (!machineType) {
    throw new Error("请选择机型");
  }
  if (!packageDeployStageState.fileName) {
    throw new Error("当前没有可继续部署的安装包，请重新上传 firmware");
  }
  const autoDeployUrls = Array.isArray(pendingPackageAutoDeployUrls) ? pendingPackageAutoDeployUrls.filter(Boolean) : [];
  formData.set("device_type", deviceType);
  formData.set("machine_type", machineType);
  formData.set("file_name", packageDeployStageState.fileName);
  formData.set("use_existing_remote", "true");
  if (autoDeployUrls.length) {
    formData.set("auto_deploy", "true");
  } else {
    formData.delete("auto_deploy");
  }
  formData.delete("deb_file");
  formData.set("server_file_path", autoDeployUrls[0] || String(formData.get("server_file_path") || "").trim());

  if (autoDeployUrls.length > 1) {
    appendLog("开始自动顺序整包部署", `版本 ${packageAutoDeploySelect?.value || ""} 共 ${autoDeployUrls.length} 个包`);
  }

  const firstTask = await createPackageDeployTask(formData, {
    progressView: uploadProgressViews.packageDeploy,
    tokenPrefix: "package-deploy",
  });
  if (!firstTask) {
    return;
  }
  const firstResult = await waitForTaskCompletion(firstTask.id);
  finalizeUploadProgressFromTask(uploadProgressViews.packageDeploy, firstResult);
  if (String(firstResult.status || "").trim().toLowerCase() === "failed") {
    throw new Error(firstResult.error || "首个整包部署任务执行失败");
  }

  for (let index = 1; index < autoDeployUrls.length; index += 1) {
    const serverFilePath = autoDeployUrls[index];
    const nextFormData = new FormData(formNode);
    nextFormData.set("device_type", deviceType);
    nextFormData.set("machine_type", machineType);
    nextFormData.set("server_file_path", serverFilePath);
    nextFormData.delete("deb_file");
    appendLog("继续自动顺序整包部署", `${index + 1}/${autoDeployUrls.length} ${serverFilePath}`);
    const nextTask = await createPackageDeployTask(nextFormData, {
      progressView: uploadProgressViews.packageDeploy,
      tokenPrefix: "package-deploy",
    });
    if (!nextTask) {
      return;
    }
    const nextResult = await waitForTaskCompletion(nextTask.id);
    finalizeUploadProgressFromTask(uploadProgressViews.packageDeploy, nextResult);
    if (String(nextResult.status || "").trim().toLowerCase() === "failed") {
      throw new Error(nextResult.error || `第 ${index + 1} 个整包部署任务执行失败`);
    }
  }

  resetPackageDeployStage({ keepHint: true, keepMachineOptions: true, selectedMachineType: machineType });
  setPackageDeployHint(autoDeployUrls.length > 1 ? "当前版本下的整包已按顺序执行完成。" : "已创建整包部署任务。如需部署其他 firmware，请重新选择文件。");
  await refreshDashboard();
}

async function submitPackageContinueDeploy(event) {
  event.preventDefault();
  await submitPackageContinueDeployForm(event.currentTarget);
}

packageDeployForm.addEventListener("submit", async (event) => {
  try {
    if (packageDeployStageState.stage === "continue") {
      await submitPackageContinueDeploy(event);
      return;
    }
    await submitPackageUploadProbe(event);
  } catch (error) {
    appendLog(packageDeployStageState.stage === "continue" ? "继续整包部署失败" : "上传并识别机型失败", error.message);
    setPackageDeployHint(error.message, true);
    alert(error.message);
  }
});

async function submitModuleDeployForm(event) {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const moduleName = String(formData.get("module_name") || "").trim();
  if (!moduleName) {
    throw new Error("请选择要部署的模块");
  }
  const { versionConfig: autoVersionConfig, moduleConfig: autoModuleConfig } = getSelectedModuleAutoDeployConfig();
  const autoDeployUrls = autoModuleConfig?.urls || [];
  if (autoDeployUrls.length) {
    formData.set("auto_deploy", "true");
    formData.set("server_file_paths_json", JSON.stringify(autoDeployUrls));
    formData.delete("server_file_path");
    formData.delete("deb_file");
    appendLog("开始批量模块部署", `${autoVersionConfig?.version || ""} / ${moduleName} 共 ${autoDeployUrls.length} 个包，将先全部替换再统一执行部署`);
    const task = await createModuleDeployTask(formData);
    const result = await waitForTaskCompletion(task.id);
    finalizeUploadProgressFromTask(uploadProgressViews.moduleDeploy, result);
    if (String(result.status || "").trim().toLowerCase() === "failed") {
      throw new Error(result.error || "批量模块部署执行失败");
    }
    appendLog("批量模块部署完成", `${autoVersionConfig?.version || ""} / ${moduleName}`);
    return;
  }
  const selectedFile = formData.get("deb_file");
  const serverFilePath = String(formData.get("server_file_path") || "").trim();
  formData.delete("auto_deploy");
  if (!(selectedFile instanceof File) || !selectedFile.name) {
    if (!extractFileNameFromServerPath(serverFilePath)) {
      throw new Error("请选择要部署的模块 deb 文件或填写文件服务器包路径");
    }
  }
  if (!serverFilePath && (!(selectedFile instanceof File) || !selectedFile.name)) {
    throw new Error("请选择要部署的模块 deb 文件");
  }

  await createModuleDeployTask(formData);
}

if (moduleDeployForm) {
  moduleDeployForm.addEventListener("submit", async (event) => {
    try {
      await submitModuleDeployForm(event);
    } catch (error) {
      appendLog("创建模块部署任务失败", error.message);
      alert(error.message);
    }
  });
}

remoteDirLoadButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    const targetSelectId = button.dataset.targetSelect;
    try {
      await loadRemoteDirectoryFromSelect(targetSelectId);
    } catch (error) {
      appendLog("02 区域目录加载失败", error.message);
      alert(error.message);
    }
  });
});

window.addEventListener("load", async () => {
  try {
    const initialPage = String(window.location.hash || "").replace(/^#/, "").trim() || "remote";
    switchPage(initialPage);
    switchGuidePage("flow");
    switchConfigPage("voice");
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
    hydrateConnectionCache(data.saved_connections || []);
    updateConnectionStatus(data.connected);
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
