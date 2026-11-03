#!/usr/bin/env python3
import sys
import json
import struct
import subprocess
import os
import re
from urllib.parse import urlparse, parse_qs

env = os.environ.copy()

SOCKET_PATH = "/tmp/yt_mpv_socket"
HISTORY_FILE = "/tmp/yt_mpv_history.txt"
YOUTUBE_ID_RE = re.compile(
    r"(?:[?&]v=|youtu\.be/|/shorts/|/embed/)([a-zA-Z0-9_-]{11})(?:[^\w-]|$)"
)

env['SOCKET_PATH'] = SOCKET_PATH

def read_message():
    try:
        text_length_bytes = sys.stdin.buffer.read(4)
        if not text_length_bytes:
            return None
        text_length = struct.unpack('@I', text_length_bytes)[0]
        text = sys.stdin.buffer.read(text_length).decode('utf-8')
        return json.loads(text)
    except Exception:
        return None

def send_message(message):
    try:
        text = json.dumps(message).encode('utf-8')
        sys.stdout.buffer.write(struct.pack('@I', len(text)))
        sys.stdout.buffer.write(text)
        sys.stdout.buffer.flush()
    except Exception:
        pass

def get_video_id(url):
    match = YOUTUBE_ID_RE.search(url or "")
    return match.group(1) if match else None

def get_request_kind(message, url):
    kind = message.get("kind")
    if kind in {"video", "playlist"}:
        return kind

    try:
        query = parse_qs(urlparse(url or "").query)
    except ValueError:
        return "video"

    return "playlist" if query.get("list") else "video"

def is_duplicate(video_id):
    if not video_id:
        return False
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                if video_id in {line.strip() for line in f}:
                    return True
        with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
            f.write(video_id + '\n')
        return False
    except OSError:
        return False

def send_ipc_command(command, timeout=None):
    payload = (json.dumps({"command": command}, separators=(',', ':')) + "\n").encode('utf-8')
    return subprocess.run(
        ["socat", "-t", str(timeout or 1), "-", f"UNIX-CONNECT:{SOCKET_PATH}"],
        input=payload,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=timeout,
    )

def is_mpv_running():
    if not os.path.exists(SOCKET_PATH):
        return False
    try:
        if send_ipc_command(["get_version"], timeout=0.5).returncode == 0:
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        os.remove(SOCKET_PATH)
    except OSError:
        pass
    return False

def build_mpv_command(url, kind, video_id):
    if kind == "video" and video_id:
        return ["script-message", "add_direct_video", url, video_id]
    return ["script-message", "add_to_queue", url, kind]

def main():

    message = read_message()
    if message and "url" in message:
        video_url = message["url"]
        video_id = message.get("videoId") or get_video_id(video_url)
        request_kind = get_request_kind(message, video_url)
        mpv_command = build_mpv_command(video_url, request_kind, video_id)
        
        env['video_url'] = video_url
        env['request_kind'] = request_kind
        env['ipc_command'] = json.dumps({"command": mpv_command}, separators=(',', ':'))

        if is_mpv_running():
            try:
                send_ipc_command(mpv_command)
            except (OSError, subprocess.SubprocessError):
                send_message({"status": "error", "message": "Không gửi được lệnh sang MPV"})
                return
            send_message({"status": "success", "message": "Đã đẩy vào hàng chờ Lua", "kind": request_kind})
        else:
            # Xóa lịch sử cũ khi khởi động MPV mới
            try:
                if os.path.exists(HISTORY_FILE):
                    os.remove(HISTORY_FILE)
            except OSError as e:
                pass
            inline_bash_script = r"""
                LOG_FILE="/tmp/mpv_script.log"
                echo "=== Khởi tạo MPV Loader: $(date) ===" >> "$LOG_FILE"

                # 1. Dùng setsid để tách hoàn toàn mpv khỏi terminal/python đang chạy
                setsid mpv --input-ipc-server="$SOCKET_PATH" \
                    --force-window=yes \
                    --idle=yes \
                    --log-file="$LOG_FILE" </dev/null >> "$LOG_FILE" 2>&1 &

                # 2. Subshell cũng cần được bảo vệ bằng cách bọc trong nohup bash -c
                # Để tránh lỗi nháy đơn/kép, truyền biến qua export
                export SOCKET_PATH
                export LOG_FILE
                
                nohup bash -c '
                    for _ in {1..30}; do
                        [ -S "$SOCKET_PATH" ] && break
                        sleep 0.1
                    done

                    sleep 0.8

                    for _ in {1..10}; do
                        RESPONSE=$(python3 -c "import os, sys; sys.stdout.write(os.environ.get('\''ipc_command'\'', '\'''\'') + '\''\n'\'')" \
                            | socat -t 1 - UNIX-CONNECT:"$SOCKET_PATH" 2>>"$LOG_FILE")
                        
                        if [ -n "$RESPONSE" ]; then
                            echo "[IPC Response]: $RESPONSE" >> "$LOG_FILE"
                            break
                        fi
                        sleep 0.3
                    done
                ' </dev/null >> "$LOG_FILE" 2>&1 &

                echo "Đã khởi chạy background process hoàn toàn độc lập. Theo dõi log tại: $LOG_FILE"
                exit 0
            """
            try:
                send_message({"status": "success", "message": "Khởi động MPV Loader", "kind": request_kind})
                subprocess.Popen([
                    "kitty", 
                    "--title", "MPV YouTube Loader",
                    "bash", "-c", inline_bash_script,
                ], env=env, stdout=subprocess.DEVNULL, stderr=None, start_new_session=True)
            except Exception:
                try:
                    with open("/tmp/mpv_debug.log", "a", encoding="utf-8") as log:
                        log.write("Tiến trình không chạy\n")
                except OSError:
                    pass

if __name__ == "__main__":
    main()
