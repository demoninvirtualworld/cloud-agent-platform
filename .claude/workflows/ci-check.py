# 示例工作流：代码审查 + 测试验证
# 用法: DScode 中使用 run_workflow(name="ci-check")

steps = [
    {
        "agent": "general-purpose",
        "prompt": "对当前项目进行代码审查，检查 tools/ 目录下所有 Python 文件的代码质量、潜在问题和改进建议。输出简洁的审查报告。",
        "depends_on": [],
    },
    {
        "agent": "general-purpose",
        "prompt": "运行 pytest 测试套件，分析测试结果。如果全部通过则输出通过确认，如果有失败则分析失败原因。",
        "depends_on": [],
    },
    {
        "agent": "general-purpose",
        "prompt": "综合前两个步骤的结果，生成一份简洁的 CI 检查总结报告。包含：代码审查结果摘要、测试通过/失败统计、总体评估（通过/需改进）。",
        "depends_on": [0, 1],
    },
]
