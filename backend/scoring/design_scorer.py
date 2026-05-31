"""
概要设计文档评分器

评估维度（6项）：
  - 结构完整性 (30分)：是否覆盖7大核心章节
  - Mermaid图表  (15分)：架构图/序列图数量
  - API端点定义  (15分)：REST端点是否明确定义
  - 数据模型定义 (15分)：CSV表字段是否完整
  - 文档长度合理 (10分)：300-1200行为黄金区间
  - 技术选型说明 (15分)：是否明确了技术栈
"""
import re
from pathlib import Path
from typing import Dict, Tuple, List


class DesignScorer:
    """概要设计文档质量评分器"""

    def __init__(self, design_dir: Path):
        self.design_dir = Path(design_dir)

    def _read(self) -> str:
        """读取设计文档内容"""
        md_files = sorted(self.design_dir.rglob("*.md"))
        if not md_files:
            return ""
        return md_files[0].read_text(encoding="utf-8")

    def _hits(self, text: str, keywords: List[str]) -> int:
        """统计命中的关键词数量"""
        return sum(1 for kw in keywords if kw in text)

    # ── 指标1: 结构完整性 (30分) ──

    def _structure(self, text: str) -> Tuple[float, str]:
        """
        检查是否包含软件工程规范的7大核心章节。
        每缺失一章扣约4.3分。
        """
        sections = [
            "系统概述",
            "架构设计",
            "模块划分",
            "API",
            "数据模型",
            "流程",
            "非功能性",
        ]
        found = self._hits(text, sections)
        missing = [s for s in sections if s not in text]
        score = round(found / len(sections) * 30, 1)
        msg = f"命中 {found}/{len(sections)} 章节"
        if missing:
            msg += f" | 缺失: {', '.join(missing[:3])}"
        return score, msg

    # ── 指标2: Mermaid 图表 (15分) ──

    def _mermaid(self, text: str) -> Tuple[float, str]:
        """
        统计 Mermaid 代码块数量。
        架构图 + 序列图 = 2个满分。
        """
        blocks = re.findall(r'```mermaid\n(.*?)```', text, re.DOTALL)
        count = len(blocks)
        score = min(15.0, count * 7.5)
        return score, f"{count} 个 Mermaid 图表"

    # ── 指标3: API 端点定义 (15分) ──

    def _api(self, text: str) -> Tuple[float, str]:
        """
        统计 REST API 端点定义数量。
        匹配 GET/POST/PUT/DELETE/PATCH + 路径的写法。
        """
        endpoints = re.findall(r'(GET|POST|PUT|DELETE|PATCH)\s+[/\w]', text)
        count = len(endpoints)
        score = min(15.0, count * 3.0)
        return score, f"{count} 个 API 端点"

    # ── 指标4: 数据模型定义 (15分) ──

    def _data(self, text: str) -> Tuple[float, str]:
        """
        统计 Markdown 表格中的字段列数。
        匹配 | field_name | 模式。
        """
        fields = re.findall(r'\|\s*[\w_]+\s*\|', text)
        count = len(fields)
        score = min(15.0, count / 2)
        return min(score, 15.0), f"约 {count} 个字段定义"

    # ── 指标5: 文档长度合理性 (10分) ──

    def _length(self, text: str) -> Tuple[float, str]:
        """
        300-1200行最佳：既有足够细节，又不冗余。
        过短 (<200) 说明简略，过长 (>1500) 说明可能堆砌。
        """
        lines = len(text.splitlines())
        if 300 <= lines <= 1200:
            score, level = 10.0, "理想"
        elif 200 <= lines <= 1500:
            score, level = 7.0, "可接受"
        elif lines < 200:
            score, level = 4.0, "过短"
        else:
            score, level = 4.0, "过长"
        return score, f"{lines} 行 ({level})"

    # ── 指标6: 技术选型说明 (15分) ──

    def _tech(self, text: str) -> Tuple[float, str]:
        """
        检查是否明确了核心技术栈。
        6个核心关键词全部命中 = 满分。
        """
        keywords = ["FastAPI", "Python", "CSV", "REST", "HTML", "Pydantic"]
        found = self._hits(text, keywords)
        score = round(found / len(keywords) * 15, 1)
        missing_kw = [kw for kw in keywords if kw not in text]
        msg = f"命中 {found}/{len(keywords)} 技术关键词"
        if missing_kw:
            msg += f" | 缺失: {', '.join(missing_kw[:3])}"
        return score, msg

    # ── 综合 ──

    def evaluate(self) -> Dict:
        """执行全维度评分，返回结构化结果"""
        text = self._read()

        if not text:
            return {
                "total_score": 0.0,
                "max_score": 100,
                "error": "未找到概要设计文档 (.md)",
                "breakdown": {},
            }

        s1, m1 = self._structure(text)
        s2, m2 = self._mermaid(text)
        s3, m3 = self._api(text)
        s4, m4 = self._data(text)
        s5, m5 = self._length(text)
        s6, m6 = self._tech(text)

        total = round(s1 + s2 + s3 + s4 + s5 + s6, 1)

        return {
            "total_score": total,
            "max_score": 100,
            "breakdown": {
                "structure":   {"score": s1, "max": 30, "detail": m1},
                "mermaid":     {"score": s2, "max": 15, "detail": m2},
                "api_def":     {"score": s3, "max": 15, "detail": m3},
                "data_model":  {"score": s4, "max": 15, "detail": m4},
                "doc_length":  {"score": s5, "max": 10, "detail": m5},
                "tech_stack":  {"score": s6, "max": 15, "detail": m6},
            },
        }
