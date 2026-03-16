# ai-coding-workflow

让 AI Coding Agent 从错误中学习的经验蒸馏系统。

```bash
# 扫描所有项目的编码经验，生成蒸馏预览
python distill.py --dry-run
```

```
🔍 扫描 ~/coding ...
  [ruflo] project_a: 10 条
  [ruflo] project_b: 3 条
  [ruflo] project_c: 19 条

📊 合并前：32 条
📊 去重后：32 条

### 架构设计
- 📌[project_a][FACT] LangGraph 支持从同一 node 多条 add_edge() 实现并行 fan-out
- ⚠️[project_c][GOTCHA] 第三方 API 的 usage 字段常为 null，需要三级 fallback 提取
- ⚙️[project_c][RULE] 服务层只做 flush 不做 commit，由 session 管理器统一管理事务

### Bug 与踩坑
- ⚠️[project_a][GOTCHA] pytest 会收集所有 test_* 函数，即使是被 import 的，需要 __test__=False
- ⚠️[project_c][GOTCHA] alembic autogenerate 检测大量无关变更，需手动清理 migration 文件
```

蒸馏后的经验写入 `CLAUDE.md`，下次 Claude Code session 自动加载 → Agent 不再重复犯同样的错。

## 解决什么问题

AI Coding Agent（Claude Code / Cursor / Copilot）每次新 session 都是全新开始：

- 上次踩的坑 → 忘了，再踩一遍
- 团队的编码约定 → 不知道，按自己的来
- 某个 API 的 workaround → 不记得，重新探索

**本工具把每次编码积累的经验自动蒸馏，写入全局规则文件，让 Agent 具备跨 session 的长期记忆。**

## 快速开始

```bash
git clone https://github.com/yaofuhong0311/ai-coding-workflow.git
cd ai-coding-workflow

# 1. 配置项目扫描路径（默认 ~/coding）
vim config.yaml

# 2. 预览蒸馏结果
python distill.py --dry-run

# 3. 确认后写入 CLAUDE.md
python distill.py --commit
```

### 配置

```yaml
# config.yaml
coding_root: ~/coding          # 项目根目录
claude_md: ~/.claude/CLAUDE.md  # CC 全局规则文件
notify:
  channel: feishu               # 通知渠道（feishu/slack/none）
  target: YOUR_ID               # 接收通知的用户 ID
```

## 工作原理

```
编码中                    每天 19:00              下次 session
┌──────────┐            ┌──────────┐           ┌──────────┐
│ ruflo DB │──┐         │          │           │          │
│ (SQLite) │  ├──汇总──→│ distill  │──确认──→  │CLAUDE.md │──自动加载→ Agent 行为改变
│.learnings│──┘    去重  │   .py    │  写入     │          │
│ (*.md)   │      分类   │          │           │          │
└──────────┘     原子化  └──────────┘           └──────────┘
```

**三步记忆转化：**

| 层级 | 对应 | 来源 | 持久性 |
|------|------|------|--------|
| Episodic（情景记忆） | ruflo DB + .learnings/ | 每次编码自动采集 | 项目级 |
| Semantic（语义记忆） | 蒸馏产出 | distill.py 汇总提炼 | 跨项目 |
| Procedural（程序记忆） | CLAUDE.md 规则 | 确认后写入 | 全局永久 |

## 蒸馏管道

```python
# distill.py 核心流程
all_memories = collect_all()       # 扫描所有项目的 ruflo DB + .learnings/
deduped = deduplicate(all_memories) # 基于 key 去重
categories = categorize(deduped)    # 关键词匹配分 6 类
block = format_block(categories)    # 原子化拆分 + 打标签(FACT/RULE/GOTCHA)
```

**原子化拆分示例：**
```
输入: "1) 服务层只做 flush 不做 commit；2) 跨模块用 lazy import 避免循环依赖"

输出:
  ⚙️[RULE] 服务层只做 flush 不做 commit
  ⚙️[RULE] 跨模块用 lazy import 避免循环依赖
```

**自动打标签规则：**
- `FACT` 📌 — 事实（"LangGraph 支持并行 fan-out"）
- `RULE` ⚙️ — 规则（"必须先 read 再 write"）
- `GOTCHA` ⚠️ — 踩坑（"pytest 会收集 import 的 test_* 函数"）

## 反幻觉规则

写入 CLAUDE.md 最前面的三条强制规则，预防 AI 编码幻觉：

```markdown
### 读优先于写
修改任何文件前，先 read 确认当前内容。
调用任何函数前，先 grep 确认它真实存在。

### 不要编造
不确定时查源码，不猜。

### 基于现有代码扩展
先读同类模块的实现，遵循已有模式。
```

> 反幻觉 = 前置过滤器（预防），ruflo = 后置安全网（兜底）。

## 完整工作流

```
superpowers 脑爆 → superpowers plan → Claude Code 执行（ruflo 自动挂载）
         ↑                                    ↓
         └──── CLAUDE.md 自动加载 ←── distill.py 蒸馏 ←──┘
```

1. **脑爆**：讨论需求，发散方案
2. **计划**：写结构化 plan，确认后动手
3. **执行**：CC 按 plan 编码，ruflo 自动记录经验
4. **蒸馏**：cron 每天汇总 → 人工确认 → 写入 CLAUDE.md
5. **加载**：下次 session 自动生效

详见 [docs/architecture.md](docs/architecture.md)

## 文件结构

```
├── distill.py              # 蒸馏脚本（可直接运行）
├── config.yaml             # 配置文件
├── templates/
│   └── CLAUDE.md.template  # 全局规则模板
├── docs/
│   ├── architecture.md     # 工具链详解
│   ├── self-evolution.md   # 蒸馏系统设计
│   └── anti-hallucination.md
└── examples/
    └── learnings-format.md # .learnings/ 记录格式
```

## 技术栈

- Python 3.10+（标准库，零依赖）
- Claude Code — AI Coding Agent
- ruflo — MCP 工具，自动记录编码经验
- OpenClaw — 定时任务 + 通知推送（可选）

## License

MIT
