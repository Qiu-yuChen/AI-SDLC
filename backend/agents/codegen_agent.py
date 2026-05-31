"""CodeGen Agent Prompt Builder"""


def build_codegen_prompt(design_doc_path: str, output_dir: str) -> str:
    """Build the task description for the CodeGen Agent"""

    return f"""
## 任务：根据概要设计文档生成源代码

### 输入
概要设计文档路径：`{design_doc_path}`

请先使用 `read_file` 工具读取概要设计文档。

### 输出要求
生成完整的项目源代码到：`{output_dir}/`

### 代码结构
```
{output_dir}/
├── app.py                 # FastAPI 主入口
├── models.py              # 数据模型（CSV 读写封装）
├── routes.py              # API 路由
├── services.py            # 业务逻辑层
├── utils.py               # 工具函数
├── data/                  # CSV 数据文件目录
│   ├── parks.csv          # 园区表
│   ├── reservations.csv   # 预约记录表
│   └── payments.csv       # 缴费记录表
├── static/
│   └── index.html         # 前端页面
└── requirements.txt       # 依赖清单
```

### 代码要求
1. **语法正确**：生成后使用 `syntax_check` 工具验证每个文件
2. **类型注解**：所有函数参数和返回值使用 Type Hints
3. **错误处理**：每个 API 端点有明确的 try/except
4. **CSV 操作**：封装 CSV 读写为类，支持增删改查
5. **注释清晰**：每个模块、类和函数有 docstring
6. **PEP 8 规范**：使用 `format_code_file` 格式化代码

### 技术约束
- 数据库：使用 CSV 文件（赛题要求），不使用 SQLite/MySQL
- 前端：单文件 HTML + 原生 JavaScript（简化部署）
- 后端：FastAPI + uvicorn
- 认证：简单的 session/token（可模拟）

### 工作流程（ReAct）
1. 💭 读取概要设计文档，理解所有模块
2. 💭 规划文件生成顺序（数据模型 → 服务层 → 路由 → 主入口 → 前端）
3. 🎬 逐个使用 `write_file` 生成文件
4. 👁️ 使用 `syntax_check` 验证语法
5. 💭 如果有语法错误，分析并修复
6. 🎬 使用 `format_code_file` 格式化代码
7. 👁️ 使用 `list_directory` 确认所有文件已生成
"""
