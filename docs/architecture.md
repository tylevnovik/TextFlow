# TextFlow Studio 架构说明

## 总体架构

- 桌面壳：Tauri 2
- 前端：React + TypeScript + Vite
- 引擎：Python 本地分析引擎
- 引擎通信：Tauri 启动一个常驻 Python sidecar，本地通过 HTTP 异步任务接口通信
- 数据持久化：用户数据目录下的 `.tfproj` 项目目录 + 可导入/导出的单文件 `.tfproj` 项目包

## 设计原则

- 项目数据与应用安装目录解耦
- 前端只负责状态和交互，不承载核心分析逻辑
- Python 引擎输出稳定的中间产物和结果 bundle
- Python 服务在桌面会话内只启动一次，退出桌面端时一并结束
- pipeline schema 预留 graph nodes/edges 字段
- run 目录一旦完成即视为不可变
- workspace 级状态单独保存，不把“当前项目选择”混进 `.tfproj` 本体
- 导入后的源文件优先复制进项目目录，保证项目迁移性和备份完整性
- source profile 需要能提供预置字段映射、别名、主文本字段和必填规则
- workspace 级模板与项目本体分离，项目模板/导入模板单独保存在 `templates/`

## 工作区元数据

- 位置：用户本地数据目录下的 `projects/workspace.json`
- 责任：
  - 记录 `current_project_id`
  - 记录 `recent_project_ids`
  - 为首页最近项目和当前项目选择提供稳定来源

## 项目生命周期动作

- `create-project`
- `open-project`
- `duplicate-project`
- `save-project`
- `import-project-files`
- `import-project-package`
- `run-pipeline`
- `export-project`
- `export-project-backup`
- `update-corpus-document`
- `delete-corpus-document`
- `save-project-template`
- `list-project-templates`
- `save-import-template`
- `list-import-templates`

这些动作都由 Python sidecar 负责持久化，Tauri 负责服务生命周期、任务轮询和进度事件，React 只负责状态与交互。

## 项目包与语料审查

- 工作区内部仍使用项目目录，便于缓存、运行记录和导出文件分层保存
- 用户侧可以导入/导出单文件 `.tfproj` 项目包，底层使用 zip 容器，但默认对终端用户隐藏压缩细节
- 数据页支持直接审查、编辑、删除语料文档；文档被修改后会清空旧的预处理结果，等待下一次 pipeline 重跑
- 新导入语料会记录源文件名、相对路径和行号，方便在 UI 里追踪来源

## 前后端通信

- 桌面启动后，Tauri 会优先拉起一个隐藏窗口的 Python sidecar
- Python sidecar 提供：
  - `GET /health`
  - `POST /tasks/start`
  - `GET /tasks/<task_id>`
- Tauri 命令层把前端动作转换成后端任务，并持续轮询任务状态
- 轮询过程中，Tauri 会向前端发出 `engine-progress` 事件，用于更新进度条和状态文字
- 桌面退出时，Tauri 会统一回收 Python sidecar，避免残留后台进程

## 打包策略

- 开发环境优先使用 `services/python-engine/dist/textflow-engine/textflow-engine.exe`
- 安装包资源同样携带目录式 sidecar，而不是单文件自解压模式
- 目录式打包避免了常驻服务模式下的重复解包和黑框体验问题
- Windows 安装包构建前会自动重建 Python sidecar，避免前后端资源版本不一致

## 模块划分

### apps/desktop
- 页面与导航
- 前端状态层
- 图表与表格可视化
- Tauri bridge

### services/python-engine
- 项目 schema 与文件存取
- 数据导入
- 清洗、标准化、分词、词表处理、过滤
- 统计分析、聚类、`YAKE` 关键词提取与 `NMF` 机构主题分析
- 导出与报告生成
  - 高分辨率 PNG 图表
  - 可选水印
  - 中文字体自动处理

### packages/shared-types
- Project、CorpusItem、DictionarySet、PipelineDefinition、RunRecord、ResultBundle 等领域模型
