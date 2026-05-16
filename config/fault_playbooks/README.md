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

- `playbook.yaml` 负责描述流程、工具调用、人工确认和失败分支。
- `rules.yaml` 负责描述断言规则和比较逻辑。
- 详细字段说明、输入输出说明、`confirmation` 写法、工具参数说明，都只写在对应模板文件顶部注释里。
- `README.md` 这里只保留目录结构和使用入口，不再重复维护详细参数文档。
