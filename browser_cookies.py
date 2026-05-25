"""Read Douyin cookies from local browsers (open or closed) or manual paste."""

from __future__ import annotations

import http.cookiejar
import os
import tempfile
import time
from pathlib import Path
from typing import Callable

from extract import ExtractError


def parse_manual_cookie(raw: str) -> tuple[str, dict[str, str]]:
  """Parse a browser Cookie header string into (header, dict)."""
  raw = (raw or "").strip()
  if not raw:
    raise ExtractError("Cookie 为空。")
  parts: list[str] = []
  cookie_dict: dict[str, str] = {}
  seen: set[str] = set()
  for segment in raw.split(";"):
    segment = segment.strip()
    if not segment or "=" not in segment:
      continue
    name, value = segment.split("=", 1)
    name = name.strip()
    value = value.strip()
    if not name or name in seen:
      continue
    seen.add(name)
    parts.append(f"{name}={value}")
    cookie_dict[name] = value
  header = "; ".join(parts)
  if not header:
    raise ExtractError("无法解析 Cookie 字符串。")
  return header, cookie_dict


def _jar_to_parts(jar: http.cookiejar.CookieJar) -> tuple[str, dict[str, str]]:
  parts: list[str] = []
  seen: set[str] = set()
  cookie_dict: dict[str, str] = {}
  for c in jar:
    if not c.name or c.name in seen:
      continue
    if c.value is None:
      continue
    domain = (c.domain or "").lower()
    if "douyin.com" not in domain:
      continue
    seen.add(c.name)
    parts.append(f"{c.name}={c.value}")
    cookie_dict[c.name] = c.value
  return "; ".join(parts), cookie_dict


def _copy_locked_file_windows(src: str, dst: str) -> bool:
  """Copy a file even when another process has it open (no admin)."""
  try:
    import win32con
    import win32file
  except ImportError:
    return False
  try:
    handle = win32file.CreateFile(
      src,
      win32file.GENERIC_READ,
      win32file.FILE_SHARE_READ
      | win32file.FILE_SHARE_WRITE
      | win32file.FILE_SHARE_DELETE,
      None,
      win32con.OPEN_EXISTING,
      win32file.FILE_ATTRIBUTE_NORMAL,
      None,
    )
    try:
      size = win32file.GetFileSize(handle)
      if size <= 0:
        return False
      _, data = win32file.ReadFile(handle, size)
      with open(dst, "wb") as out:
        out.write(data)
      return True
    finally:
      win32file.CloseHandle(handle)
  except Exception:
    return False


def _load_jar_from_path(
  loader: Callable[..., http.cookiejar.CookieJar],
  cookie_path: Path,
) -> http.cookiejar.CookieJar | None:
  """Try browser_cookie3 loader on a cookie DB path (works if browser is open)."""
  path_str = str(cookie_path)
  attempts = 3
  for attempt in range(attempts):
    try:
      return loader(cookie_file=path_str, domain_name="douyin.com")
    except Exception:
      pass
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
      copied = _copy_locked_file_windows(path_str, tmp_path)
      if not copied:
        try:
          import shutil

          shutil.copyfile(path_str, tmp_path)
          copied = True
        except Exception:
          copied = False
      if copied:
        try:
          return loader(cookie_file=tmp_path, domain_name="douyin.com")
        except Exception:
          pass
    finally:
      try:
        os.remove(tmp_path)
      except OSError:
        pass
    if attempt + 1 < attempts:
      time.sleep(0.25)
  return None


def _iter_chromium_cookie_files(user_data: Path) -> list[Path]:
  out: list[Path] = []
  if not user_data.is_dir():
    return out
  for profile in sorted(user_data.iterdir()):
    if not profile.is_dir():
      continue
    if profile.name != "Default" and not profile.name.startswith("Profile"):
      continue
    for rel in ("Network/Cookies", "Cookies"):
      p = profile / rel
      if p.is_file():
        out.append(p)
  return out


