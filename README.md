# 机器人控制台

这是一个本地部署的机器人升级控制台，基于 `FastAPI + Paramiko + Jinja2 + SQLite` 实现。启动后会在本机提供一个 Web 页面，用于连接 ORIN / PICO、执行部署、导出日志和查看历史任务。

## 当前能力

1. 通过 SSH 连接 ORIN，并缓存最近使用的 ORIN / PICO 连接信息
2. 执行整包部署，支持本地上传 `firmware` 包或直接填写文件服务器路径
3. 执行模块部署，按模块替换 `.deb` 并重启对应容器
5. 在后台持续跟踪任务状态、执行结果和详细日志
6. 保存部署历史、文件替换历史和回滚历史
7. 对支持的历史记录执行一键回滚
8. 浏览机器人远程目录、选择常用路径并扫描文件
9. 替换任意远程文件，并可在替换前自动备份
10. 导出 ORIN / PICO 日志压缩包，支持按时间范围筛选，ORIN 额外支持按模块筛选

## 环境要求

- Python 3.10 及以上
- 可访问目标机器人 ORIN 的网络环境
- 若需要部署到 PICO，当前电脑需要先能连接 ORIN，PICO 通过 ORIN 跳板访问

## 快速开始

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 前台启动：

```bash
python3 -m backend.main
```

3. 浏览器访问：

```text
http://127.0.0.1:8000
```

默认监听地址可通过环境变量覆盖：

```bash
APP_HOST=0.0.0.0 APP_PORT=8000 python3 -m backend.main
```

## 后台运行

项目内置了服务管理脚本 `service.sh`：

```bash
chmod +x service.sh
./service.sh start
./service.sh status
./service.sh restart
./service.sh stop
```

默认配置：

- `APP_HOST=0.0.0.0`
- `APP_PORT=8000`
- `PYTHON_BIN=python3`

也可以在启动时临时指定：

```bash
PYTHON_BIN=/path/to/python APP_PORT=9000 ./service.sh start
```

服务日志和 PID 文件位于：

- `.runtime/app.log`
- `.runtime/app.pid`

## 推荐使用流程

1. 打开页面后，先在 `远程连接` 页填写 ORIN 主机、端口、用户名和密码
2. 如果后续要部署 PICO 或导出 PICO 日志，同时填写 PICO 主机、端口、用户名和密码
3. 点击 `连接机器人`，确认右上角状态变为 `已连接`
4. 进入 `部署` 页，根据现场场景选择 `整包部署` 或 `模块部署`
5. 选择本地文件，或直接填写文件服务器包路径
6. 创建部署任务后，在 `后台任务` 中持续查看实时日志和结果
7. 如遇异常，进入 `日志` 页导出 ORIN / PICO 日志压缩包用于排查
8. 如需恢复，可在历史记录中对支持的任务执行回滚

## 两种部署方式

### 1. 整包部署

- 适合整机升级或整包覆盖
- 支持上传本地 `firmware` 包，也支持填写文件服务器路径
- 默认上传到目标处理器的 `/tmp`
- ORIN 整包部署直接使用当前 ORIN 连接
- PICO 整包部署通过当前已连接的 ORIN 跳板连接到 PICO
- 上传后系统会识别可选机型，必须手动确认机型后才能继续部署

相关配置来自 `static/deploy_config.json` 中的 `package` 段：

- `probe_command_template`：识别机型命令
- `install_template`：安装命令模板
- `start_command`：安装后启动命令
- `health_command`：健康检查命令
- `rollback_template`：自动回滚命令模板
- `auto_rollback`：是否在健康检查失败后自动回滚
- `machine_options`：机型下拉选项

### 2. 模块部署

- 适合替换单个模块的 `.deb`
- 需要先选择模块名，再上传对应模块包或填写文件服务器路径
- 模块包会上传到机器人模块分发目录下，再执行模块安装和容器重启
- 当前支持的模块选项默认来自 `static/deploy_config.json` 中的 `module.machine_options`

