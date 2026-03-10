---
name: run
description: Use when user types /run to launch the Construct 3 RAG chat or server in a new terminal window.
---

# Run Construct 3 RAG

## Modes

| 命令 | 作用 |
|------|------|
| `/run` | 启动对话客户端（自动连接服务器，或本地加载模型） |
| `/run server` | 启动模型服务器（只需启动一次，多个 chat 共享） |

## Steps

1. **终止旧进程**：

```bash
for pid in $(wmic process where "name='python.exe' and commandline like '%chat.py%'" get processid 2>/dev/null | grep -E '^[0-9]+' | tr -d '\r'); do
  taskkill /PID "$pid" /F 2>/dev/null || true
done
```

2. **根据参数启动**：

```bash
# /run server
wt -d "D:/Users/Administrator/Documents/GitHub/Construct3-RAG" \
  "C:/Users/test/AppData/Local/Python/bin/python.exe" -X utf8 scripts/server.py 2>/dev/null \
|| start "RAG-Server" cmd /k "cd /d D:\Users\Administrator\Documents\GitHub\Construct3-RAG && C:\Users\test\AppData\Local\Python\bin\python.exe -X utf8 scripts\server.py"

# /run (chat)
wt -d "D:/Users/Administrator/Documents/GitHub/Construct3-RAG" \
  "C:/Users/test/AppData/Local/Python/bin/python.exe" -X utf8 scripts/chat.py 2>/dev/null \
|| start "RAG-Chat" cmd /k "cd /d D:\Users\Administrator\Documents\GitHub\Construct3-RAG && C:\Users\test\AppData\Local\Python\bin\python.exe -X utf8 scripts\chat.py"
```

3. **告知用户**：新窗口已打开。服务器模式：模型加载约 30–60 秒后即可连接多个 chat。

## Notes

- `chat.py` 启动时自动检测服务器（`localhost:8765`），有则直接连接，无则本地加载
- 服务器在所有客户端关闭后 30 秒自动退出
- 端口可通过环境变量 `RAG_SERVER_PORT` 修改（默认 `8765`）
