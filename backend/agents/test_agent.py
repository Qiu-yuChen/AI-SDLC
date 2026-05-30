"""Test Agent Prompt Builder"""


def build_test_prompt(design_doc_path: str, code_dir: str, output_dir: str) -> str:
    """Build the task description for the Test Agent"""

    return f"""
## 任务：根据源代码和设计文档生成单元测试

### 输入
- 概要设计文档：`{design_doc_path}`
- 源代码目录：`{code_dir}`

请使用 `read_file` 和 `list_directory` 工具了解代码结构。

### 输出要求
生成单元测试代码到：`{output_dir}/`

### 测试代码结构
```
{output_dir}/
├── conftest.py            # pytest fixtures（测试数据、mock对象）
├── test_models.py         # 数据模型测试（CSV 读写）
├── test_services.py       # 业务逻辑测试
├── test_routes.py         # API 路由测试（使用 FastAPI TestClient）
└── test_utils.py          # 工具函数测试
```

### 测试要求
1. **框架**：pytest
2. **覆盖率目标**：≥80%
3. **测试类型**：
   - 正常路径测试（Happy Path）
   - 边界值测试（Boundary）
   - 异常处理测试（Error Handling）
   - 参数校验测试（Validation）
4. **Mock 策略**：
   - 使用 pytest fixtures 模拟 CSV 数据
   - FastAPI 路由使用 TestClient 进行集成测试
5. **断言**：每个测试函数至少有 1 个明确断言
6. **可重复执行**：测试不依赖外部服务，可独立运行

### 测试用例清单（基于赛题测试用例）
- ✅ 创建预约 → 检查 CSV 记录 + 科拓系统同步
- ✅ 取消预约 → 检查车位释放 + 状态同步
- ✅ 提前缴费 → 检查缴费记录 + 金额正确
- ✅ 超额预约 → 预约失败提示
- ✅ 园区开关 → 关闭时预约被拒绝
- ✅ 重复预约 → 同一车牌同一天被拒绝
- ✅ 节假日/工作日 → 配额分别生效

### 工作流程（ReAct）
1. 💭 读取设计文档和所有源代码文件
2. 💭 分析每个模块的测试场景
3. 🎬 先用 `write_file` 生成 conftest.py（fictures）
4. 🎬 逐个生成测试文件
5. 👁️ 使用 `syntax_check` 验证测试代码语法
6. 💭 检查是否覆盖了所有关键场景
7. 🎬 如有遗漏，补充测试
"""
