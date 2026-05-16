/* common.js */
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
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatSubmitBtn = document.getElementById("chatSubmitBtn");
const chatClearBtn = document.getElementById("chatClearBtn");
const chatMessageList = document.getElementById("chatMessageList");
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

let uploadProgressViews = {
  packageDeploy: null,
  moduleDeploy: null,
};
let deployFlowViews = {
  package: null,
  module: null,
};

let selectedTaskId = "";
let dashboardTimer = null;
let heartbeatTimer = null;
let dashboardErrorShown = false;
let connectionState = false;
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
const lastFinishedDeployTasks = {
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
let packageDeployRequestInFlight = false;
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
const chatState = {
  messages: [],
  pending: false,
  pendingClarify: null,
};
let currentSessionId = "";
/* common.js */
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
  const response = await fetch(url, {
    credentials: "include",
    ...options,
  });
  const data = await response.json();
  if (!data.ok) {
    throw buildRequestError(data);
  }
  return data;
}
