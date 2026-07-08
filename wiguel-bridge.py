#!/usr/bin/env python3
# Wiguel-AI Bridge v3.0 - Developed by miguelmolinas713

# Copyright (c) 2026 Miguel Molina. All Rights Reserved.
# Unauthorized copying of this file, via any medium is strictly prohibited.
# Proprietary and confidential.

import functools
import os
import sys
import hashlib
import socket
import subprocess
import random
import json
import asyncio
import signal
import http.client
import urllib.request
import urllib.parse
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ══════════════════════════════════════════
#   WIGUEL-AI CONFIGURATION
# ══════════════════════════════════════════
MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguff"
MODEL_FILE = "Wiguel-AI.gguf"
PWA_URL = "https://wiguel-ai.vercel.app/"

# Automatic synchronization with the web
WEB_APP_URL = "AUTO_REPLACE_WEB_APP_URL"
FALLBACK_WEB_URLS = [
    "https://wiguel-ai.vercel.app",
    "https://ais-dev-r5seu74fsp2ztzi5ljgoom-437698592681.europe-west2.run.app",
    "https://ais-pre-r5seu74fsp2ztzi5ljgoom-437698592681.europe-west2.run.app"
]

# Cargar system prompt desde variable de entorno
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", "Eres Wiguel-AI, un asistente virtual de vanguardia.")

# ══════════════════════════════════════════
#   GLOBAL VARIABLES
# ══════════════════════════════════════════
llama_proc = None
PIN = f"{random.randint(100000, 999999)}"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ══════════════════════════════════════════
#   MODEL DOWNLOAD
# ══════════════════════════════════════════
def download_model():
    if os.path.exists(MODEL_FILE) and os.path.getsize(MODEL_FILE) > 10 * 1024 * 1024:
        print("\033[92m[✓] Wiguel-AI.gguf already available.\033[0m")
        return True

    print("\033[93m[📥] Downloading Wiguel-AI from HuggingFace...\033[0m")
    try:
        req = urllib.request.Request(MODEL_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as r, open(MODEL_FILE, 'wb') as f:
            total = int(r.headers.get('content-length', 0))
            downloaded = 0
            while True:
                block = r.read(1024 * 1024)
                if not block:
                    break
                f.write(block)
                downloaded += len(block)
                if total > 0:
                    print(f"\r  Downloading: {(downloaded/total)*100:.1f}% ({downloaded/(1024*1024):.0f}MB / {total/(1024*1024):.0f}MB)", end='', flush=True)
        print(f"\n\033[92m[✓] Download completed.\033[0m")
        return True
    except Exception as e:
        print(f"\n\033[91m[❌] Error downloading model: {e}\033[0m")
        try: os.remove(MODEL_FILE)
        except: pass
        sys.exit(1)

# ══════════════════════════════════════════
#   FIND LLAMA.CPP
# ══════════════════════════════════════════
def find_llama_server():
    import shutil
    for name in ["llama-server", "server", "llama-cli"]:
        path = shutil.which(name)
        if path:
            return path
    common_dirs = [
        ".", "./llama.cpp", "./llama.cpp/build/bin",
        os.path.expanduser("~/llama.cpp"),
        os.path.expanduser("~/llama.cpp/build/bin"),
        os.path.expanduser("~/llama.cpp/build")
    ]
    for d in common_dirs:
        if not os.path.exists(d):
            continue
        for root, dirs, files in os.walk(d):
            for f in files:
                if f in ["llama-server", "server"] or (f.startswith("llama-server") and not f.endswith((".cpp", ".h", ".o"))):
                    path = os.path.join(root, f)
                    if os.access(path, os.X_OK):
                        return path
                    path_exe = path + ".exe"
                    if os.path.exists(path_exe) and os.access(path_exe, os.X_OK):
                        return path_exe
    return None

# ══════════════════════════════════════════
#   WEBSOCKET ENDPOINT
# ══════════════════════════════════════════
def http_post_stream(path, body_bytes):
    conn = http.client.HTTPConnection("127.0.0.1", 8080, timeout=120)
    conn.request("POST", path, body=body_bytes, headers={"Content-Type": "application/json"})
    return conn.getresponse()

@app.websocket("/ws")
@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    authenticated = False
    try:
        code = websocket.query_params.get("code")
        if code and code == PIN:
            authenticated = True
            await websocket.send_text(json.dumps({"type": "auth", "status": "success"}))
        while True:
            data = await websocket.receive_text()
            if not authenticated:
                try:
                    payload = json.loads(data)
                    sent_code = payload.get("code") if isinstance(payload, dict) else data.strip()
                except:
                    sent_code = data.strip()
                if str(sent_code) == PIN:
                    authenticated = True
                    await websocket.send_text(json.dumps({"type": "auth", "status": "success"}))
                    print(f"\033[92m[✓] Device connected via PIN.\033[0m")
                else:
                    await websocket.send_text(json.dumps({"type": "auth", "status": "failed", "message": "Incorrect code."}))
                    await websocket.close()
                    break
                continue
            try:
                payload = json.loads(data)
                endpoint = payload.get("endpoint", "/v1/chat/completions")
                body = payload.get("body", payload)

                # Inject Wiguel-AI system prompt
                if "messages" in body:
                    has_system = any(m.get("role") == "system" for m in body["messages"])
                    if not has_system:
                        body["messages"].insert(0, {"role": "system", "content": SYSTEM_PROMPT})

                # Optimized parameters for short and fast responses
                body.setdefault("temperature", 0.6)
                body.setdefault("top_p", 0.95)
                body.setdefault("top_k", 40)
                body.setdefault("max_tokens", 512)
                body.setdefault("stream", True)
                body.setdefault("stop", ["<|im_end|>", "<|im_start|>", "<|eot_id|>", "User:", "Assistant:"])

                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, http_post_stream, endpoint, json.dumps(body).encode('utf-8'))
                if response.status != 200:
                    err = response.read()
                    await websocket.send_text(json.dumps({"type": "error", "message": f"Error {response.status}", "details": err.decode('utf-8', errors='ignore')}))
                    continue
                while True:
                    line = await loop.run_in_executor(None, response.readline)
                    if not line:
                        break
                    line_str = line.decode('utf-8', errors='ignore')
                    if line_str.strip():
                        await websocket.send_text(line_str)
            except Exception as e:
                await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
    except WebSocketDisconnect:
        pass

