#!/bin/bash
# Python Quality Gate — PostToolUse hook
# 每次 AI 写完 Python 文件后自动触发，检查结果反馈给 AI 自己修复
#
# 安装：复制到 ~/.claude/hooks/python-quality-gate.sh
# 配置：在 ~/.claude/settings.json 的 PostToolUse 里加入（见 docs/architecture.md）

# 从 stdin 解析 file_path
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except:
    print('')
" 2>/dev/null)

# 只处理 Python 文件
if [[ -z "$FILE_PATH" ]] || [[ "$FILE_PATH" != *.py ]] || [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

ERRORS=0
OUTPUT=""

# ── ruff lint 检查 ──
RUFF_OUT=$(ruff check "$FILE_PATH" 2>&1)
RUFF_EXIT=$?
if [[ "$RUFF_EXIT" -ne 0 ]]; then
    ERRORS=1
    OUTPUT+="[ruff] $FILE_PATH 存在问题：
$RUFF_OUT
Fix: 运行 ruff check --fix $FILE_PATH 可自动修复大部分问题。
"
fi

# ── hardcode 端口检查（只匹配赋值/函数调用，不匹配字符串切片）──
HARDCODE=$(grep -nE "(port|PORT)\s*=\s*(5000|5001|5002|5003|8000|8080|3000)|bind\(['\"].*:(5000|5001|5002|5003|8000|8080|3000)" "$FILE_PATH" 2>/dev/null | grep -v "^\s*#")
if [[ -n "$HARDCODE" ]]; then
    ERRORS=1
    OUTPUT+="[架构约束] 禁止 hardcode 端口，请使用配置文件中定义的常量：
$HARDCODE
Fix: 将端口值提取到配置文件或环境变量。
"
fi

# ── 文件行数检查 ──
LINE_COUNT=$(wc -l < "$FILE_PATH")
if [[ "$LINE_COUNT" -gt 500 ]]; then
    ERRORS=1
    OUTPUT+="[架构约束] 文件超过 500 行（当前 ${LINE_COUNT} 行），请拆分为更小的模块。
Fix: 将独立功能提取到单独文件，保持每个文件职责单一。
"
fi

# ── 输出结果 ──
if [[ "$ERRORS" -eq 1 ]]; then
    echo "⚠️  Quality Gate 未通过 — $FILE_PATH"
    echo ""
    echo "$OUTPUT"
    echo "请修复以上问题后继续。"
fi

exit 0
