# backend/agent

这里按领域收口，方便后续维护时先定位职责，再看实现文件。

## 建议的入口

- `orchestration/`
  - LLM 编排核心，包括模型创建、系统提示、路由图节点和状态定义
- `common/`
  - 通用日志、文本处理和跨子包复用工具
- `tools/`
  - 工具注册、工具参数 schema、工具执行
- `rules/`
  - 规则引擎、规则校验、断言解析
- `playbooks/`
  - playbook 加载、执行、匹配、脚本化故障上下文
- `conversation/`
  - 对话驱动、渲染、聊天支撑逻辑

## 现有实现文件

当前结构已经按领域收口完成，核心实现都放在各自子包里：

- `backend/agent/tools/`
  - `runtime.py`
  - `registry.py`
- `backend/agent/rules/`
  - `schema.py`
  - `engine.py`
- `backend/agent/playbooks/`
  - `loader.py`
  - `matcher.py`
  - `executor.py`
  - `catalog.py`
- `backend/agent/conversation/`
  - `runner.py`
  - `render.py`
  - `support.py`
- `backend/agent/orchestration/`
  - `model.py`
  - `prompts.py`
  - `router_nodes.py`
  - `router_state.py`
  - `routing.py`
