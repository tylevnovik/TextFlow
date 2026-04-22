# 开发与构建说明

## 环境要求

- Node.js `24+`
- npm `11+`
- Python `3.11+`
- Rust / Cargo
- Windows 为当前主要开发和打包目标

## 初始化

### Python 引擎

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-python.ps1
```

脚本会：

- 创建 `services/python-engine/.venv`
- 升级 `pip`
- 以 editable 模式安装引擎和开发依赖

### 前端依赖

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-frontend.ps1
```

脚本会把 npm 缓存固定到仓库内的 `.npm-cache`，减少环境漂移。

## 常用命令

### 启动桌面开发模式

```powershell
npm run dev
```

### TypeScript 检查

```powershell
npm run lint
```

注意：当前 `lint` 实际上是 `tsc --noEmit`，不是 ESLint。

### Python 测试

```powershell
npm run test:engine
```

或直接：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test-engine.ps1
```

## 构建

### 仅重建 Python sidecar

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-python-sidecar.ps1
```

产物目录：

```text
services/python-engine/dist/textflow-engine/
```

### 构建安装包

```powershell
npm run tauri:build --workspace apps/desktop
```

当前配置行为：

- Tauri 在 build 前会先执行 `scripts/build-desktop-release.ps1`
- `build-desktop-release.ps1` 会先重建 Python sidecar，再构建前端
- bundling 目标当前为 `NSIS`

## 词表快照更新

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\update-builtin-dictionaries.ps1
```

当前内置来源包括：

- `stopwords-iso`
- `THUOCL`
- `OpenCC`
- `client9/misspell`

## benchmark

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-large-benchmark.ps1
```

可选参数示例：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-large-benchmark.ps1 --limit 2000
```

## 当前测试与验证情况

截至 `2026-04-23`，本地已验证：

- `npm run lint` 通过
- `npm run test:engine` 通过，`48` 个测试全部通过

当前测试重点在：

- 项目存储与工作区 CLI
- 导入与 pipeline 主链
- workflow 节点目录和前后端 schema 一致性
- native DAG / bridge 的关键路径

## 当前开发注意事项

- 目前没有前端单元测试和 E2E 测试。
- 仓库中没有 CI 配置，回归主要依赖本地命令。
- Python 测试耗时接近 8 分钟，适合在较完整改动后执行。
- sidecar 打包依赖 `PyInstaller`，首次构建会慢一些。
- 大语料性能当前主要受关键词提取和导出写盘影响。

## 建议的开发节奏

1. 先跑 `bootstrap-python.ps1` 和 `bootstrap-frontend.ps1`
2. 日常修改时用 `npm run dev`
3. 提交前至少跑 `npm run lint`
4. 涉及引擎、workflow、存储或导出的改动再跑 `npm run test:engine`
5. 涉及打包时补跑 `build-python-sidecar.ps1` 或 `tauri:build`
