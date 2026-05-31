"""
评分报告生成器 — 输出 JSON + Markdown 双格式

输出文件:
  - scoring_report.json : 结构化评分数据，供前端解析
  - scoring_report.md   : 人类可读评分报告
"""
import json
from pathlib import Path
from datetime import datetime, timezone


def generate_reports(batch_dir: Path, report: dict) -> None:
    """
    生成评分报告 JSON 和 Markdown 文件。

    参数:
        batch_dir: 批次目录 (如 workspace/docs/已生成/batch_xxx/)
        report: 完整的评分报告字典
    """

    # ── 1. JSON 报告 ──
    json_path = batch_dir / "scoring_report.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    # ── 2. Markdown 报告 ──
    md_path = batch_dir / "scoring_report.md"

    composite = report.get("composite_score", 0)
    stars_count = int(composite // 20)
    stars_count = max(0, min(5, stars_count))
    stars = "★" * stars_count + "☆" * (5 - stars_count)

    grade_map = {
        (90, 101): "A+ — Production Ready",
        (80, 90): "A — Excellent",
        (70, 80): "B — Good",
        (60, 70): "C — Acceptable",
        (40, 60): "D — Needs Improvement",
        (0, 40): "F — Failed",
    }
    grade = next(
        label for (lo, hi), label in grade_map.items() if lo <= composite < hi
    )

    lines = [
        f"# 🏆 质量评分报告",
        f"",
        f"> **批次**: `{batch_dir.name}`",
        f"> **日期**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"> **方法论**: SWE-bench (ICLR 2024) + RepoZero (NeurIPS 2026)",
        f"",
        f"## 📊 综合评分: **{composite}/100**  {stars}",
        f"",
        f"**等级**: {grade}",
        f"",
        f"### 各维度贡献",
        f"",
        f"| 维度 | 得分 | 权重 | 贡献分数 |",
        f"|------|------|------|----------|",
    ]

    weights = report.get("weights", {})
    for label, data in weights.items():
        w = data.get("weight", 0)
        s = data.get("score", 0)
        c = data.get("contribution", 0)
        lines.append(f"| {label} | {s}/100 | {w*100:.0f}% | {c} |")

    # ── 展开各维度详情 ──
    dimension_configs = [
        ("design_score", "概要设计"),
        ("code_score", "代码生成"),
        ("test_score", "单元测试"),
        ("repozero_score", "RepoZero 验证"),
    ]

    for dim_key, dim_label in dimension_configs:
        dim_data = report.get(dim_key, {})
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")
        lines.append(
            f"## 📐 {dim_label}评分 "
            f"({dim_data.get('total_score', '-')}/100)"
        )

        breakdown = dim_data.get("breakdown", {})
        if not breakdown:
            lines.append(f"")
            lines.append(f"*{dim_data.get('error', '无数据')}*")
            lines.append("")
            continue

        lines.append(f"")
        lines.append(f"| 指标 | 得分 | 满分 | 占比 | 详情 |")
        lines.append(f"|------|------|------|------|------|")

        for metric_name, metric_data in breakdown.items():
            score = metric_data.get("score", 0)
            max_s = metric_data.get("max", 1)
            pct = f"{score/max_s*100:.0f}%"
            detail = metric_data.get("detail", "-")
            if isinstance(detail, str) and len(detail) > 80:
                detail = detail[:77] + "..."
            elif isinstance(detail, dict):
                detail = ", ".join(
                    f"{k}={v}" for k, v in detail.items()
                    if not isinstance(v, (list, dict))
                )
                if len(detail) > 80:
                    detail = detail[:77] + "..."

            lines.append(
                f"| {metric_name} | {score} | {max_s} | {pct} | {detail} |"
            )

        sweb_ref = dim_data.get("sweb_ref", "")
        repozero_ref = dim_data.get("repozero_ref", "")
        ref = sweb_ref or repozero_ref
        if ref:
            lines.append(f"")
            lines.append(f"> 📚 *{ref}*")
            lines.append("")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*本报告由 AI-SDLC 评分模块自动生成。*")
    lines.append("")
    lines.append("*评分方法参考：*")
    lines.append(
        "* • SWE-bench (Jimenez et al., ICLR 2024) — "
        "F2P/P2P 测试验证 + radon 软件工程指标*"
    )
    lines.append(
        "* • RepoZero (Zhang et al., NeurIPS 2026) — "
        "黑盒输出验证 + API 规格忠实度*"
    )

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"[Scoring] 报告已生成: {json_path.name}, {md_path.name}")