# ══════════════════════════════════════════
#   LAN SHARING ENDPOINT
# ══════════════════════════════════════════
@app.get("/share")
async def share_page(request: Request):
    """
    Any device on the same network can open this URL in a browser
    (e.g. http://192.168.1.x:8765/share) to get the sync PIN and
    connection instructions — no need to run the script themselves.
    """
    lan_ips = [ip for ip in get_local_ips() if not ip.startswith("127.")]
    ws_urls = [f"ws://{ip}:8765" for ip in lan_ips] or ["ws://localhost:8765"]
    ws_list = "".join(f"<li><code>{u}</code></li>" for u in ws_urls)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Wiguel-AI Bridge — Network Access</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #020617; color: #e2e8f0;
         display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
  .card {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 16px;
           padding: 2rem 2.5rem; max-width: 420px; width: 90%; text-align: center; }}
  h1 {{ font-size: 1.4rem; font-weight: 900; letter-spacing: 0.05em; color: #fff; margin: 0 0 0.3rem; }}
  .sub {{ font-size: 0.75rem; color: #64748b; margin-bottom: 1.8rem; text-transform: uppercase; letter-spacing: 0.1em; }}
  .pin-box {{ background: #020617; border: 2px solid #334155; border-radius: 12px;
              padding: 1.2rem; margin: 1rem 0 1.5rem; }}
  .pin-label {{ font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.15em;
                color: #64748b; margin-bottom: 0.4rem; }}
  .pin {{ font-size: 2.4rem; font-weight: 900; letter-spacing: 0.3em; color: #fbbf24; font-family: monospace; }}
  .step {{ font-size: 0.72rem; color: #94a3b8; line-height: 1.7; margin-bottom: 1.2rem; text-align: left; }}
  .step b {{ color: #e2e8f0; }}
  ul {{ list-style: none; padding: 0; margin: 0.4rem 0 0; }}
  ul li {{ font-size: 0.72rem; color: #38bdf8; margin: 0.15rem 0; }}
  code {{ background: #1e293b; padding: 0.1rem 0.4rem; border-radius: 4px; }}
  .badge {{ display: inline-block; background: #92400e22; border: 1px solid #b45309;
            color: #fbbf24; font-size: 0.6rem; font-weight: 800; letter-spacing: 0.1em;
            text-transform: uppercase; padding: 0.2rem 0.6rem; border-radius: 6px; margin-bottom: 1rem; }}
</style>
</head>
<body>
<div class="card">
  <h1>WIGUEL-AI</h1>
  <div class="sub">Local AI Bridge — Network Access</div>
  <div class="badge">🌐 LAN Sharing Active</div>
  <div class="pin-box">
    <div class="pin-label">Sync PIN for this session</div>
    <div class="pin">{PIN}</div>
  </div>
  <div class="step">
    <b>How to connect from this device or any device on this network:</b><br>
    1. Open <b>Wiguel-AI</b> in your browser (<a href="{PWA_URL}" style="color:#38bdf8">{PWA_URL}</a>).<br>
    2. Click the <b>Bridge</b> icon and enter the PIN shown above.<br>
    3. That's it — you're connected to the local AI running on the host machine.
  </div>
  <div class="step">
    <b>Bridge WebSocket addresses:</b>
    <ul>{ws_list}</ul>
  </div>
  <div style="font-size:0.6rem;color:#475569;margin-top:1.5rem;">
    This PIN is valid for the current session only. Restart the bridge to generate a new one.<br>
    Created by <b style="color:#94a3b8">Wiguel &amp; Miguel</b>
  </div>
</div>
</body>
</html>"""
    return Response(content=html, media_type="text/html")

# ══════════════════════════════════════════
#   API ENDPOINTS
# ══════════════════════════════════════════
@app.get("/verify")
async def verify(request: Request):
    code = request.query_params.get("code") or request.headers.get("X-Wiguel-Sync-Code")
    if code == PIN:
        return {"valid": True}
    return Response(content=json.dumps({"valid": False}), status_code=401, media_type="application/json")

@app.get("/api/tags")
async def api_tags(request: Request):
    return {
        "models": [{
            "name": "Wiguel-AI:latest",
            "model": "Wiguel-AI:latest",
            "details": {"format": "gguf", "family": "llama", "parameter_size": "1B"}
        }]
    }

@app.post("/api/chat")
async def api_chat(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    messages = body.get("messages", [])
    has_system = any(m.get("role") == "system" for m in messages)
    if not has_system:
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    stream = body.get("stream", True)
    llama_body = {
        "model": "Wiguel-AI:latest",
        "messages": messages,
        "stream": stream,
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 40,
        "max_tokens": 512,
        "stop": ["<|im_end|>", "<|im_start|>", "<|eot_id|>", "User:", "Assistant:"]
    }
    if stream:
        async def gen():
            try:
                req = urllib.request.Request(
                    "http://127.0.0.1:8080/v1/chat/completions",
                    data=json.dumps(llama_body).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, functools.partial(urllib.request.urlopen, req, timeout=120))
                while True:
                    line_bytes = await loop.run_in_executor(None, response.readline)
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="ignore").strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data_json = json.loads(data_str)
                        content = data_json.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if content:
                            yield json.dumps({"model": "Wiguel-AI", "message": {"role": "assistant", "content": content}, "done": False}) + "\n"
                    except:
                        pass
                yield json.dumps({"model": "Wiguel-AI", "done": True}) + "\n"
            except Exception as e:
                yield json.dumps({"error": str(e)}) + "\n"
        return StreamingResponse(gen(), media_type="application/x-ndjson")
    else:
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8080/v1/chat/completions",
                data=json.dumps(llama_body).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, functools.partial(urllib.request.urlopen, req, timeout=120))
            res_data = json.loads(res.read().decode("utf-8"))
            content = res_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"model": "Wiguel-AI", "message": {"role": "assistant", "content": content}, "done": True}
        except Exception as e:
            return Response(content=json.dumps({"error": str(e)}), status_code=500, media_type="application/json")

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy(request: Request, path: str):
    if request.method == "OPTIONS":
        return Response(status_code=200)
    url = f"http://127.0.0.1:8080/{path}"
    body_bytes = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ["host", "content-length", "origin", "referer"]}
    try:
        def send():
            req = urllib.request.Request(url, data=body_bytes or None, headers=headers, method=request.method)
            return urllib.request.urlopen(req, timeout=120)
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, send)
        def gen():
            while True:
                chunk = res.read(4096)
                if not chunk:
                    break
                yield chunk
        return StreamingResponse(gen(), status_code=res.status, media_type=res.headers.get("content-type"))
    except Exception as e:
        return Response(content=json.dumps({"error": str(e)}), status_code=500, media_type="application/json")

# ══════════════════════════════════════════
#   CLEANUP
# ══════════════════════════════════════════
def cleanup():
    global llama_proc
    print("\n\033[96m🧹 Shutting down Wiguel-AI...\033[0m")
    if llama_proc:
        try:
            llama_proc.terminate()
            llama_proc.wait(timeout=3)
        except:
            try: llama_proc.kill()
            except: pass

    print("\033[92m[✓] Wiguel-AI closed successfully.\033[0m")

def sig_handler(signum, frame):
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, sig_handler)
signal.signal(signal.SIGTERM, sig_handler)
try:
    signal.signal(signal.SIGBREAK, sig_handler)
except AttributeError:
    pass

# ══════════════════════════════════════════
#   MAIN
# ══════════════════════════════════════════
def get_local_ips():
    """Return all local IPv4 addresses, including hotspot/AP interfaces."""
    ips = []
    seen = set()

    # Method 1: socket approach (gets the primary outbound IP)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127.") and ip not in seen:
            ips.append(ip)
            seen.add(ip)
    except:
        pass

    # Method 2: enumerate ALL network interfaces (catches hotspot/AP IPs)
    try:
        import subprocess as sp
        if sys.platform == "win32":
            output = sp.check_output(["ipconfig"], text=True, errors="ignore")
            for line in output.splitlines():
                line = line.strip()
                if "IPv4" in line and ":" in line:
                    candidate = line.split(":")[-1].strip()
                    if candidate and not candidate.startswith("127.") and candidate not in seen:
                        ips.append(candidate)
                        seen.add(candidate)
        else:
            output = sp.check_output(["ip", "-4", "addr", "show"], text=True, errors="ignore")
            import re
            for match in re.finditer(r"inet (\d+\.\d+\.\d+\.\d+)/", output):
                candidate = match.group(1)
                if not candidate.startswith("127.") and candidate not in seen:
                    ips.append(candidate)
                    seen.add(candidate)
    except:
        pass

    # Method 3: hostname-based fallback
    try:
        hostname = socket.gethostname()
        for ip in socket.getaddrinfo(hostname, None, socket.AF_INET):
            candidate = ip[4][0]
            if candidate and not candidate.startswith("127.") and candidate not in seen:
                ips.append(candidate)
                seen.add(candidate)
    except:
        pass

    return ips + ["127.0.0.1"]

def register_with_backends():
    import threading
    def _do_register():
        targets = []
        if WEB_APP_URL and WEB_APP_URL != "AUTO_REPLACE_WEB_APP_URL":
            targets.append(WEB_APP_URL)
        for url in FALLBACK_WEB_URLS:
            if url not in targets:
                targets.append(url)

        payload = {
            "pin": PIN,
            "urls": [f"http://{ip}:8765" for ip in get_local_ips()]
        }
        data_bytes = json.dumps(payload).encode('utf-8')

        for target in targets:
            try:
                reg_url = f"{target.rstrip('/')}/api/bridge/register"
                req_reg = urllib.request.Request(
                    reg_url,
                    data=data_bytes,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req_reg, timeout=3.0) as reg_res:
                    if reg_res.status == 200:
                        print(f"\033[92m[✓ Auto-Sync] Sync achieved with web swarm: {target}\033[0m")
            except Exception:
                pass
    threading.Thread(target=_do_register, daemon=True).start()

def main():
    global llama_proc

    print("\033[1;36m")
    print("══════════════════════════════════════════")
    print("         W I G U E L - A I  v3.0         ")
    print("      Developed by miguelmolinas713       ")
    print("══════════════════════════════════════════")
    print("\033[0m")

    # 1. Download model if it doesn't exist
    download_model()

    # 2. Find llama.cpp
    llama_bin = find_llama_server()
    if not llama_bin:
        print("\033[91m[❌] llama-server was not found.\033[0m")
        print("     Install llama.cpp: https://github.com/ggerganov/llama.cpp")
        sys.exit(1)

    # 3. Launch llama.cpp
    print(f"\033[93m[🚀] Starting AI engine...\033[0m")
    try:
        llama_proc = subprocess.Popen(
            [llama_bin, "-m", MODEL_FILE,
             "--port", "8080",
             "-c", "4096",
             "--threads", "4",
             "--temp", "0.6",
             "--top-p", "0.95",
             "--top-k", "40"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("\033[92m[✓] Engine active on port 8080.\033[0m")
    except Exception as e:
        print(f"\033[91m[❌] Error starting llama.cpp: {e}\033[0m")
        sys.exit(1)

    import time
    time.sleep(4)

    # 4. Display sync code and start server
    all_ips = get_local_ips()
    lan_ips = [ip for ip in all_ips if not ip.startswith("127.")]

    print("\n" + "═"*52)
    print(f"\033[1;32m   SYNCHRONIZATION PIN:\033[0m")
    print(f"\033[1;33m          >>>  {PIN}  <<<\033[0m")
    print(f"\033[1;32m   Enter it at: {PWA_URL}\033[0m")
    print()
    print(f"\033[1;35m   Bridge addresses (WebSocket):\033[0m")
    for ip in all_ips:
        tag = " ← this device" if ip == "127.0.0.1" else ""
        print(f"     👉 ws://{ip}:8765{tag}")
    if lan_ips:
        print()
        print(f"\033[1;36m   ━━ LAN SHARING ━━\033[0m")
        print(f"\033[0;36m   Other devices on the same Wi-Fi / hotspot\033[0m")
        print(f"\033[0;36m   do NOT need to run this script.\033[0m")
        print(f"\033[0;36m   They can open this page in any browser:\033[0m")
        for ip in lan_ips:
            print(f"\033[1;33m     🌐 http://{ip}:8765/share\033[0m")
        print(f"\033[0;36m   That page shows the PIN and how to connect.\033[0m")
    print("═"*52)
    print("  Ctrl+C to stop Wiguel-AI\n")

    register_with_backends()

    try:
        uvicorn.run(app, host="0.0.0.0", port=8765, log_level="warning")
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()

if __name__ == "__main__":
    main()
