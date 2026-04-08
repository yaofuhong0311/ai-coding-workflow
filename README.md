# AI Coding Workflow

一套让 AI Coding Agent 不再重复犯错、且无法绕过质量底线的工程方法论。

## 适用范围

本工具链专为 **Python + Claude Code** 开发场景设计。其他语言或其他 AI Coding Agent 可参考思路，但脚本和配置细节需自行适配。

## 快速开始

**前提**：Claude Code 已安装，Python 项目。

```bash
# 1. 克隆本仓库
git clone https://github.com/yaofuhong0311/ai-coding-workflow.git

# 2. 复制全局规则模板
cp templates/CLAUDE.md.template ~/.claude/CLAUDE.md

# 3. 复制 hook 脚本
mkdir -p ~/.claude/hooks
cp hooks/python-quality-gate.sh ~/.claude/hooks/
cp hooks/find-plan.sh ~/.claude/hooks/
cp hooks/pre-tool-use-write.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh

# 4. 复制 settings.json 模板（如已有则手动合并 hooks 部分）
cp templates/settings.json.template ~/.claude/settings.json
```

**可选增强**：
- 安装 [ruflo MCP](https://github.com/ruvnet/ruflo) 用于自动记录和查询编码经验
- 配置 `distill.py` 定时任务用于经验蒸馏（见 docs/self-evolution.md）

## 问题

AI Coding Agent（Claude Code / Cursor / Copilot）有两个结构性缺陷：

**1. 没有记忆。** 每次新 session 都是全新开始。上次踩的坑、团队的约定、某个 API 的 workaround——全部忘干净，下次重新踩一遍。

**2. 规则靠自觉。** 你可以在 prompt 里写"不要用 bare except"、"先读再写"，但 Agent 在复杂任务中会忘记遵守。规则写了等于没写。

## 核心思路

用三层机制解决这两个问题：

```
第一层：软约束 ——— 写在 CLAUDE.md 里的行为规则，Agent 自觉遵守
第二层：硬执行 ——— python-quality-gate.sh PostToolUse hook，每次写文件自动扫描，违规强制修复
第三层：后置记录 ——— ruflo + .learnings 采集经验，蒸馏后写回 CLAUDE.md
```

**软约束**解决的是意识问题：告诉 Agent "先读再写、不要编造、遵循现有模式"。覆盖面广，但 Agent 可能忘。

**硬执行**解决的是遗忘问题：Agent 写了问题代码，不管它记不记得规则，python-quality-gate.sh 都会在文件保存后立即扫到，把违规信息塞回 Agent 上下文，Agent 被迫看到并修复。同理，UserPromptSubmit hook 检测到 plan.md 有多个独立任务时，强制注入 Swarm 执行指令——Agent 被迫走并行模式，不依赖自觉。机械触发，不可绕过。

**后置记录**解决的是积累问题：这次踩的坑记下来，蒸馏成规则，下次 session 自动加载。Agent 从"每次重新开始"变成"站在之前的经验上继续"。

三层形成闭环：

```
编码中发现新问题 → 记录 → 蒸馏成新规则 → 下次 session 加载
                                          ↓
                              其中可机械判定的 → 变成 python-quality-gate.sh 规则
                              需要判断力的     → 留在 CLAUDE.md 软约束
```

## 工作流

```
brainstorm → plan → execute (Swarm 并行) → distill → 下次 session 自动加载
```

**brainstorm**：先和 Agent 讨论需求、发散方案、对齐方向。不让 Agent 直接开写——它会按自己的理解抢跑，做完才发现方向错了。

**plan**：写结构化实施计划，保存到当前项目 `docs/plans/`（`find-plan.sh` 优先从项目目录查找，回退到 `~/coding/.plans/`）。plan.md 建议包含 `## 核心约束` 章节，PreToolUse hook 会自动提取注入上下文。

**execute**：按 plan 执行。如果 plan 拆出了 2 个以上互不依赖的任务，自动进入 **Swarm Agent 并行模式**：

```
Queen（主 Claude 进程）读取 plan.md
    ↓
拆解独立任务，分析依赖关系
    ↓
Ruflo hive-mind 注册 Worker（状态追踪 + 共享记忆）
    ↓
为每个 Worker 启动一个 CC 内置子 Agent（真·并行子进程）
    ↓
所有子 Agent 并行执行 → 结果返回 Queen → 汇总
```

单任务或有强依赖的任务仍然串行执行。三层防御在串行和并行模式下都生效：
- CLAUDE.md 规则约束行为模式（先读再写、不编造）
- python-quality-gate.sh hook 拦截 Python 问题代码（每次文件保存自动触发）
- ruflo 自动记录经验，.learnings 捕获错误和纠正

**distill**：每天自动汇总所有项目的经验，去重、分类、原子化，人工确认后写入 CLAUDE.md。

## 三层防御详解

### 第一层：软约束（反幻觉规则）

写在 CLAUDE.md 最前面的三条强制规则：

- **读优先于写**：修改文件前先 read，调用函数前先 grep。打断"凭记忆写代码"的模式。
- **不要编造**：不确定就查源码，不猜。
- **基于现有代码扩展**：先看同类模块怎么写的，再写新的。

> 设计哲学：与其让 AI 变得更"聪明"，不如让它变得更"谨慎"。大部分 coding 错误不是能力不足，而是太自信。

### 第二层：硬执行（python-quality-gate.sh 机械化检查）

Agent 每次写/编辑 `.py` 文件后，PostToolUse hook 同步触发 `~/.claude/hooks/python-quality-gate.sh`。违规信息注入 Agent 上下文，Agent 修复后才能继续。

**机制说明：** 输出驱动，不依赖 exit code。脚本有 stdout 输出 → AI 收到 ⚠️ 自动修复；无输出 = 通过。

### 第三层：后置记录 + 蒸馏

**采集**：ruflo（MCP 工具）通过 hooks 自动记录编码过程中的经验；.learnings/ 文件捕获错误、纠正、最佳实践。

**蒸馏**：`distill.py` 每天汇总所有项目的经验，执行：
1. 去重（相同 key 保留最丰富的版本）
2. 分类（架构/算法/踩坑/性能/纠正/其他）
3. 原子化（复合经验拆成独立知识点）
4. 打标签（FACT 📌 / RULE ⚙️ / GOTCHA ⚠️）
5. 人工确认后写入 CLAUDE.md

**参考**：三层记忆模型借鉴 PlugMem 论文（arXiv:2603.03296）——Episodic（原始经验）→ Semantic（蒸馏提炼）→ Procedural（内化为规则）。

## Swarm Agent 并行执行

**注意**：Swarm 模式为近期新增功能，建议在熟悉基础工作流后再使用。

当 plan.md 包含多个互不依赖的任务时，execute 阶段自动切换为并行模式。

### 架构

```
                Queen（主 Claude 进程）
                ├── 读取 plan.md，拆解任务
                ├── Ruflo hive-mind：注册 Worker（状态追踪）
                │
                └── 同时调用 N 个 CC 内置 Agent（并行子进程）
                     ├── Worker-1 → CC Agent 子进程 1（独立 token、独立 tool use）
                     ├── Worker-2 → CC Agent 子进程 2
                     └── Worker-N → CC Agent 子进程 N
                           ↓
                     并行执行 → 结果返回 Queen → Ruflo 更新状态
```

**两层职责分离：**

| 层 | 工具 | 做什么 |
|----|------|--------|
| 协调层 | Ruflo hive-mind | Worker 注册、任务分配记录、共享记忆、claims 看板 |
| 执行层 | CC 内置 Agent | 真正的并行子进程，每个 Agent 独立读写文件、执行命令 |

Ruflo 是协调和状态管理工具，不启动进程。CC 内置 Agent 是实际的并行执行引擎。两者配合使用。

### 并行规则

- **无依赖的任务**：并行执行（如 routes.py 和 schemas.py 可以同时写）
- **有依赖的任务**：串行执行（如先写 models.py，再写依赖它的 services.py）
- **同一文件**：禁止并行修改，通过 Ruflo claims 系统分配文件归属
- **触发条件**：plan.md 中有 2 个以上独立任务时自动触发，不需要人工指定

### 观察进度

执行过程中，所有子 Agent 在同一个终端窗口内并行显示：

```
● 4 agents running...
├─ Worker-1: 实现 routes.py    · running
├─ Worker-2: 实现 schemas.py   · running
├─ Worker-3: 实现 services.py  · running
└─ Worker-4: 写测试            · running
```

随时查看 Ruflo claims 看板获取任务分配和完成状态。

## 效果

对日常 coding 的实际影响：

| 环节 | 之前 | 之后 |
|------|------|------|
| Agent 开始写代码 | 可能凭记忆瞎写 | 先读现有代码，遵循已有模式 |
| Agent 写出 `except: pass` | 你 review 时才发现（或漏掉） | 文件保存后 1 秒内被拦截，自动修复 |
| 上次踩过的坑 | 下次重新踩 | 蒸馏后自动加载，不再重犯 |
| 你的 review 负担 | 检查所有问题 | 低级错误已拦干净，只看设计和逻辑 |

## 文档

| 文档 | 内容 |
|------|------|
| [docs/architecture.md](docs/architecture.md) | 工具链详解：四个工具各自的角色 |
| [docs/anti-hallucination.md](docs/anti-hallucination.md) | 三层防御体系设计 |
| [docs/self-evolution.md](docs/self-evolution.md) | 蒸馏系统设计与演进方向 |
| [diagrams/workflow.md](diagrams/workflow.md) | 流程图（Mermaid） |
| [examples/learnings-format.md](examples/learnings-format.md) | .learnings/ 记录格式规范 |
| [templates/CLAUDE.md.template](templates/CLAUDE.md.template) | CLAUDE.md 全局规则模板 |

## 技术栈

> 本工具链专为 **Python + Claude Code** 开发场景设计。

- **Claude Code** — AI Coding Agent，内置 Agent 工具支持并行子进程
- **ruff** — Python lint 工具，python-quality-gate.sh 的核心检查引擎
- **ruflo** — MCP 工具，提供 memory 记录、hive-mind 协调、claims 任务追踪
- **distill.py** — 经验蒸馏脚本（Python 3.10+，零依赖）
- **OpenClaw** — 定时任务 + 飞书通知推送 + 蒸馏审核流程

## License

MIT
