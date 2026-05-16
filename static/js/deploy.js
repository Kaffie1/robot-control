/* deploy.js */
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
/* deploy.js */
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
    setPackageDeployHint(`已读取远端 ROBOT_TYPE=${normalizedSelectedMachineType}，已默认选中该机型；如有需要仍可手动切换，确认后点击“继续部署”。`);
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

function markPackageDeployFailed(message = "") {
  resetPackageDeployStage({ keepHint: true });
  setPackageMachineAttention(false);
  if (message) {
    setPackageDeployHint(`${message}，请重新上传 firmware 后再试。`, true);
  } else {
    setPackageDeployHint("部署失败，请重新上传 firmware 后再试。", true);
  }
}

function markModuleDeployFailed(message = "") {
  clearDeployTaskTracking("module");
  resetUploadProgress(uploadProgressViews.moduleDeploy, "等待上传");
  renderDeployFlow(deployFlowViews.module, deriveDeployFlow(null, null, "module"));
  if (moduleDeployFileInput) {
    moduleDeployFileInput.value = "";
  }
  setModuleDeployFileMeta(null);
  if (moduleDeployForm) {
    moduleDeployForm.reset();
  }
  const moduleSubmitBtn = moduleDeployForm?.querySelector('button[type="submit"]');
  if (moduleSubmitBtn instanceof HTMLButtonElement) {
    moduleSubmitBtn.disabled = false;
  }
  if (moduleAutoDeploySelect) {
    moduleAutoDeploySelect.value = "";
  }
  setModuleAutoDeployHint(message ? `${message}，请重新上传模块 deb 文件后再试。` : "部署失败，请重新上传模块 deb 文件后再试。", true);
}
/* deploy.js */
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

uploadProgressViews = {
  packageDeploy: createUploadProgressView("packageDeployUploadProgress"),
  moduleDeploy: createUploadProgressView("moduleDeployUploadProgress"),
};
deployFlowViews = {
  package: createDeployFlowView("packageDeployFlow"),
  module: createDeployFlowView("moduleDeployFlow"),
};

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

function clearDeployTaskTracking(deployMode) {
  if (deployMode === "package" || deployMode === "module") {
    currentDeployTaskIds[deployMode] = "";
  }
}

function findCurrentDeployTask(tasks = [], deployMode) {
  if (currentDeployTaskIds[deployMode]) {
    const currentTask = tasks.find((task) => task.id === currentDeployTaskIds[deployMode]);
    if (currentTask && !isTaskFinished(currentTask)) {
      return currentTask;
    }
    clearDeployTaskTracking(deployMode);
  }
  if (deployMode === "package" && packageDeployRequestInFlight) {
    return null;
  }
  const latestTask = tasks.find((task) => isDeployTask(task, deployMode) && !isTaskFinished(task));
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
  if (!resolvedTask && (deployMode === "package" || deployMode === "module")) {
    resolvedTask = lastFinishedDeployTasks[deployMode];
  }
  if (resolvedTask && isDeployTask(resolvedTask, deployMode)) {
    if (isTaskFinished(resolvedTask)) {
      lastFinishedDeployTasks[deployMode] = resolvedTask;
    } else {
      currentDeployTaskIds[deployMode] = resolvedTask.id;
    }
  }

  const resolvedStatus = String(resolvedTask && resolvedTask.status ? resolvedTask.status : "").trim().toLowerCase();
  if (resolvedTask && isDeployTask(resolvedTask, deployMode) && isTaskFinished(resolvedTask)) {
    clearDeployTaskTracking(deployMode);
  }

  if (deployMode === "package" && resolvedTask && resolvedStatus === "failed") {
    markPackageDeployFailed(String(resolvedTask.error || "部署失败，请查看后台日志"));
  } else if (deployMode === "module" && resolvedTask && resolvedStatus === "failed") {
    markModuleDeployFailed(String(resolvedTask.error || "部署失败，请查看后台日志"));
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
      const deployMode = String(task?.metadata?.deploy_mode || "").trim();
      if (deployMode === "package" || deployMode === "module") {
        lastFinishedDeployTasks[deployMode] = task;
      }
      clearDeployTaskTracking(deployMode);
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
/* deploy.js */
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
/* deploy.js */
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
      markPackageDeployFailed(error.message || "上传或识别机型失败");
      throw error;
    }
    if (retryResolution.cancelled) {
      markPackageDeployFailed(error.message || "上传或识别机型失败");
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
  packageDeployRequestInFlight = true;
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
  } finally {
    packageDeployRequestInFlight = false;
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
  packageDeployRequestInFlight = true;
  try {
    data = await submitUploadWithProgress("/api/package-upload-probe", formData, uploadProgressViews.packageDeploy, "package-probe", {
      skipBrowserUpload: conflictResolution.skipBrowserUpload,
    });
  } catch (error) {
    const retryResolution = await resolveDeployConflictFromError(formData, uploadProgressViews.packageDeploy, error);
    if (!retryResolution.handled) {
      markPackageDeployFailed(error.message || "上传并识别机型失败");
      throw error;
    }
    if (retryResolution.cancelled) {
      markPackageDeployFailed(error.message || "上传并识别机型失败");
      return;
    }
    data = await submitUploadWithProgress("/api/package-upload-probe", formData, uploadProgressViews.packageDeploy, "package-probe", {
      skipBrowserUpload: retryResolution.skipBrowserUpload,
    });
  } finally {
    packageDeployRequestInFlight = false;
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
      setPackageDeployHint(`已读取 ROBOT_TYPE=${selectedMachineType}，并默认选中该机型；如有需要仍可切换。点击“继续部署”后系统会按顺序执行当前版本下的 ${autoDeployUrls.length} 个包。`);
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
    markPackageDeployFailed(firstResult.error || "首个整包部署任务执行失败");
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
      markPackageDeployFailed(nextResult.error || `第 ${index + 1} 个整包部署任务执行失败`);
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
    const isContinueStage = packageDeployStageState.stage === "continue";
    appendLog(isContinueStage ? "继续整包安装失败" : "上传并识别机型失败", error.message);
    if (isContinueStage) {
      markPackageDeployFailed(error.message || "安装失败，请查看后台日志");
    } else {
      setPackageDeployHint(error.message, true);
    }
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