默认模块部署目录：

```text
/home/naviai/navi_project/.dists
```

## 页面功能说明

- `远程连接`：连接 ORIN / PICO，管理最近使用的缓存连接
- `部署`：执行整包部署、模块部署，并查看后台任务
- `日志`：导出 ORIN / PICO 日志压缩包
- `使用说明`：页面内置的操作流程、部署方式和排障提示
- `飞书云文档`：展示已配置的飞书文档链接

## 配置文件

### `static/deploy_config.json`

用于定义部署命令模板和下拉选项，至少包含以下两段：

- `package`：整包部署配置
- `module`：模块部署配置

现场使用前，建议优先确认以下内容是否符合机器人实际环境：

- 安装命令是否正确
- 启动命令是否需要补充
- 健康检查命令是否符合现场服务状态
- 回滚命令是否可执行
- 机型和模块下拉选项是否完整

### 自动部署配置

静态目录下保留了按页面拆分的配置文件：

- `static/page_configs/deploy.auto.json`
- `static/page_configs/deploy.json`
- `static/page_configs/ros.filters.json`
- `static/page_configs/ros.json`
- `static/page_configs/config.json`
- `static/page_configs/logs.json`
- `static/page_configs/feishu-doc.json`

其中：

- `deploy.auto.json` 用于页面中的自动部署版本下拉
- `deploy.json` 用于后端部署命令模板和部署页下拉项配置
- `ros.filters.json` 用于 ROS 页的前端筛选规则
- `ros.json` 用于 ROS 页的容器与命令模板配置
- `config.json` 用于配置页的远端文件路径与 reload service 配置
- `logs.json` 用于日志页的默认远端日志目录配置
- `feishu-doc.json` 用于页面中的飞书云文档入口

## 数据文件

运行后会自动生成以下数据：

- `data/operations.db`：SQLite 历史库，保存任务、部署、回滚和文件替换记录
- `data/connection_cache.json`：最近使用的连接缓存
- `.runtime/app.log`：后台服务日志
- `.runtime/app.pid`：后台服务 PID

兼容旧版本时，程序也会尝试迁移根目录下的旧数据文件。

## 目录结构

- `backend/`：后端逻辑，包括配置、会话、任务、SSH 客户端、部署服务和 API
- `templates/`：Jinja2 页面模板
- `static/`：前端脚本、样式和静态配置
- `data/`：运行时生成的数据文件
- `.runtime/`：后台运行日志和 PID 文件
- `static/deploy_config.json`：部署命令和下拉项配置
- `service.sh`：后台服务管理脚本

## 注意事项

- 当前服务默认前台监听 `127.0.0.1:8000`，通过 `service.sh` 启动时默认监听 `0.0.0.0:8000`
- SSH 主机密钥使用自动信任策略，更适合内网、测试或受控环境
- `data/connection_cache.json` 中会保存密码明文，共用电脑时请注意访问控制，必要时手动清空
- PICO 相关部署和日志导出依赖 ORIN 跳板，必须先成功连接 ORIN
- 整包部署的目标处理器连接信息来自当前页面连接信息和缓存，不来自 `static/deploy_config.json`
- 整包部署如果停在“等待继续”，通常是因为还没有确认机型
- 文件服务器路径模式可跳过浏览器上传，但前提是后端能够访问配置中的文件服务器
- 扫描远程根目录 `/` 会比较慢，建议优先选择业务目录
- 回滚是否可用取决于历史记录中是否保存了回滚命令或备份文件

## 常见排查

- 服务无法启动：先确认当前 Python 环境已安装 `requirements.txt` 中的依赖
- 页面能打开但无法连接机器人：优先检查网络、账号密码、端口和目标主机可达性
- 上传后无法继续：重点查看后台任务日志，并确认整包部署是否已经选择机型
- 部署失败：先复制任务日志，再导出对应时间范围内的 ORIN / PICO 日志一并排查
