"""
代码质量评分器 — SWE-bench Section C.7 对齐

评估维度（7项）：
  - 语法正确性       (25分)：ast.parse 编译检查
  - 圈复杂度         (15分)：radon cc_visit  — SWE-bench 核心
  - 可维护性指数     (15分)：radon mi_visit  — SWE-bench 核心
  - 代码风格         (10分)：flake8 PEP 8 检查
  - 错误处理覆盖     (15分)：AST 分析 try/except
  - 文档注释覆盖     (10分)：AST 分析 docstring
  - 模块化程度       (10分)：文件数/行数比

依赖: radon, flake8, ast (标准库)
"""
import ast
import subprocess
from pathlib import Path
from typing import Dict, Tuple

try:
    from radon.complexity import cc_visit, cc_rank
    from radon.metrics import mi_visit
    HAS_RADON = True
except ImportError:
    HAS_RADON = False


class CodeScorer:
    """代码质量评分器"""

    def __init__(self, code_dir: Path):
        self.code_dir = Path(code_dir)

    # ── 指标1: 语法正确性 (25分) ──

    def _syntax(self) -> Tuple[float, str]:
        """
        使用 Python AST 解析器编译每个 .py 文件。
        AST 编译比 py_compile 更严格，能捕获更多语法问题。
        """
        errors = []
        py_files = list(self.code_dir.rglob("*.py"))
        if not py_files:
            return 0.0, "未找到 Python 文件"

        for f in py_files:
            try:
                ast.parse(f.read_text())
            except SyntaxError as e:
                errors.append(f"{f.name}:L{e.lineno} - {e.msg}")

        passed = len(py_files) - len(errors)
        score = round((passed / len(py_files)) * 25, 1)
        msg = f"{passed}/{len(py_files)} 个文件语法正确"
        if errors:
            msg += f" | 错误: {'; '.join(errors[:3])}"
        return score, msg

    # ── 指标2: 圈复杂度 (15分) — SWE-bench 核心 ──

    def _cyclomatic(self) -> Tuple[float, Dict]:
        """
        使用 radon 计算每个函数的圈复杂度 (Cyclomatic Complexity)。

        CC 含义：
          A(1-5)   : 简单、清晰、易测试
          B(6-10)  : 结构良好、可维护
          C(11-20) : 较复杂、需关注
          D(21-30) : 复杂、易出错
          F(>30)   : 不可测试、必须重构
        """
        if not HAS_RADON:
            return 7.5, {"error": "radon 未安装 (pip install radon)"}

        all_funcs = []
        for f in self.code_dir.rglob("*.py"):
            try:
                blocks = cc_visit(f.read_text())
                if blocks:
                    all_funcs.extend([
                        {
                            "file": f.name,
                            "name": b.name,
                            "complexity": b.complexity,
                            "rank": cc_rank(b.complexity),
                        }
                        for b in blocks
                    ])
            except Exception:
                pass

        if not all_funcs:
            return 15.0, {"message": "无函数可分析（可能全是空文件）"}

        avg_cc = sum(x["complexity"] for x in all_funcs) / len(all_funcs)
        high_risk = [x for x in all_funcs if x["complexity"] > 10]

        if avg_cc <= 5:
            score = 15.0
        elif avg_cc <= 10:
            score = 12.0
        elif avg_cc <= 20:
            score = 8.0
        elif avg_cc <= 30:
            score = 4.0
        else:
            score = 1.0

        return score, {
            "avg_complexity": round(avg_cc, 2),
            "total_functions": len(all_funcs),
            "high_risk_count": len(high_risk),
            "high_risk_functions": [
                f"{x['file']}::{x['name']} (CC={x['complexity']})"
                for x in high_risk[:5]
            ],
        }

    # ── 指标3: 可维护性指数 (15分) — SWE-bench 核心 ──

    def _maintainability(self) -> Tuple[float, Dict]:
        """
        使用 radon 计算可维护性指数 (Maintainability Index)。

        MI 综合公式: Halstead Volume + Cyclomatic Complexity + LOC
        MI 范围 0-100:
          >80  极易维护
          60-80 良好
          40-60 需改进
          <40  难以维护
        """
        if not HAS_RADON:
            return 7.5, {"error": "radon 未安装"}

        scores = []
        for f in self.code_dir.rglob("*.py"):
            try:
                mi = mi_visit(f.read_text(), multi=True)
                scores.append(mi)
            except Exception:
                pass

        if not scores:
            return 15.0, {"message": "无法计算（可能文件为空）"}

        avg_mi = sum(scores) / len(scores)

        if avg_mi > 80:
            score = 15.0
        elif avg_mi > 60:
            score = 12.0
        elif avg_mi > 40:
            score = 8.0
        else:
            score = 4.0

        return score, {"avg_mi": round(avg_mi, 2), "files_analyzed": len(scores)}

    # ── 指标4: 代码风格 (10分) ──

    def _flake8(self) -> Tuple[float, str]:
        """
        flake8 PEP 8 规范检查。
        统计 E/W/F 类问题数量，0 问题 = 满分。
        """
        try:
            r = subprocess.run(
                [
                    "flake8", str(self.code_dir),
                    "--max-line-length=120",
                    "--count",
                    "--exit-zero",
                    "--select=E,W,F",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            lines = r.stdout.strip().split("\n")
            issue_count = int(lines[-1]) if lines[-1].isdigit() else 0
            score = max(0.0, 10.0 - issue_count * 0.5)
            return score, f"{issue_count} 个 PEP 8 问题"
        except FileNotFoundError:
            return 5.0, "flake8 未安装"
        except Exception as e:
            return 5.0, f"flake8 执行失败: {e}"

    # ── 指标5: 错误处理覆盖 (15分) ──

    def _error_handling(self) -> Tuple[float, str]:
        """
        AST 分析：多少函数包含 try/except 块。
        真实世界的代码需要处理异常，尤其是 CSV 文件操作。
        """
        total_funcs = 0
        funcs_with_try = 0

        for f in self.code_dir.rglob("*.py"):
            try:
                tree = ast.parse(f.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        total_funcs += 1
                        if any(
                            isinstance(child, ast.Try)
                            for child in ast.walk(node)
                        ):
                            funcs_with_try += 1
            except Exception:
                pass

        if total_funcs == 0:
            return 15.0, "无函数定义"

        ratio = funcs_with_try / total_funcs
        # 阶梯制：简单函数（getter/setter/工具函数）不加异常处理正常，
        # 核心业务函数有 try/except 才加分
        if ratio >= 0.50:
            score = 15.0
        elif ratio >= 0.30:
            score = 12.0
        elif ratio >= 0.15:
            score = 8.0
        elif ratio >= 0.05:
            score = 4.0
        else:
            score = 1.0
        return score, f"{funcs_with_try}/{total_funcs} 个函数有异常处理"

    # ── 指标6: 文档注释覆盖 (10分) ──

    def _docstring(self) -> Tuple[float, str]:
        """
        AST 分析：多少函数/类有 docstring。
        赛题要求 "注释清晰，每个模块/类/函数有 docstring"。
        """
        total = 0
        with_doc = 0

        for f in self.code_dir.rglob("*.py"):
            try:
                tree = ast.parse(f.read_text())
                for node in ast.walk(tree):
                    if isinstance(
                        node,
                        (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                    ):
                        total += 1
                        if ast.get_docstring(node):
                            with_doc += 1
            except Exception:
                pass

        if total == 0:
            return 10.0, "无函数/类定义"

        ratio = with_doc / total
        score = round(ratio * 10, 1)
        return score, f"{with_doc}/{total} 有 docstring"

    # ── 指标7: 模块化程度 (10分) ──

    def _modularity(self) -> Tuple[float, str]:
        """
        文件数和每个文件的平均行数。
        理想: 每个文件 100-300 行，函数职责单一。
        """
        py_files = list(self.code_dir.rglob("*.py"))
        if not py_files:
            return 0.0, "无 Python 文件"

        total_lines = sum(
            len(f.read_text().splitlines()) for f in py_files
        )
        avg_lines = total_lines / len(py_files)

        if 100 <= avg_lines <= 300:
            score, level = 10.0, "理想"
        elif 50 <= avg_lines <= 500:
            score, level = 7.0, "可接受"
        elif avg_lines < 50:
            score, level = 4.0, "文件过多过碎"
        else:
            score, level = 4.0, "文件过大"

        return score, f"{len(py_files)} 个文件, 平均 {avg_lines:.0f} 行/文件 ({level})"

    # ── 综合 ──

    def evaluate(self) -> Dict:
        """执行全维度评分，返回结构化结果"""
        s1, m1 = self._syntax()
        s2, d2 = self._cyclomatic()
        s3, d3 = self._maintainability()
        s4, m4 = self._flake8()
        s5, m5 = self._error_handling()
        s6, m6 = self._docstring()
        s7, m7 = self._modularity()

        total = round(s1 + s2 + s3 + s4 + s5 + s6 + s7, 1)

        return {
            "total_score": total,
            "max_score": 100,
            "breakdown": {
                "syntax":           {"score": s1, "max": 25, "detail": m1},
                "cyclomatic":       {"score": s2, "max": 15, "detail": d2},
                "maintainability":  {"score": s3, "max": 15, "detail": d3},
                "flake8":           {"score": s4, "max": 10, "detail": m4},
                "error_handling":   {"score": s5, "max": 15, "detail": m5},
                "docstring":        {"score": s6, "max": 10, "detail": m6},
                "modularity":       {"score": s7, "max": 10, "detail": m7},
            },
            "sweb_ref": (
                "SWE-bench §C.7 — "
                "Cyclomatic Complexity + Maintainability Index (Halstead)"
            ),
        }
