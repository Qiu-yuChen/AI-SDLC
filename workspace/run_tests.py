import subprocess
import sys

# 安装 pytest 和 pytest-cov
subprocess.run([sys.executable, "-m", "pip", "install", "pytest", "pytest-cov", "httpx", "fastapi", "pydantic", "uvicorn"], capture_output=True)

# 运行测试并生成覆盖率报告
result = subprocess.run(
    [sys.executable, "-m", "pytest", 
     "/home/cqy/hackathon/ai-sdlc/workspace/docs/已生成/batch_20260531_201339_bc2499/单元测试/",
     "-v", 
     "--cov=/home/cqy/hackathon/ai-sdlc/workspace/docs/已生成/batch_20260531_201339_bc2499/代码生成/app.py",
     "--cov-report=term-missing",
     "--tb=short"],
    capture_output=True, text=True
)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
print("Return code:", result.returncode)
