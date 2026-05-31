# Quick syntax check of all files
import py_compile
import sys

files = [
    r"E:\all courses\2026_1\AI-SDLC\workspace\docs\已生成\batch_20260531_043341_1303f7\单元测试\conftest.py",
    r"E:\all courses\2026_1\AI-SDLC\workspace\docs\已生成\batch_20260531_043341_1303f7\单元测试\test_models.py",
    r"E:\all courses\2026_1\AI-SDLC\workspace\docs\已生成\batch_20260531_043341_1303f7\单元测试\test_utils.py",
    r"E:\all courses\2026_1\AI-SDLC\workspace\docs\已生成\batch_20260531_043341_1303f7\单元测试\test_services.py",
    r"E:\all courses\2026_1\AI-SDLC\workspace\docs\已生成\batch_20260531_043341_1303f7\单元测试\test_routes.py",
]

for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"✅ {f} - OK")
    except py_compile.PyCompileError as e:
        print(f"❌ {f} - {e}")
