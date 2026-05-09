# GitHub 文件同步管理器

基于 Python + Tkinter 开发的桌面端文件管理与云端同步工具，通过 GitHub 仓库作为存储后端，实现本地文件的增删改查、分类检索、文本预览以及与 GitHub 指定分支的双向同步，支持多端文件共享与查看。

## ✨ 功能特性

- 📁 **本地文件管理** — 文件/文件夹的增删改查、拖拽上传、批量操作
- ☁️ **GitHub 云端同步** — 推送/拉取文件到 GitHub 指定分支，支持文件夹递归同步
- 🔍 **分类与搜索** — 自动文件分类（文档/代码/图片/压缩包），关键词模糊搜索
- 👁️ **文本预览** — 支持 .txt/.md/.py/.json 等 20+ 种文本文件的实时预览
- 🔒 **安全存储** — Token 加密存储，SSL 证书安全管理
- 📦 **一键打包** — PyInstaller 打包为独立 EXE，无需 Python 环境即可运行

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.9+ |
| GUI | Tkinter |
| GitHub API | PyGithub |
| 打包 | PyInstaller |
| 安全 | certifi, python-dotenv |
| 测试 | pytest |

## 📂 项目结构

```
├── file_manager.py      # 主程序（MVC 架构）
├── requirements.txt     # 依赖列表
├── build.spec          # PyInstaller 打包配置
├── build.bat           # Windows 打包脚本
├── build.sh            # Linux/Mac 打包脚本
├── .env.example        # 环境变量示例
├── .gitignore          # Git 忽略规则
├── tests/              # 单元测试
│   ├── test_file_item.py
│   ├── test_file_store.py
│   └── test_github_sync.py
└── .github/workflows/  # CI/CD 配置
    ├── ci.yml
    └── release.yml
```

## 🚀 快速开始

### 环境要求

- Python 3.9 及以上
- pip 包管理器

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行程序

```bash
python file_manager.py
```

### 打包部署

**Windows：**
```bash
# 方式一：使用脚本
build.bat

# 方式二：手动打包
pyinstaller --clean --noconfirm build.spec
```

**Linux/Mac：**
```bash
chmod +x build.sh
./build.sh
```

打包产物位于 `dist/` 目录下。

## ⚙️ 配置说明

### GitHub 令牌

1. 前往 GitHub **Settings → Developer settings → Personal access tokens**
2. 点击 **Generate new token (classic)**
3. 勾选 `repo` 权限（完整仓库访问）
4. 生成并复制令牌

### 环境变量（可选）

复制 `.env.example` 为 `.env`，填入配置：

```bash
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPO=your_username/your_repo
GITHUB_BRANCH=main
```

## 🏗️ 架构设计

项目采用 MVC 分层架构：

| 层级 | 类 | 职责 |
|------|-----|------|
| Model | `FileItem`, `FileStore` | 数据实体与持久化 |
| Service | `GitHubSync` | GitHub API 通信 |
| View | `UIManager` | 界面渲染与交互 |
| Controller | `FileManagerApp` | 应用初始化与协调 |

## 🧪 测试

```bash
pytest tests/ -v
```

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 开源。
