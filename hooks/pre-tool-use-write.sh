#!/bin/bash
# pre-tool-use-write.sh — PreToolUse hook（Write/Edit/MultiEdit）
# 每次 AI 写文件前触发：
#   1. 检查质量门是否有未修复的阻断
#   2. 注入 plan.md 核心约束到 AI 上下文
#
# 安装：复制到 ~/.claude/hooks/pre-tool-use-write.sh
# 配置：在 ~/.claude/settings.json 的 PreToolUse 里加入（见 docs/architecture.md）

INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', 'unknown'))
except:
    print('unknown')
" 2>/dev/null || echo 'unknown')

# 注入 plan 核心约束（有则注入，无则跳过）
PLAN=$(bash "$(dirname "$0")/find-plan.sh")
if [ -n "$PLAN" ]; then
    CONSTRAINTS=$(sed -n '/## 核心约束/,/^##/p' "$PLAN" | grep -v '^##' | grep -v '^$' | head -15)
    if [ -n "$CONSTRAINTS" ]; then
        python3 -c "
import json, sys
c = sys.argv[1]
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': '[核心约束 - 必须遵守]\n' + c}}, ensure_ascii=False))
" "$CONSTRAINTS" 2>/dev/null
    fi
fi

exit 0
