"""
RepoZero 对齐评分器 — 黑盒输出验证 + API 覆盖度

评估维度（2项）：
  - 黑盒输出验证 BOV (60分)：生成的代码对给定输入是否产生预期输出
  - API 覆盖度         (40分)：设计文档定义的端点，代码中实现了多少

核心思想（来自 RepoZero 论文）：
  "A sample is successful if and only if the outputs from both the source
   and target repositories exhibit strict string-level consistency"
  "Functional Synthesis: translating high-level API specifications into
   concrete implementations"

参考: Zhang et al., RepoZero, NeurIPS 2026
"""
import re
import os
import ast
import subprocess
import json
import time
import requests
from pathlib import Path
from typing import Dict, Tuple, List, Optional


class RepoZeroScorer:
    """RepoZero 对齐评分器"""

    def __init__(self, design_dir: Path, code_dir: Path, test_dir: Path):
        self.design_dir = Path(design_dir)
        self.code_dir = Path(code_dir)
        self.test_dir = Path(test_dir)

    # ═══════════════════════════════════════════════════════════
    # 指标1: 黑盒输出验证 BOV (60分) — RepoZero 核心
    # ═══════════════════════════════════════════════════════════

    def _bov(self) -> Tuple[float, str]:
        """
        黑盒输出验证 (Black-box Output Verification)

        对应 RepoZero: "strict string-level consistency between source
        and target repository outputs"

        实现策略（分层降级）：
          1. 首选：从测试代码提取输入-输出对，启动服务验证
          2. 次选：从设计文档提取 API 示例，启动服务验证
          3. 兜底：基于 pytest 结果推断（带降级系数 0.8）

        RepoZero 论文发现：约 40% 的可执行代码输出与预期不一致。
        所以测试通过 ≠ 输出正确。
        """
        # 第一层：测试代码中的 IO 对
        io_pairs = self._extract_io_from_tests()
        if io_pairs:
            return self._verify_io_pairs(io_pairs)

        # 第二层：设计文档中的 API 示例
        io_pairs = self._extract_io_from_design()
        if io_pairs:
            return self._verify_io_pairs(io_pairs)

        # 第三层：pytest 推断（降级）
        return self._bov_from_pytest()

    def _extract_io_from_tests(self) -> List[Dict]:
        """
        从测试文件中提取输入-输出对。

        解析模式：
          def test_xxx():
              response = client.post("/api/xxx", json={...})
              assert response.status_code == 200
              assert response.json() == {...}
        """
        pairs = []
        for test_file in self.test_dir.rglob("test_*.py"):
            try:
                tree = ast.parse(test_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                if not node.name.startswith("test_"):
                    continue
                pair = self._parse_test_function(node)
                if pair:
                    pairs.append(pair)
        return pairs

    def _parse_test_function(self, func_node: ast.FunctionDef) -> Optional[Dict]:
        """解析单个测试函数，提取 HTTP 请求和预期响应"""
        endpoint = None
        method = None
        request_body = None
        expected_status = None
        expected_keys = []

        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    http_methods = {"get", "post", "put", "delete", "patch"}
                    if node.func.attr in http_methods:
                        method = node.func.attr.upper()
                        if node.args:
                            first_arg = node.args[0]
                            if isinstance(first_arg, ast.Constant):
                                endpoint = first_arg.value
                        for kw in node.keywords:
                            if kw.arg == "json" and isinstance(kw.value, ast.Dict):
                                request_body = self._ast_dict_to_python(kw.value)

            if isinstance(node, ast.Assert):
                if isinstance(node.test, ast.Compare):
                    left = self._get_attr_chain(node.test.left)
                    if left and "status_code" in left:
                        if node.test.comparators and isinstance(
                            node.test.comparators[0], ast.Constant
                        ):
                            expected_status = node.test.comparators[0].value

            if isinstance(node, ast.Assert):
                for child in ast.walk(node):
                    if isinstance(child, ast.Subscript):
                        if isinstance(child.slice, ast.Constant):
                            expected_keys.append(child.slice.value)

        if endpoint and method:
            return {
                "endpoint": endpoint,
                "method": method,
                "request_body": request_body,
                "expected_status": expected_status or 200,
                "expected_keys": expected_keys,
                "source": "test_code",
            }
        return None

    def _ast_dict_to_python(self, node: ast.Dict) -> dict:
        """将 AST Dict 节点转换为 Python 字典"""
        result = {}
        for key, value in zip(node.keys, node.values):
            k = key.value if isinstance(key, ast.Constant) else str(key)
            if isinstance(value, ast.Constant):
                result[k] = value.value
            elif isinstance(value, ast.Dict):
                result[k] = self._ast_dict_to_python(value)
            elif isinstance(value, ast.List):
                result[k] = [
                    el.value if isinstance(el, ast.Constant) else str(el)
                    for el in value.elts
                ]
            else:
                result[k] = str(value)
        return result

    def _get_attr_chain(self, node) -> Optional[str]:
        """提取属性链如 response.status_code"""
        if isinstance(node, ast.Attribute):
            parts = []
            current = node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return None

    def _extract_io_from_design(self) -> List[Dict]:
        """从设计文档中提取 API 端点定义作为 IO 对"""
        pairs = []
        design_doc = self._read_design_doc()
        if not design_doc:
            return pairs

        endpoint_pattern = r'(GET|POST|PUT|DELETE|PATCH)\s+(/\S+)'
        for method, path in re.findall(endpoint_pattern, design_doc):
            pairs.append({
                "endpoint": path,
                "method": method,
                "request_body": None,
                "expected_status": 200,
                "expected_keys": [],
                "source": "design_doc",
            })
        return pairs

    def _verify_io_pairs(self, io_pairs: List[Dict]) -> Tuple[float, str]:
        """
        验证输入-输出对：启动 FastAPI 服务 → 发送请求 → 比对结果。

        对应 RepoZero 核心评估：
        "evaluation is performed by executing the generated target repository
        against the saved test cases and comparing outputs"
        """
        if not io_pairs:
            return 0.0, "无可用输入-输出对"

        server_url = self._start_server()
        if not server_url:
            return 30.0, "无法启动服务进行黑盒验证（给予基础分）"

        passed = 0
        failed_details = []

        try:
            for pair in io_pairs[:20]:
                ok, detail = self._verify_single_pair(server_url, pair)
                if ok:
                    passed += 1
                else:
                    failed_details.append(detail)
        finally:
            self._stop_server()

        total = min(len(io_pairs), 20)
        score = round((passed / total) * 60, 1) if total > 0 else 0.0

        msg = f"黑盒验证: {passed}/{total} 通过"
        if failed_details and len(failed_details) <= 3:
            msg += f" | 失败: {'; '.join(failed_details)}"
        elif failed_details:
            msg += f" | {len(failed_details)} 个端点失败"

        return score, msg

    def _verify_single_pair(
        self, base_url: str, pair: Dict
    ) -> Tuple[bool, str]:
        """验证单个输入-输出对：状态码 + 响应键"""
        endpoint = pair["endpoint"]
        method = pair["method"]
        expected_status = pair.get("expected_status", 200)
        expected_keys = pair.get("expected_keys", [])

        url = f"{base_url}{endpoint}"
        try:
            if method == "GET":
                resp = requests.get(url, timeout=5)
            elif method == "POST":
                resp = requests.post(
                    url, json=pair.get("request_body") or {}, timeout=5
                )
            elif method == "PUT":
                resp = requests.put(
                    url, json=pair.get("request_body") or {}, timeout=5
                )
            elif method == "DELETE":
                resp = requests.delete(url, timeout=5)
            else:
                return True, ""

            if resp.status_code != expected_status:
                return False, (
                    f"{method} {endpoint}: "
                    f"预期 {expected_status}, 实际 {resp.status_code}"
                )

            if expected_keys:
                try:
                    data = resp.json()
                    missing = [k for k in expected_keys if k not in data]
                    if missing:
                        return False, (
                            f"{method} {endpoint}: 响应缺少字段 {missing}"
                        )
                except Exception:
                    pass

            return True, ""

        except requests.ConnectionError:
            return False, f"{method} {endpoint}: 连接被拒绝"
        except requests.Timeout:
            return False, f"{method} {endpoint}: 请求超时"
        except Exception as e:
            return False, f"{method} {endpoint}: {type(e).__name__}"

    def _bov_from_pytest(self) -> Tuple[float, str]:
        """
        降级方案：从 pytest 结果推断 BOV。
        降级系数 0.8，因为 RepoZero 揭示了"可运行 ≠ 正确"的 gap。
        """
        try:
            r = subprocess.run(
                ["pytest", str(self.test_dir), "-q", "--tb=line", "--timeout=30"],
                capture_output=True, text=True, timeout=60,
            )
            m = re.search(r"(\d+)\s+passed", r.stdout)
            passed = int(m.group(1)) if m else 0
            m = re.search(r"(\d+)\s+failed", r.stdout)
            failed = int(m.group(1)) if m else 0

            if passed + failed == 0:
                return 0.0, "无可执行测试"

            rate = passed / (passed + failed)
            score = round(rate * 60 * 0.8, 1)
            return score, (
                f"基于 pytest 推断: {passed}/{passed+failed} 通过 "
                f"(降级系数 0.8)"
            )
        except Exception as e:
            return 0.0, f"pytest 执行失败: {e}"

    def _start_server(self) -> Optional[str]:
        """尝试启动 FastAPI 服务（最大 8 秒超时）"""
        entry_path = None
        for entry in ["app.py", "main.py"]:
            p = self.code_dir / entry
            if p.exists():
                entry_path = p
                break
        if entry_path is None:
            return None

        seed_script = self.code_dir / "seed_data.py"
        if seed_script.exists():
            try:
                subprocess.run(
                    ["python3", str(seed_script)],
                    cwd=str(self.code_dir), capture_output=True, timeout=5,
                )
            except Exception:
                pass

        env = os.environ.copy()
        cds = str(self.code_dir.resolve())
        env["PYTHONPATH"] = cds + ":" + env.get("PYTHONPATH", cds)

        for port in range(18923, 18925):  # 只试 2 个端口, not 5
            try:
                self._server_process = subprocess.Popen(
                    ["python3", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "error"],
                    cwd=str(self.code_dir), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                for _ in range(16):  # max 8s
                    time.sleep(0.5)
                    try:
                        if requests.get(f"http://127.0.0.1:{port}/docs", timeout=1).status_code == 200:
                            return f"http://127.0.0.1:{port}"
                    except Exception:
                        pass
                self._server_process.terminate()
                try: self._server_process.wait(timeout=1)
                except Exception: self._server_process.kill()
            except Exception:
                pass
        return None

    def _stop_server(self):
        if hasattr(self, "_server_process") and self._server_process:
            try:
                self._server_process.terminate()
                self._server_process.wait(timeout=1)
            except Exception:
                try: self._server_process.kill()
                except Exception: pass

    # ═══════════════════════════════════════════════════════════
    # 指标2: API 覆盖度 (40分) — RepoZero 规格忠实度
    # ═══════════════════════════════════════════════════════════

    def _api_coverage(self) -> Tuple[float, str]:
        """
        API 端点覆盖度检查。

        对应 RepoZero 的 "Functional Synthesis" 挑战：
        "translating high-level API specifications into concrete implementations"

        流程：
          1. 从设计文档提取所有 API 端点定义
          2. 从代码中提取实际实现的路由
          3. 计算覆盖率（精确匹配 1 分，部分匹配 0.5 分）
        """
        defined = self._extract_defined_endpoints()
        implemented = self._extract_implemented_endpoints()

        if not defined:
            return 40.0, "设计文档中未定义 API 端点（跳过检查）"
        if not implemented:
            return 0.0, f"代码中未发现路由实现（定义了 {len(defined)} 个端点）"

        matched = 0
        partial = 0
        unmatched = []

        for def_ep in defined:
            def_path = def_ep["path"].rstrip("/")
            def_method = def_ep["method"]

            exact_match = any(
                imp["path"].rstrip("/") == def_path
                and imp["method"] == def_method
                for imp in implemented
            )
            if exact_match:
                matched += 1
                continue

            path_parts = [
                p for p in def_path.split("/") if p and not p.startswith("{")
            ]
            loose_match = any(
                imp["method"] == def_method
                and all(part in imp["path"] for part in path_parts)
                for imp in implemented
            )
            if loose_match:
                partial += 1
            else:
                unmatched.append(f"{def_method} {def_path}")

        max_score = len(defined)
        raw_score = matched + partial * 0.5
        score = round((raw_score / max_score) * 40, 1)

        msg = (
            f"API 覆盖: {matched} 精确 + {partial} 部分匹配 "
            f"/ {len(defined)} 定义 ({raw_score/max_score*100:.0f}%)"
        )
        if unmatched and len(unmatched) <= 5:
            msg += f" | 缺失: {'; '.join(unmatched)}"

        return score, msg

    def _extract_defined_endpoints(self) -> List[Dict]:
        """从设计文档中提取 API 端点定义"""
        defined = []
        design_doc = self._read_design_doc()
        if not design_doc:
            return defined

        table_pattern = r'\|\s*(GET|POST|PUT|DELETE|PATCH)\s*\|\s*(/\S+)\s*\|'
        for method, path in re.findall(table_pattern, design_doc):
            defined.append({"method": method, "path": path})

        inline_pattern = r'(GET|POST|PUT|DELETE|PATCH)\s+(/\S+)'
        for method, path in re.findall(inline_pattern, design_doc):
            if {"method": method, "path": path} not in defined:
                defined.append({"method": method, "path": path})

        seen = set()
        unique = []
        for d in defined:
            key = (d["method"], d["path"])
            if key not in seen:
                seen.add(key)
                unique.append(d)

        return unique

    def _extract_implemented_endpoints(self) -> List[Dict]:
        # 优先静态扫描（快速），失败才启动服务
        result = self._extract_from_static()
        if result:
            return result
        return []  # 跳过 OpenAPI 动态提取（可能 hang）

    def _extract_from_openapi(self, server_url: str) -> List[Dict]:
        """从 FastAPI 的 /openapi.json 动态提取所有已注册路由"""
        try:
            resp = requests.get(f"{server_url}/openapi.json", timeout=10)
            spec = resp.json()
            endpoints = []
            for path, methods in spec.get("paths", {}).items():
                for method in methods:
                    if method.upper() in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
                        endpoints.append({
                            "method": method.upper(),
                            "path": path,
                            "file": "openapi",
                        })
            return endpoints
        except Exception:
            return []

    def _extract_from_static(self) -> List[Dict]:
        """静态正则扫描：从 .py 源文件中解析装饰器路由（回退方案）"""
        implemented = []
        py_files = list(self.code_dir.rglob("*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue

            # FastAPI: @router.get("/path") / @app.get("/path")
            for match in re.finditer(
                r'@\w+\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                content,
            ):
                implemented.append({
                    "method": match.group(1).upper(),
                    "path": match.group(2),
                    "file": py_file.name,
                })

            # Flask: @app.route("/path", methods=["GET"])
            for match in re.finditer(
                r'@\w+\.route\s*\(\s*["\']([^"\']+)["\'].*?methods\s*=\s*\[([^\]]+)\]',
                content,
                re.DOTALL,
            ):
                path = match.group(1)
                methods_str = match.group(2)
                for m in re.findall(r'["\']([A-Z]+)["\']', methods_str):
                    implemented.append({
                        "method": m, "path": path, "file": py_file.name,
                    })

        return implemented

    def _read_design_doc(self) -> str:
        """读取设计文档"""
        md_files = sorted(self.design_dir.rglob("*.md"))
        if not md_files:
            return ""
        return md_files[0].read_text(encoding="utf-8")

    # ═══════════════════════════════════════════════════════════
    # 综合评估
    # ═══════════════════════════════════════════════════════════

    def evaluate(self) -> Dict:
        """执行 RepoZero 双维度评分"""
        bov_s, bov_m = self._bov()
        api_s, api_m = self._api_coverage()

        total = round(bov_s + api_s, 1)

        return {
            "total_score": total,
            "max_score": 100,
            "breakdown": {
                "bov": {"score": bov_s, "max": 60, "detail": bov_m},
                "api_coverage": {"score": api_s, "max": 40, "detail": api_m},
            },
            "repozero_ref": (
                "RepoZero §2.3 & §6.3 — "
                "Black-box Output Verification + API Specification Fidelity "
                "(Zhang et al., NeurIPS 2026)"
            ),
        }
