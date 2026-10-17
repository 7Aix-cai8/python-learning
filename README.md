# FocusBoard

FocusBoard 是一个轻量、可测试、无第三方运行时依赖的命令行任务管理器。它使用 SQLite 保存数据，适合个人学习 Python 工程化实践，也适合直接在终端管理日常任务。

## 功能

- 创建、编辑、完成、重新打开和删除任务
- 1 到 5 级优先级（1 最高）
- 标签、描述和 ISO 格式截止日期
- 按状态、标签、关键词和逾期状态筛选
- 统计总任务、待办、已完成和逾期数量
- JSON 导入/导出
- 标准库 unittest 测试和 GitHub Actions CI

## 快速开始

需要 Python 3.10 或更高版本：

    python -m venv .venv
    # Windows: .venv\\Scripts\\activate
    source .venv/bin/activate
    python -m pip install -e .

添加和查看任务：

    focusboard add "设计登录页" --priority 1 --tags design,web --due 2026-11-01
    focusboard add "写项目文档" -d "补充安装和示例" --tags docs
    focusboard list
    focusboard list --status todo --tag design
    focusboard list --search 登录

管理任务：

    focusboard done 1
    focusboard edit 2 --priority 2 --clear-due
    focusboard reopen 1
    focusboard delete 2
    focusboard stats

数据迁移：

    focusboard export backup.json
    focusboard import backup.json

默认数据库位置是 ~/.focusboard/tasks.db，也可以通过 --db path/to/tasks.db 指定路径。

## 开发

运行测试：

    python -m unittest discover -s tests -v

项目采用分层结构：

- models.py：领域模型
- db.py：SQLite schema 和持久化操作
- service.py：输入校验、业务规则、统计与 JSON 传输
- cli.py：参数解析和终端展示

## 许可证

MIT
