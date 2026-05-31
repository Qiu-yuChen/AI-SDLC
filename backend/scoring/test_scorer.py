"""
测试评分器 — 双层评估：静态分析 + 动态运行

评估维度：
  第1层：静态分析（始终执行，80分）
    - test_files_exist  (20分)：测试目录是否有 .py 文件
    - test_functions    (25分)：AST 解析 def test_* 函数数量
    - assert_density    (15分)：AST 统计 assert 语句总数
    - conftest_content  (10分)：检查 conftest.py 是否有 fixture
    - test_lines        (10分)：测试代码总行数（反映详细程度）

  第2层：动态运行（pytest 可用时执行，20分）
    - fail_to_pass      (12分)：pytest 通过率
    - pass_to_pass      ( 8分)：两次运行结果一致性

  降级策略：pytest 收集到 0 个测试时，纯静态分析按 80→100 缩放。

依赖: pytest（可选）, ast（标准库）
"""
import ast
import subprocess
import re
from pathlib import Path
from typing import Dict, Tuple


class TestScorer:
    """单元测试评分器 — 双层评估"""

    def __init__(self, test_dir: Path, code_dir: Path):
        self.test_dir = Path(test_dir)
        self.code_dir = Path(code_dir)
        self._cached_run = None

    # ═══════════════════════════════════════════════════════
    # 第1层：静态分析（始终执行）
    # ═══════════════════════════════════════════════════════

    def _test_files_exist(self) -> Tuple[float, str]:
        """检查测试目录是否有有效的测试文件"""
        py_files = [
            f for f in self.test_dir.rglob("*.py")
            if f.name != "__init__.py" and "__pycache__" not in str(f)
        ]
        count = len(py_files)
        if count == 0:
            return 0.0, "未找到任何测试文件"
        score = min(20.0, count * 4.0)
        return score, f"{count} 个测试文件"

    def _test_functions(self) -> Tuple[float, str]:
        """AST 解析测试函数数量"""
        total = 0
        for f in self.test_dir.rglob("test_*.py"):
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                        total += 1
            except Exception:
                pass

        if total >= 30:
            score = 25.0
        elif total >= 20:
            score = 20.0
        elif total >= 10:
            score = 15.0
        elif total >= 5:
            score = 10.0
        elif total >= 1:
            score = 5.0
        else:
            score = 0.0
        return score, f"共 {total} 个 test_ 函数"

    def _assert_density(self) -> Tuple[float, str]:
        """AST 统计 assert 语句总数"""
        total_asserts = 0
        for f in self.test_dir.rglob("test_*.py"):
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assert):
                        total_asserts += 1
            except Exception:
                pass

        if total_asserts >= 60:
            score = 15.0
        elif total_asserts >= 30:
            score = 12.0
        elif total_asserts >= 15:
            score = 8.0
        elif total_asserts >= 5:
            score = 4.0
        else:
            score = 1.0
        return score, f"共 {total_asserts} 个 assert 断言"

    def _conftest_content(self) -> Tuple[float, str]:
        """检查 conftest.py 是否有 fixture 定义"""
        conftest = self.test_dir / "conftest.py"
        if not conftest.exists():
            return 3.0, "未找到 conftest.py"
        try:
            tree = ast.parse(conftest.read_text(encoding="utf-8"))
            fixtures = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for dec in node.decorator_list:
                        if isinstance(dec, ast.Call) and hasattr(dec.func, 'attr') and dec.func.attr == 'fixture':
                            fixtures += 1
                        elif isinstance(dec, ast.Name) and dec.id == 'fixture':
                            fixtures += 1
            if fixtures >= 3:
                score = 10.0
            elif fixtures >= 1:
                score = 6.0
            else:
                score = 3.0
            return score, f"conftest.py 有 {fixtures} 个 fixture"
        except Exception:
            return 3.0, "conftest.py 语法解析失败"

    def _test_lines(self) -> Tuple[float, str]:
        """测试代码总行数（反映测试详细程度）"""
        total_lines = 0
        for f in self.test_dir.rglob("test_*.py"):
            try:
                total_lines += len(f.read_text(encoding="utf-8").splitlines())
            except Exception:
                pass

        if total_lines >= 500:
            score = 10.0
        elif total_lines >= 300:
            score = 8.0
        elif total_lines >= 150:
            score = 6.0
        elif total_lines >= 50:
            score = 3.0
        else:
            score = 1.0
        return score, f"测试代码共 {total_lines} 行"

    # ═══════════════════════════════════════════════════════
    # 第2层：动态运行（pytest 可用时）
    # ═══════════════════════════════════════════════════════

    def _run_pytest(self) -> Dict:
        """执行 pytest，结果缓存"""
        if self._cached_run is not None:
            return self._cached_run
        try:
            r = subprocess.run(
                ["pytest", str(self.test_dir), "-q", "--tb=line"],
                capture_output=True, text=True, timeout=120,
            )
            self._cached_run = {
                "stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode,
            }
            return self._cached_run
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "timeout", "returncode": -1}
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "returncode": -1}

    def _parse(self, stdout: str) -> Dict:
        m = re.search(r"(\d+)\s+passed", stdout)
        passed = int(m.group(1)) if m else 0
        m = re.search(r"(\d+)\s+failed", stdout)
        failed = int(m.group(1)) if m else 0
        return {"passed": passed, "failed": failed, "total": passed + failed}

    def _f2p(self, parsed: Dict) -> Tuple[float, str]:
        if parsed["total"] == 0:
            return 0.0, "未收集到任何测试用例"
        rate = parsed["passed"] / parsed["total"]
        score = round(rate * 12, 1)
        return score, f"{parsed['passed']}/{parsed['total']} 通过 ({rate*100:.0f}%)"

    def _p2p(self) -> Tuple[float, str]:
        r1 = self._parse(self._run_pytest()["stdout"])
        cached = self._cached_run
        self._cached_run = None
        r2 = self._parse(self._run_pytest()["stdout"])
        self._cached_run = cached

        match = (r1["passed"], r1["failed"]) == (r2["passed"], r2["failed"])
        if match:
            return 8.0, "两次运行结果一致 ✓"
        return 0.0, f"不一致 | R1:{r1['passed']}p/{r1['failed']}f R2:{r2['passed']}p/{r2['failed']}f"

    # ═══════════════════════════════════════════════════════
    # 综合评估
    # ═══════════════════════════════════════════════════════

    def evaluate(self) -> Dict:
        """双层评估：静态分析 + 动态运行（自动降级）"""
        # ── 静态分析（始终执行）──
        sf1, sm1 = self._test_files_exist()
        sf2, sm2 = self._test_functions()
        sf3, sm3 = self._assert_density()
        sf4, sm4 = self._conftest_content()
        sf5, sm5 = self._test_lines()

        static_total = round(sf1 + sf2 + sf3 + sf4 + sf5, 1)
        static_max = 80

        # ── 动态运行 ──
        r1 = self._run_pytest()
        parsed = self._parse(r1["stdout"])
        pytest_available = parsed["total"] > 0

        if pytest_available:
            f2p_s, f2p_m = self._f2p(parsed)
            p2p_s, p2p_m = self._p2p()
            dynamic_total = round(f2p_s + p2p_s, 1)

            # 静态 + 动态 合并
            total = round(static_total + dynamic_total, 1)
            dynamic_used = True
        else:
            # 降级：纯静态分析按 80→100 缩放
            f2p_s, f2p_m = 0.0, "pytest 不可用（降级到静态分析）"
            p2p_s, p2p_m = 0.0, "pytest 不可用"
            dynamic_total = 0.0
            total = round(static_total / static_max * 100, 1)
            dynamic_used = False

        return {
            "total_score": min(total, 100.0),
            "max_score": 100,
            "evaluation_mode": "static+dynamic" if dynamic_used else "static_only",
            "breakdown": {
                "test_files":     {"score": sf1, "max": 20, "detail": sm1},
                "test_functions": {"score": sf2, "max": 25, "detail": sm2},
                "assert_density": {"score": sf3, "max": 15, "detail": sm3},
                "conftest":       {"score": sf4, "max": 10, "detail": sm4},
                "test_lines":     {"score": sf5, "max": 10, "detail": sm5},
                "fail_to_pass":   {"score": f2p_s, "max": 12, "detail": f2p_m},
                "pass_to_pass":   {"score": p2p_s, "max": 8, "detail": p2p_m},
            },
            "static_subtotal": static_total,
            "dynamic_subtotal": dynamic_total,
            "raw": parsed,
            "sweb_ref": (
                "SWE-bench §2.2 & §A.4 — "
                "Fail-to-Pass + Pass-to-Pass dual verification "
                "(with static analysis fallback)"
            ),
        }
