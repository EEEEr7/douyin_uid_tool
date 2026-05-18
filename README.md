# douyin_uid_tool

从抖音主页链接或抖音号提取 **to_uid**（桌面 GUI + 命令行）。

## 使用

### 图形界面（exe）

1. 在 [Releases](https://github.com/EEEEr7/douyin_uid_tool/releases) 下载 `DouyinUIDExtractor.exe`，或本地运行 `build_exe.ps1` 生成。
2. 双击 `DouyinUIDExtractor.exe` 或 `launch_exe.bat`。
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

生成 `dist\DouyinUIDExtractor.exe`，并复制到项目根目录。

## 依赖

- Python 3.10+
- PySide6、requests、browser-cookie3

开发打包另需：`pip install -r requirements-dev.txt`
