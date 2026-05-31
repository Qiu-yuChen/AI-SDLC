# Simple check - just print file content
print("Files exist")
import os
files = [
    r"E:\all courses\2026_1\AI-SDLC\workspace\docs\已生成\batch_20260531_043341_1303f7\单元测试\conftest.py",
    r"E:\all courses\2026_1\AI-SDLC\workspace\docs\已生成\batch_20260531_043341_1303f7\单元测试\test_models.py",
    r"E:\all courses\2026_1\AI-SDLC\workspace\docs\已生成\batch_20260531_043341_1303f7\单元测试\test_utils.py",
    r"E:\all courses\2026_1\AI-SDLC\workspace\docs\已生成\batch_20260531_043341_1303f7\单元测试\test_services.py",
    r"E:\all courses\2026_1\AI-SDLC\workspace\docs\已生成\batch_20260531_043341_1303f7\单元测试\test_routes.py",
]
for f in files:
    if os.path.exists(f):
        size = os.path.getsize(f)
        print(f"✅ {os.path.basename(f)} - {size} bytes")
    else:
        print(f"❌ {f} - NOT FOUND")
