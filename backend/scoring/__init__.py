"""
评分模块 — SWE-bench + RepoZero 双基准对齐的多维度质量评估

参考:
  - Jimenez et al., SWE-bench: Can Language Models Resolve Real-World GitHub Issues?, ICLR 2024
  - Zhang et al., RepoZero: Can LLMs Generate a Code Repository from Scratch?, NeurIPS 2026
"""
from .design_scorer import DesignScorer
from .code_scorer import CodeScorer
from .test_scorer import TestScorer
from .repozero_scorer import RepoZeroScorer
from .report_generator import generate_reports
