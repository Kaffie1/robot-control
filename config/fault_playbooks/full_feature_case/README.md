# Full Feature Case

这是一组真实会被 loader 加载的 playbook，用来验证：

- 目录扫描是否正常
- LLM 路由是否能命中
- 行为树字段是否都能被解析

注意：

- 当前工具注册表还是空的，所以命中并开始执行后，大概率会在工具调用阶段报“未找到 agent 工具”
- `call_playbook` 里的 `localization_map_mismatch` 如果不存在，也会在运行到该分支时报错

如果你现在的目标只是验证“有没有加载到 catalog、有没有走路由”，这组文件已经够用。
