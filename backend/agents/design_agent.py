"""Design Agent Prompt Builder"""


def build_design_prompt(spec_path: str, output_dir: str, examples: str = "") -> str:
    """Build the task description for the Design Agent

    Args:
        spec_path: 规格说明书路径
        output_dir: 输出目录
        examples: 历史参考范例（来自 skill_store），可为空
    """

    example_section = ""
    if examples:
        example_section = f"""
{examples}

请参考以上范例的结构、深度和格式来生成新的设计文档。
"""

    return f"""
## 任务：生成概要设计文档

### 输入
产品规格说明书路径：`{spec_path}`

请先使用 `read_file` 工具读取完整的产品规格说明书。
{example_section}
### 输出要求
生成一份完整的概要设计文档，保存为：
`{output_dir}/概要设计文档.md`

### 概要设计文档必须包含以下章节：

1. **系统概述**
   - 项目背景与目标
   - 系统范围与边界
   - 用户角色定义

2. **系统架构设计**
   - 整体架构图（使用 Mermaid 语法绘制）
   - 分层说明（表示层、业务逻辑层、数据访问层）
   - 技术选型：Python FastAPI 后端 + HTML/JS 前端 + CSV 数据库

3. **模块划分**
   - 每个模块的功能描述和职责
   - 模块间的依赖关系
   - 模块接口定义

4. **API 接口设计**
   - 列出所有 REST API 端点
   - 每个端点的：方法、路径、请求参数、响应格式
   - 示例请求/响应

5. **数据模型设计**
   - CSV 表结构定义（赛题要求用 CSV 模拟数据库）
   - 每个表的字段名、类型、约束
   - 表间关系说明
   - 示例数据

6. **关键业务流程**
   - 核心业务流程图（Mermaid sequence diagram）
   - 异常处理流程

7. **非功能性需求**
   - 性能指标
   - 安全策略
   - 错误处理策略

### 工作流程（ReAct）
1. 💭 先读取规格说明书
2. 💭 分析需求，确定架构
3. 🎬 调用 `write_file` 写入设计文档
4. 👁️ 使用 `validate_design_completeness` 检查文档完整性
5. 💭 如果检查不通过，补充缺失内容
6. 🎬 最终保存完整的设计文档

### 约束
- 文档语言：中文
- 代码和数据都在 CSV 文件中模拟，不使用 SQL/NoSQL
- API 使用 RESTful 风格
- 架构图使用 Mermaid 语法
"""
