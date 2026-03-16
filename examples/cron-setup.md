# 定时任务配置指南

## 蒸馏脚本定时运行

使用 cron 每天 19:00 自动触发蒸馏：

```bash
# 编辑 crontab
crontab -e

# 添加以下行（根据你的实际路径修改）
0 19 * * * /path/to/distill-notify.sh
```

## distill-notify.sh 示例

```bash
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# 运行蒸馏脚本
python3 /path/to/distill.py >> /path/to/distill.log 2>&1

# 通过 OpenClaw 推送飞书通知
MSG=$(python3 -c "
import json, pathlib
try:
    p = pathlib.Path('/path/to/distill-pending.json')
    d = json.loads(p.read_text())
    msg = '📚 每日蒸馏报告\n\n汇总了' + str(d['total_count']) + '条编码经验：\n\n' + d['preview']
    msg += '\n\n---\n回复「确认蒸馏」→ 写入 CLAUDE.md\n回复「跳过」→ 本次不写入'
    print(msg)
except Exception as e:
    print('蒸馏完成，请回复确认或跳过（错误: ' + str(e) + '）')
" 2>/dev/null)

# 使用 OpenClaw CLI 发送消息（替换为你的 target）
openclaw message send --channel feishu --target "YOUR_TARGET_ID" --message "$MSG"
```

## 确认流程

1. 蒸馏脚本生成 `distill-pending.json`（status: pending）
2. 通知脚本推送飞书消息
3. 用户回复「确认蒸馏」→ OpenClaw 触发 `distill.py --commit`
4. 用户回复「跳过」→ 删除 pending 文件

## 注意事项

- 确保 Python 环境中有 `sqlite3`、`json`、`pathlib`（标准库，无需额外安装）
- 如果使用 OpenClaw 的 HEARTBEAT 机制，也可以在心跳中检测 pending 文件并推送
- 日志文件建议定期清理或 logrotate
