# XTeink · 抖音UID采集

**© 2026 阅星曈 v1.2.0**

从抖音主页链接或抖音号采集 **UID**（桌面 GUI + 命令行）。

## 使用

### 图形界面（exe）

1. 在 [Releases](https://github.com/EEEEr7/douyin_uid_tool/releases) 下载程序，或本地运行 `build_exe.ps1` 生成。
2. 双击 **`XTeink 抖音UID采集.exe`** 或 `launch_exe.bat`。
3. 浏览器请先登录 [douyin.com](https://www.douyin.com)，查询前建议关闭浏览器以便读取 Cookie。

### 从源码运行

```powershell
py -3 -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pythonw.exe main.py
```

### 命令行

```powershell
.\.venv\Scripts\python.exe main.py "https://www.douyin.com/user/..."
.\.venv\Scripts\python.exe main.py "你的抖音号"
```

## 打包 exe

```powershell
.\build_exe.ps1
```

生成 `dist\XTeinkDouyinUID.exe`，并复制为项目根目录的 **`XTeink 抖音UID采集.exe`**。

## 分发给同事（推荐）

同事电脑**不需要安装 Python**，只需 Windows 10/11 64 位。

```powershell
.\package_release.ps1
```

会在 `release\` 下生成：

- `XTeinkDouyinUID-Windows-YYYYMMDD.zip` — 发给同事解压即用
- 内含：`XTeink 抖音UID采集.exe`、`launch_exe.bat`、`使用说明.txt` / `USAGE.txt`

你把 zip 通过微信 / 网盘 / U 盘发给同事即可。同事解压后双击 exe 或 `launch_exe.bat`。

## 依赖

- Python 3.10+
- PySide6、requests、browser-cookie3

开发打包另需：`pip install -r requirements-dev.txt`
