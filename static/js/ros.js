/* ros.js */
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
/* ros.js */
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
/* ros.js */
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
/* ros.js */
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
/* ros.js */
rosNavButtons.forEach((button) => {
  button.addEventListener("click", () => {
    switchRosSection(button.dataset.rosTarget || "topic");
  });
});
