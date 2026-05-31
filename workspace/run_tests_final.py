#!/usr/bin/env python3
"""运行单元测试并检查覆盖率"""
import subprocess
import sys
import os

os.chdir("/home/cqy/hackathon/ai-sdlc/workspace")

# 运行测试
result = subprocess.run(
    [
        sys.executable, "-m", "pytest",
        "/home/cqy/hackathon/ai-sdlc/workspace/docs/已生成/batch_20260531_201339_bc2499/单元测试/",
        "-v",
        "--cov=/home/cqy/hackathon/ai-sdlc/workspace/docs/已生成/batch_20260531_201339_bc2499/代码生成/app.py",
        "--cov-report=term-missing",
        "--tb=short",
    ],
    capture_output=True,
    text=True,
    timeout=120
)
print("STDOUT:")
print(result.stdout)
print("STDERR:")
print(result.stderr)
print("Return code:", result.returncode)
