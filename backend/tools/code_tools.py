"""ReAct Code Tools — Code quality & syntax check operations"""

import subprocess
import tempfile
from pathlib import Path
from crewai.tools import tool


@tool("syntax_check")
def syntax_check(file_path: str) -> str:
    """
    使用 Python 编译器检查单个文件的语法正确性。
    参数 file_path: Python 文件路径
    返回: 语法检查结果
    """
    path = Path(file_path)
    if not path.exists():
        return f"❌ 文件不存在: {file_path}"

    try:
        result = subprocess.run(
            ["python3", "-m", "py_compile", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return f"✅ 语法检查通过: {file_path}"
        else:
            return f"❌ 语法错误:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return "⚠️ 语法检查超时"
    except Exception as e:
        return f"❌ 检查失败: {str(e)}"


@tool("format_code")
def format_code_file(file_path: str) -> str:
    """
    使用 autopep8 或 black 格式化 Python 代码。
    参数 file_path: Python 文件路径
    返回: 格式化结果
    """
    path = Path(file_path)
    if not path.exists():
        return f"❌ 文件不存在: {file_path}"

    # Try autopep8 first, then black
    for formatter in ["autopep8", "black"]:
        try:
            result = subprocess.run(
                [formatter, "--in-place", str(path)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                return f"✅ 已使用 {formatter} 格式化: {file_path}"
        except FileNotFoundError:
            continue
        except Exception:
            continue

    return f"ℹ️ 格式化工具不可用，文件保持原样: {file_path}"
