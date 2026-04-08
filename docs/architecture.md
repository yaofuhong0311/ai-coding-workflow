# 工具链架构详解

## 五个角色

### Claude Code (CC) — 执行者
Claude Code 是实际写代码的 Agent。它能读写文件、执行命令、搜索代码库。

**内置 Agent 工具**：CC 可以在同一条回复中启动多个子进程（子 Agent），每个子进程独立执行、独立消耗 token。这是 Swarm 并行执行的底层能力。

**但它有个致命缺陷：没有跨 session 记忆。** 每次新对话，之前学到的一切全部丢失。

### python-quality-gate.sh — 执法者

`~/.claude/hooks/python-quality-gate.sh` 通过 PostToolUse hook 挂载在 CC 上：

- CC 每次写/编辑 `.py` 文件后，hook **同步**触发脚本
- 违规信息注入 CC 上下文，CC 被迫看到并修复
- 当前检查：ruff lint + hardcode 端口 + 文件超 500 行
- 脚本可持续扩展，加新检查段即永久生效

**机制**：输出驱动。脚本有 stdout 输出 → AI 自动修复；无输出 = 通过。CC 无法绕过。

### ruflo (claude-flow) — 记录者 + 协调者
ruflo 是一个 MCP（Model Context Protocol）工具，以 hooks 形式挂载在 CC 上，承担两个职责：

**记录**：
- 所有 coding 操作自动触发 ruflo hooks
- 经验存储在 SQLite 数据库（`.swarm/memory.db`）
- 支持 `memory_search` 查询历史经验、`memory_store` 存储新经验

**协调**（Swarm 模式下）：
- `hive-mind`：注册 Worker 身份、共享记忆（shared memory）
- `claims`：任务认领和文件归属管理，防止多 Agent 同时修改同一文件
- 看板视图：展示每个 Worker 的任务分配和完成状态

**重要区分**：ruflo 是状态管理和协调工具，不启动进程。真正的并行执行靠 CC 内置 Agent 子进程。

### OpenClaw — 编排者
OpenClaw 是 AI Agent 运行时，在本工作流中承担：

- **定时任务**：每天 19:00 触发蒸馏脚本
- **通知渠道**：通过飞书推送蒸馏预览
- **审核流程**：接收用户确认，触发写入
- **日常助理**：面试准备、信息推送等

## 四步工作流

```
脑爆 → 计划 → 执行（串行 or Swarm 并行）→ 蒸馏
```

**第一步：脑爆**
- 用脑爆模型讨论需求
- 发散思路，探索方案空间
- 产出：方向性结论 + 技术选型

**第二步：计划**
- 写结构化实施计划，保存到当前项目 `docs/plans/`
- `find-plan.sh` 优先从 `$PWD/docs/plans/` 查找，回退到 `~/coding/.plans/`
- plan.md 建议包含 `## 核心约束` 章节，PreToolUse hook 自动提取注入上下文
- 用户确认后再动手
- 产出：plan.md

**第三步：执行**

CC 读取 plan.md 后，根据任务依赖关系自动选择执行模式：

| 条件 | 模式 | 说明 |
|------|------|------|
| 任务 < 2 或有强依赖 | 串行执行 | 主进程逐步实现 |
| 2 个以上独立任务 | Swarm 并行 | Queen 分发给多个子 Agent 并行执行 |

**Swarm 并行执行流程：**

1. Queen（主 Claude 进程）读 plan.md，拆出独立任务
2. Ruflo `hive-mind_init` + `hive-mind_spawn` 注册 Worker
3. Ruflo `hive-mind_memory set` 记录任务分配
4. Queen 在同一条回复中同时调用 N 个 CC 内置 Agent 工具
5. N 个子 Agent 并行执行（每个是独立子进程，有独立 token 消耗）
6. 结果返回 Queen，更新 Ruflo claims 状态
7. Queen 汇总结果

两层职责分离：
- **Ruflo hive-mind**（协调层）：Worker 注册、共享记忆、claims 防冲突、看板展示
- **CC 内置 Agent**（执行层）：真正的并行子进程，独立读写文件和执行命令

**并行安全规则：**
- 不同 Worker 分配不同文件范围，禁止同时修改同一文件
- 涉及同一文件的任务串行执行
- 通过 Ruflo claims 系统追踪文件归属

所有模式下，三层防御同时生效：
- python-quality-gate.sh hook 实时拦截 Python 问题代码（同步，不可绕过）
- ruflo 自动记录经验
- 学习记录自动写入 `.learnings/`
- 产出：代码 + 经验数据

**第四步：蒸馏**
- `distill.py` 汇总所有项目的经验
- OpenClaw 定时触发 + 飞书推送预览
- 人工确认后写入 CLAUDE.md
- 产出：更新后的 CLAUDE.md

**代码审查（可选）**
- 日常：superpowers code-reviewer（快速单 Agent 审查）
- 合并前：`/fagan-review`（双 Agent 并行审查——结构检查 + 语义检查，合并去重出报告）

## Hooks 配置示例

以下是 `~/.claude/settings.json` 中与本工作流相关的 hooks 配置：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "command": "bash ~/.claude/hooks/python-quality-gate.sh",
            "type": "command",
            "statusMessage": "🔍 Python quality gate..."
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "command": "bash ~/.claude/hooks/pre-tool-use-write.sh",
            "type": "command",
            "statusMessage": "🔒 检查约束..."
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "command": "echo '=== [上下文压缩提醒] ==='; PLAN=$(bash ~/.claude/hooks/find-plan.sh); if [ -n \"$PLAN\" ]; then echo \"📋 当前 Plan: $(basename $PLAN)\"; sed -n '/## 核心约束/,/^##/p' \"$PLAN\" | head -10; fi",
            "type": "command"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "command": "检测编码关键词 → 注入 ruflo memory_search 指令；同时检测 plan.md 任务数，>= 2 则注入 Swarm 强制指令",
            "type": "command"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "command": "ruflo hooks metrics → 确认 MCP 挂载状态",
            "type": "command"
          }
        ]
      }
    ]
  }
}
```

**关键 hook 说明：**

| Hook | 触发时机 | 作用 |
|------|---------|------|
| `PostToolUse` (Write/Edit) | 每次写 .py 文件后 | python-quality-gate.sh 拦截问题代码 |
| `PreToolUse` (Write/Edit) | 每次写文件前 | 注入 plan 核心约束到上下文 |
| `PreCompact` | 上下文即将压缩时 | 保留 plan 核心约束不被压缩丢失 |
| `UserPromptSubmit` | 用户发送消息时 | 编码任务 → 注入 ruflo memory 查询；检测到 plan.md 有 2+ 任务 → 强制注入 Swarm 执行指令 |
| `SessionStart` | CC 启动时 | 确认 ruflo MCP 连接状态 |

## 为什么不直接起 CC 写代码？

因为 AI Agent 在没有明确目标的情况下容易"抢跑"——按自己理解的方向开始实现，做完才发现方向错了。

先对齐（脑爆 + plan），再执行。这和人类工程师的工作方式一样。
