"""ReAct Quality Tools — Code quality & design validation"""

import json
import subprocess
from pathlib import Path
from crewai.tools import tool


@tool("validate_design")
def validate_design_completeness(design_doc_path: str) -> str:
    """
    检查概要设计文档是否包含所有必要章节。
    参数 design_doc_path: 设计文档路径
    返回: 完整性检查报告
    """
    path = Path(design_doc_path)
    if not path.exists():
        return f"❌ 文档不存在: {design_doc_path}"

    content = path.read_text(encoding="utf-8")

    checks = {
        "系统概述/背景": ["系统概述", "项目背景", "需求背景"],
        "系统架构设计": ["架构设计", "系统架构", "架构图", "Mermaid"],
        "模块划分": ["模块划分", "功能模块", "模块说明"],
        "API 接口设计": ["API", "接口设计", "REST", "端点"],
        "数据模型设计": ["数据模型", "表结构", "字段", "CSV"],
        "流程图": ["流程图", "sequence", "流程"],
    }

    results = []
    score = 0
    for section_name, keywords in checks.items():
        found = any(kw in content for kw in keywords)
        if found:
            results.append(f"✅ {section_name}: 已包含")
            score += 1
        else:
            results.append(f"❌ {section_name}: 缺失 — 请补充")
    results.append(f"\n📊 完整度评分: {score}/{len(checks)} ({score/len(checks)*100:.0f}%)")

    return "\n".join(results)


@tool("lint_check")
def lint_check(code_path: str) -> str:
    """
    使用 flake8 检查代码规范。
    参数 code_path: 代码文件或目录路径
    返回: flake8 检查结果
    """
    path = Path(code_path)
    if not path.exists():
        return json.dumps({
            "status": "error",
            "message": f"路径不存在: {code_path}",
            "errors": [],
            "error_count": 0,
        })

    try:
        result = subprocess.run(
            ["flake8", str(path), "--max-line-length", "120", "--exit-zero"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        errors = [line.strip() for line in result.stdout.split("\n") if line.strip()]
        return json.dumps({
            "status": "ok",
            "message": f"发现 {len(errors)} 个代码规范问题" if errors else "代码规范检查通过",
            "errors": errors[:50],
            "error_count": len(errors),
        })
    except FileNotFoundError:
        return json.dumps({
            "status": "skipped",
            "message": "flake8 未安装，跳过检查",
            "errors": [],
            "error_count": 0,
        })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e),
            "errors": [],
            "error_count": 0,
        })


@tool("coverage_check")
def coverage_check(test_path: str, src_path: str) -> str:
    """
    调用 pytest-cov 计算测试覆盖率。
    参数 test_path: 测试文件或目录路径
    参数 src_path: 源代码文件或目录路径
    返回: 覆盖率报告
    """
    test = Path(test_path)
    src = Path(src_path)
    if not test.exists():
        return json.dumps({
            "status": "error",
            "message": f"测试路径不存在: {test_path}",
            "coverage_percent": 0,
        })

    try:
        result = subprocess.run(
            ["python3", "-m", "pytest", str(test),
             f"--cov={src}",
             "--cov-report=term",
             "--cov-report=json",
             "-q", "--tb=short", "--timeout=60"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        # Parse coverage percentage from stdout
        coverage = 0
        for line in result.stdout.split("\n"):
            if "TOTAL" in line:
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        coverage = int(parts[-1].rstrip("%"))
                    except ValueError:
                        pass

        return json.dumps({
            "status": "ok",
            "message": f"覆盖率: {coverage}%",
            "coverage_percent": coverage,
        })
    except FileNotFoundError:
        return json.dumps({
            "status": "skipped",
            "message": "pytest/pytest-cov 未安装，跳过覆盖率检查",
            "coverage_percent": 0,
        })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e),
            "coverage_percent": 0,
        })


@tool("calculate_quality")
def calculate_quality_score(lint_result: str = "", coverage_result: str = "") -> str:
    """
    汇总 lint 和 coverage 结果，计算综合质量评分（0-100分）。
    参数 lint_result: lint_check 返回的 JSON 字符串
    参数 coverage_result: coverage_check 返回的 JSON 字符串
    返回: 综合质量评分 JSON
    """
    score = 50  # Base score
    total = 100
    details = []

    # Parse lint result
    try:
        lint_data = json.loads(lint_result) if lint_result else {}
        lint_errors = lint_data.get("error_count", 0)
        if lint_data.get("status") == "ok":
            if lint_errors == 0:
                score += 25
                details.append("代码规范: 完美 ✓")
            elif lint_errors <= 5:
                score += 15
                details.append(f"代码规范: 良好 (5个以内问题)")
            elif lint_errors <= 20:
                score += 5
                details.append(f"代码规范: 一般 ({lint_errors}个问题)")
            else:
                details.append(f"代码规范: 差 ({lint_errors}个问题)")
        elif lint_data.get("status") == "skipped":
            score += 10
            details.append("代码规范: 跳过检查")
    except (json.JSONDecodeError, Exception):
        pass

    # Parse coverage result
    try:
        cov_data = json.loads(coverage_result) if coverage_result else {}
        cov_pct = cov_data.get("coverage_percent", 0)
        if cov_data.get("status") == "ok":
            if cov_pct >= 80:
                score += 25
                details.append(f"测试覆盖率: {cov_pct}% (优秀)")
            elif cov_pct >= 60:
                score += 15
                details.append(f"测试覆盖率: {cov_pct}% (良好)")
            elif cov_pct >= 30:
                score += 5
                details.append(f"测试覆盖率: {cov_pct}% (一般)")
            else:
                details.append(f"测试覆盖率: {cov_pct}% (不足)")
        elif cov_data.get("status") == "skipped":
            score += 10
            details.append("测试覆盖率: 跳过检查")
    except (json.JSONDecodeError, Exception):
        pass

    return json.dumps({
        "score": min(score, total),
        "total": total,
        "details": details,
    })
