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
├── conftest.py            # pytest fixtures（临时目录、测试客户端）
├── test_services.py       # 业务逻辑和 CSV 读写测试
└── test_routes.py         # API 路由 smoke 测试（FastAPI TestClient）
```

### 测试要求
1. **框架**：pytest
2. **覆盖率目标**：优先覆盖核心增删改查流程
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

### 测试用例生成原则
- 只根据概要设计和源代码中的真实实体、函数、路由来写测试。
- 不要套用停车、预约、支付等旧赛题用例，除非源代码明确包含这些业务。
- 如果源码结构复杂，先写可运行的 smoke tests：模块可导入、核心 service 可调用、主要 API 返回预期状态码。

### 工作流程（ReAct）
1. 💭 读取设计文档和所有源代码文件
2. 💭 分析每个模块的测试场景
3. 🎬 先用 `write_file` 生成 conftest.py
4. 🎬 再用 `write_file` 生成 test_services.py 和 test_routes.py
5. 👁️ 使用 `syntax_check` 验证测试代码语法
6. 👁️ 使用 `list_directory` 确认测试文件已生成

### 小模型执行约束
- 最多生成 3 个测试文件，避免过度规划。
- 每个文件只调用一次 `write_file`；不要重复完全相同的 Action Input。
- 如果不确定具体函数签名，写保守的导入 smoke test 和 TestClient 基础路由测试，保证语法正确。
"""
