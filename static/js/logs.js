/* logs.js */
function setLogStatus(node, message, isError = false) {
  if (!node) {
    return;
  }
  node.textContent = message;
  node.classList.toggle("is-error", Boolean(isError));
}
/* logs.js */
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
/* logs.js */
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