def _iter_firefox_cookie_files() -> list[Path]:
  out: list[Path] = []
  base = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles"
  if not base.is_dir():
    return out
  for profile in base.iterdir():
    if not profile.is_dir():
      continue
    p = profile / "cookies.sqlite"
    if p.is_file():
      out.append(p)
  return out


def _try_chromium_family(
  label: str,
  loader: Callable[..., http.cookiejar.CookieJar],
  user_data: Path,
) -> tuple[str, dict[str, str]]:
  paths = _iter_chromium_cookie_files(user_data)
  if not paths:
    raise ExtractError(f"未找到 {label} 的 Cookie 数据库。")
  last_err: str | None = None
  for cookie_path in paths:
    jar = _load_jar_from_path(loader, cookie_path)
    if jar is None:
      continue
    header, cookie_dict = _jar_to_parts(jar)
    if header:
      return header, cookie_dict
    last_err = f"{label}（{cookie_path.name}）中无 douyin.com Cookie"
  raise ExtractError(last_err or f"{label} 中未找到 douyin.com 的 Cookie")


def _try_firefox(loader: Callable[..., http.cookiejar.CookieJar]) -> tuple[str, dict[str, str]]:
  paths = _iter_firefox_cookie_files()
  if not paths:
    raise ExtractError("未找到 Firefox 配置目录。")
  for cookie_path in paths:
    jar = _load_jar_from_path(loader, cookie_path)
    if jar is None:
      continue
    header, cookie_dict = _jar_to_parts(jar)
    if header:
      return header, cookie_dict
  raise ExtractError("Firefox 中未找到 douyin.com 的 Cookie")


def _try_browser_default(
  load_fn: Callable[..., http.cookiejar.CookieJar],
  label: str,
) -> tuple[str, dict[str, str]]:
  try:
    jar = load_fn(domain_name="douyin.com")
  except Exception as e:
    raise ExtractError(f"读取 {label} Cookie 失败：{e}") from e
  header, cookie_dict = _jar_to_parts(jar)
  if header:
    return header, cookie_dict
  raise ExtractError(f"{label} 中未找到 douyin.com 的 Cookie")


def get_douyin_cookie_bundle(
  manual_cookie: str | None = None,
) -> tuple[str, dict[str, str]]:
  """
  Return (Cookie header string, name->value dict) for douyin.com.

  Works with the browser open or closed. Optional manual_cookie skips disk read.
  """
  if manual_cookie and manual_cookie.strip():
    return parse_manual_cookie(manual_cookie)

  import browser_cookie3

  local = os.environ.get("LOCALAPPDATA", "")
  errors: list[str] = []

  # Firefox locking is often looser — try first.
  try:
    return _try_firefox(browser_cookie3.firefox)
  except ExtractError as e:
    errors.append(str(e))

  edge_data = Path(local) / "Microsoft" / "Edge" / "User Data"
  try:
    return _try_chromium_family("Edge", browser_cookie3.edge, edge_data)
  except ExtractError as e:
    errors.append(str(e))

  chrome_data = Path(local) / "Google" / "Chrome" / "User Data"
  try:
    return _try_chromium_family("Chrome", browser_cookie3.chrome, chrome_data)
  except ExtractError as e:
    errors.append(str(e))

  for load_fn, label in (
    (browser_cookie3.firefox, "Firefox"),
    (browser_cookie3.edge, "Edge"),
    (browser_cookie3.chrome, "Chrome"),
  ):
    try:
      return _try_browser_default(load_fn, label)
    except ExtractError as e:
      errors.append(str(e))

  detail = "\n".join(errors[:4]) if errors else ""
  raise ExtractError(
    "无法读取抖音登录 Cookie。请确认已在浏览器登录 douyin.com。\n"
    "可在下方「Cookie（可选）」粘贴浏览器 Cookie 后重试（无需关浏览器）。\n"
    + (detail if detail else "")
  )


def get_douyin_cookie_header(manual_cookie: str | None = None) -> str:
  return get_douyin_cookie_bundle(manual_cookie)[0]


def get_douyin_cookies_dict(manual_cookie: str | None = None) -> dict[str, str]:
  return get_douyin_cookie_bundle(manual_cookie)[1]
