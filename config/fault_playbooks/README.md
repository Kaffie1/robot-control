# Fault Playbooks

每个故障一个目录，推荐结构如下：

```text
config/fault_playbooks/<playbook_id>/
  playbook.yaml
  rules.yaml
  script.py        # 可选
  README.md        # 可选
```

新增 playbook 时，优先复制这两个模板：

- `config/fault_playbooks/playbook.template.yaml`
- `config/fault_playbooks/rules.template.yaml`

约定如下：

- `playbook.yaml` 现在推荐用行为树 `root` 来描述流程、工具调用、人工确认和结论分支。
- 旧 `script` 写法仍兼容，但新增 playbook 默认不要再使用旧格式。
- `rules.yaml` 负责描述断言规则和比较逻辑。
- 详细字段说明、输入输出说明、`confirmation` 写法、工具参数说明，都只写在对应模板文件顶部注释里。
- `README.md` 这里只保留目录结构和使用入口，不再重复维护详细参数文档。

## 人工确认示例

下面给一组“工具缺参数，需要向客户索取”的完整示例。假设故障是“没有定位”，恢复动作需要客户补充 `map_name`。

### playbook.yaml

```yaml
version: 1
description: localization lost with human confirmation

playbooks:
  - id: localization_lost
    title: 没有定位
    root:
      type: selector
      name: localization_root
      children:
        - type: condition
          name: already_localized
          tool_name: check_localization
          arguments:
            robot_id: "{{ robot_id }}"
          assert_ref: rule_localized
          success_message: 当前已有定位

        - type: sequence
          name: recover_localization
          children:
            - type: action
              name: relocalize_with_customer_map
              tool_name: trigger_relocalization
              arguments:
                robot_id: "{{ robot_id }}"
                map_name:
                  from_context: map_name
              require_confirmation: true
              confirmation:
                when: before
                mode: input
                message: 请向客户确认当前使用的地图名称
                input:
                  type: text
                  label: 地图名称
                  placeholder: 例如 factory_map_b1
                  help_text: 让客户提供当前机器人实际使用的地图名
                  allow_empty: false
                output:
                  store_as: map_name
                  type: raw_input
              assert_ref: rule_relocalize_triggered
              failure_message: 重定位动作未成功触发
              success_message: 已触发重定位动作

            - type: condition
              name: verify_localization_after_recovery
              tool_name: check_localization
              arguments:
                robot_id: "{{ robot_id }}"
              assert_ref: rule_localized
              wait_seconds: 3
              confirm_times: 2
              failure_message: 重定位后仍未恢复定位

        - type: result
          name: localization_not_recovered
          status: failure
          message: 当前仍然没有定位，需要现场继续处理
```

### rules.yaml

```yaml
version: 1
description: rules for localization lost

rules:
  rule_localized:
    type: compare
    field: result.localized
    op: boolean_true

  rule_relocalize_triggered:
    type: compare
    field: result.accepted
    op: boolean_true
```

### 第一次 `/api/chat` 请求

```json
{
  "message": "机器人现在没有定位"
}
```

如果 `tool_context` 里还没有 `map_name`，playbook 会在 `relocalize_with_customer_map` 这个节点中断，返回：

```json
{
  "ok": true,
  "model": "<model>",
  "message": "请向客户确认当前使用的地图名称",
  "tool_traces": [
    {
      "name": "already_localized",
      "arguments": {
        "robot_id": "R001"
      },
      "result": "{'localized': False}"
    }
  ],
  "pending_confirmation": {
    "type": "playbook_confirmation",
    "playbook_id": "localization_lost",
    "playbook_title": "没有定位",
    "node_path": "root.children[1].children[0]",
    "node_name": "relocalize_with_customer_map",
    "tool_name": "trigger_relocalization",
    "message": "请向客户确认当前使用的地图名称",
    "mode": "input",
    "input": {
      "type": "text",
      "label": "地图名称",
      "placeholder": "例如 factory_map_b1",
      "help_text": "让客户提供当前机器人实际使用的地图名",
      "allow_empty": false
    },
    "output": {
      "store_as": "map_name",
      "type": "raw_input"
    }
  },
  "continuation": {
    "kind": "playbook_confirmation",
    "user_message": "机器人现在没有定位",
    "playbook_id": "localization_lost",
    "playbook_title": "没有定位",
    "reason": "用户描述与没有定位问题匹配",
    "tool_context": {
      "robot_id": "R001"
    },
    "resume_state": {
      "...": "已执行节点快照"
    },
    "pending_confirmation": {
      "...": "与上面相同"
    }
  }
}
```

### 第二次 `/api/chat` 请求

把客户回复作为 `message`，把上一次的 `continuation` 原样带回：

```json
{
  "message": "factory_map_b1",
  "continuation": {
    "kind": "playbook_confirmation",
    "user_message": "机器人现在没有定位",
    "playbook_id": "localization_lost",
    "playbook_title": "没有定位",
    "reason": "用户描述与没有定位问题匹配",
    "tool_context": {
      "robot_id": "R001"
    },
    "resume_state": {
      "...": "上一次返回的快照"
    },
    "pending_confirmation": {
      "type": "playbook_confirmation",
      "playbook_id": "localization_lost",
      "playbook_title": "没有定位",
      "node_path": "root.children[1].children[0]",
      "node_name": "relocalize_with_customer_map",
      "tool_name": "trigger_relocalization",
      "message": "请向客户确认当前使用的地图名称",
      "mode": "input",
      "input": {
        "type": "text",
        "label": "地图名称",
        "placeholder": "例如 factory_map_b1",
        "help_text": "让客户提供当前机器人实际使用的地图名",
        "allow_empty": false
      },
      "output": {
        "store_as": "map_name",
        "type": "raw_input"
      }
    }
  }
}
```

这次后端会把：

- `message = "factory_map_b1"` 视为确认回复
- 按 `output.store_as = map_name` 写回 `tool_context`
- 用 `resume_state` 从中断点继续执行 playbook

### 当前确认能力边界

- 目前只支持 `confirmation.when: before`
- `mode` 支持 `approve` / `input` / `select`
- `select` 目前只支持静态 `input.options`
- `output.store_as` 必填，确认结果会写回 `tool_context`
- 如果 `store_as` 对应值已经存在，则不会再次中断

### 三种确认模式最小写法

`approve`

```yaml
require_confirmation: true
confirmation:
  when: before
  mode: approve
  message: 请确认是否允许继续执行恢复动作
  output:
    store_as: operator_approved
    type: boolean
```

`input`

```yaml
require_confirmation: true
confirmation:
  when: before
  mode: input
  message: 请向客户索取站点编号
  input:
    type: text
    label: 站点编号
    allow_empty: false
  output:
    store_as: station_id
    type: raw_input
```

`select`

```yaml
require_confirmation: true
confirmation:
  when: before
  mode: select
  message: 请让客户从以下地图中选择当前地图
  input:
    type: text
    auto_select_if_single: true
    options:
      - label: B1 地图
        value: factory_map_b1
      - label: B2 地图
        value: factory_map_b2
  output:
    store_as: map_name
    type: selected_option_value
```
