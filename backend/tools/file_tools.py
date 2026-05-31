"""ReAct File Tools — File system operations for Agents"""
import functools
from pathlib import Path
from crewai.tools import tool


@functools.lru_cache(maxsize=128)
def _cached_read(path: str, mtime: float) -> str:
    """Cached file read, invalidated by file modification time"""
    file_path = Path(path)
    content = file_path.read_text(encoding="utf-8")
    if len(content) > 20000:
        content = content[:20000] + f"\n\n... (文件过长，已截断，共 {len(content)} 字符)"
    return content


@tool("read_file")
def read_file(path: str) -> str:
    """
    读取指定路径的文本文件内容（带缓存加速）。
    参数 path: 文件路径（绝对路径或相对路径）
    返回: 文件内容字符串
    """
    file_path = Path(path)
    if not file_path.exists():
        return f"❌ 文件不存在: {path}"
    try:
        mtime = file_path.stat().st_mtime
        return _cached_read(str(file_path.resolve()), mtime)
    except Exception as e:
        return f"❌ 读取失败: {str(e)}"


@tool("write_file")
def write_file(path: str, content: str) -> str:
    """
    将内容写入指定路径的文件。自动创建父目录。
    参数 path: 目标文件路径
    参数 content: 要写入的内容
    返回: 操作结果
    """
    file_path = Path(path)
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"✅ 文件已写入: {path} ({len(content)} 字符)"
    except Exception as e:
        return f"❌ 写入失败: {str(e)}"


@tool("list_directory")
def list_directory(path: str) -> str:
    """
    列出指定目录下的所有文件和子目录。
    参数 path: 目录路径
    返回: 文件/目录列表
    """
    dir_path = Path(path)
    if not dir_path.exists():
        return f"❌ 目录不存在: {path}"
    if not dir_path.is_dir():
        return f"❌ 不是目录: {path}"

    items = []
    for item in sorted(dir_path.rglob("*")):
        rel = item.relative_to(dir_path)
        if item.is_dir():
            items.append(f"📁 {rel}/")
        else:
            size = item.stat().st_size
            items.append(f"📄 {rel} ({size:,} bytes)")

    if not items:
        return f"📭 目录为空: {path}"
    return "\n".join(items[:50])  # Limit output
