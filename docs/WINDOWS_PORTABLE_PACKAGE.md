# Windows 零依赖打包说明

目标：让评委在 Windows 电脑上无需安装 Python、Node.js、uv 等依赖，直接双击即可运行。

## 方案

- 前端先执行 `vite build`，生成静态页面。
- FastAPI 在生产模式下直接托管 `frontend/dist`。
- 使用 PyInstaller 把 `backend/app/desktop.py` 打成 Windows 可执行程序。
- 桌面入口会自动：
  - 选择本机空闲端口
  - 启动本地 HTTP 服务
  - 默认启用 `mock` 演示模式
  - 自动打开浏览器进入应用

评委拿到的是一个压缩包，解压后双击 `ResearchFlow.exe` 即可。

## 打包产物

- 可执行文件目录：`dist/windows/ResearchFlow/`
- 可分发压缩包：`dist/windows/ResearchFlow-windows-portable.zip`

## 本地 Windows 构建

前提：

- Windows 10/11
- Python 3.12
- Node.js 20+

执行：

```powershell
.\scripts\build_windows_bundle.ps1 -Clean
```

## GitHub Actions 构建

仓库已提供工作流：

- [`.github/workflows/windows-package.yml`](/Users/xcy/Program/SH-Program/Deep-Research/.github/workflows/windows-package.yml)

触发后会在 `Actions` 产出一个 artifact：

- `ResearchFlow-windows-portable`

下载并解压，把整个目录交给评委即可。

## 运行方式

评委机器上：

1. 解压 `ResearchFlow-windows-portable.zip`
2. 双击 `ResearchFlow.exe`
3. 浏览器会自动打开本地地址

关闭 `ResearchFlow.exe` 对应的控制台窗口即可停止程序。

## 演示模式与真实模式

默认行为：

- 桌面版默认 `DR_USE_MOCK_SOURCES=true`
- 不需要 API Key，适合答辩现场演示

如果你想在自己的机器上切换到真实检索/真实模型：

1. 把 `desktop.env.example` 复制为 `desktop.env`
2. 在同目录下填写 API Key
3. 设置 `DR_USE_MOCK_SOURCES=false`

桌面入口启动时会自动读取 `desktop.env`。

## 数据落盘位置

桌面版默认把数据库和导出文件放到：

- `%LOCALAPPDATA%\ResearchFlow\`

其中报告输出目录为：

- `%LOCALAPPDATA%\ResearchFlow\reports\`

这样不会写回程序目录，避免权限问题。
