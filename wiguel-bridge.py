#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Wiguel-AI - Local GPU Terminal Bridge
=====================================
Sincroniza tu navegador de forma segura con tu motor de inferencia local (Ollama).
No requiere dependencias externas, solo Python 3 estándar.

Uso:
  python wiguel-bridge.py [--port 8765] [--ollama http://localhost:11434]
"""

import os
import sys
import json
import random
import socket
import urllib.request
import urllib.parse
import urllib.error
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Marcador que será auto-reemplazado por el backend para saber dónde registrarse.
# Si no está configurado, por defecto se asume la URL actual en producción o localhost.
WEB_APP_URL = "AUTO_REPLACE_WEB_APP_URL"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
BRIDGE_PORT = 8765

# Generar PIN de sincronización aleatorio de 6 dígitos
SYNC_PIN = "".join(str(random.randint(0, 9)) for _ in range(6))

# Colores de consola ANSI para un diseño impecable
C_GREEN = "\033[92m"
C_BLUE = "\033[94m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_CYAN = "\033[96m"
C_BOLD = "\033[1m"
C_RESET = "\033[0m"

if sys.platform == "win32":
    # Habilitar soporte de colores ANSI en Windows
    os.system("")

def get_local_ips():
    """Obtiene todas las IPs locales activas de la máquina."""
    ips = ["http://localhost:8765", "http://127.0.0.1:8765"]
    try:
        # Obtener IP por sockets
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            # No necesita ser alcanzable, solo para resolver la interfaz principal
            s.connect(('8.8.8.8', 1))
            ip = s.getsockname()[0]
            if ip and ip != "127.0.0.1":
                ips.append(f"http://{ip}:8765")
        except Exception:
            pass
        finally:
            s.close()
            
        # Intento secundario por hostname
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            addr = f"http://{ip}:8765"
            if addr not in ips and not ip.startswith("127."):
                ips.append(addr)
    except Exception:
        pass
    return list(dict.fromkeys(ips)) # Eliminar duplicados preservando orden

class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Sobrescribir para evitar logs ruidosos en la terminal principal
        pass

    def send_cors_headers(self, content_type="application/json"):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Wiguel-Sync-Code, Authorization")
        if content_type:
            self.send_header("Content-Type", content_type)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers(None)
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def verify_auth(self):
        """Verifica que el PIN sea correcto."""
        # Obtener de query params
        parsed_url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_url.query)
        code_query = query.get("code", [None])[0]

        # Obtener de headers
        code_header = self.headers.get("X-Wiguel-Sync-Code") or self.headers.get("x-wiguel-sync-code")

        provided_code = code_query or code_header
        return provided_code == SYNC_PIN

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # 1. Página de inicio del puente (Landing informativa)
        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_cors_headers("text/html; charset=utf-8")
            self.end_headers()
            
            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Wiguel-AI GPU Bridge</title>
    <style>
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
        }}
        .card {{
            background: #1e293b;
            padding: 2.5rem;
            border-radius: 1.5rem;
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.3);
            text-align: center;
            max-width: 500px;
            border: 1px solid #334155;
        }}
        h1 {{
            color: #6366f1;
            margin-top: 0;
            font-size: 1.8rem;
        }}
        .pin {{
            font-size: 3rem;
            font-weight: 800;
            letter-spacing: 0.2em;
            color: #22c55e;
            background: #0f172a;
            padding: 1rem;
            border-radius: 1rem;
            margin: 1.5rem 0;
            border: 1px solid #1e293b;
            font-family: 'Courier New', monospace;
        }}
        .status {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: #1e293b;
            border: 1px solid #22c55e;
            color: #22c55e;
            padding: 0.4rem 1rem;
            border-radius: 2rem;
            font-size: 0.85rem;
            font-weight: 600;
        }}
        .dot {{
            width: 8px;
            height: 8px;
            background: #22c55e;
            border-radius: 50%;
            animation: pulse 1.5s infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(0.9); opacity: 0.6; }}
            50% {{ transform: scale(1.2); opacity: 1; }}
            100% {{ transform: scale(0.9); opacity: 0.6; }}
        }}
        p {{
            color: #94a3b8;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="status"><span class="dot"></span> PUENTE ACTIVO</div>
        <h1>Wiguel-AI GPU Bridge</h1>
        <p>Tu terminal local está vinculada de forma segura. Introduce este código PIN en la aplicación web para autorizar la conexión:</p>
        <div class="pin">{SYNC_PIN}</div>
        <p style="font-size: 0.8rem;">Ollama: <span style="color: #6366f1;">{DEFAULT_OLLAMA_URL}</span></p>
    </div>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))
            return

        # 2. Verificar código PIN
        if path == "/verify":
            valid = self.verify_auth()
            self.send_response(200 if valid else 403)
            self.send_cors_headers()
            self.end_headers()
            response = {"valid": valid, "message": "Autorizado" if valid else "PIN Incorrecto"}
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        # 3. Obtener modelos locales (Proxy GET /api/tags)
        if path == "/api/tags":
            if not self.verify_auth():
                self.send_response(403)
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "PIN no autorizado"}).encode("utf-8"))
                return

            req = urllib.request.Request(f"{DEFAULT_OLLAMA_URL}/api/tags", method="GET")
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = response.read()
                    self.send_response(200)
                    self.send_cors_headers("application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
            except Exception as e:
                self.send_response(502)
                self.send_cors_headers()
                self.end_headers()
                err_msg = {"error": "Ollama desconectado", "details": str(e)}
                self.wfile.write(json.dumps(err_msg).encode("utf-8"))
            return

        # Ruta desconocida
        self.send_response(404)
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Ruta no encontrada"}).encode("utf-8"))

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # 1. Proxy para chat con streaming (POST /api/chat)
        if path == "/api/chat":
            if not self.verify_auth():
                self.send_response(403)
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "PIN no autorizado"}).encode("utf-8"))
                return

            # Leer cuerpo del POST
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)

            req = urllib.request.Request(
                f"{DEFAULT_OLLAMA_URL}/api/chat",
                data=post_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            try:
                # Realizar la petición con streaming
                with urllib.request.urlopen(req, timeout=120) as response:
                    self.send_response(200)
                    self.send_cors_headers(response.headers.get("Content-Type", "application/json"))
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()

                    print(f"\n{C_CYAN}[Inferencia local]{C_RESET} Procesando chat...", end="", flush=True)

                    while True:
                        chunk = response.read(1024)
                        if not chunk:
                            break
                        # Escribir chunk en formato chunked encoding
                        hex_len = f"{len(chunk):X}\r\n".encode("utf-8")
                        self.wfile.write(hex_len)
                        self.wfile.write(chunk)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()

                    # Finalizar transferencia chunked
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                    print(f" {C_GREEN}¡Completado!{C_RESET}")
            except Exception as e:
                self.send_response(502)
                self.send_cors_headers()
                self.end_headers()
                err_msg = {"error": "Ollama desconectado o error de inferencia", "details": str(e)}
                self.wfile.write(json.dumps(err_msg).encode("utf-8"))
                print(f" {C_RED}Error:{C_RESET} {e}")
            return

        self.send_response(404)
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Ruta no encontrada"}).encode("utf-8"))

def register_with_web_app(pin, urls):
    """Intenta registrar el PIN y las URLs del puente en el backend central de la web app."""
    if not WEB_APP_URL or "AUTO_REPLACE" in WEB_APP_URL:
        return
    
    payload = json.dumps({"pin": pin, "urls": urls}).encode("utf-8")
    req = urllib.request.Request(
        f"{WEB_APP_URL}/api/bridge/register",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                print(f"{C_GREEN}✓ Sincronización auto-registrada en la nube.{C_RESET}")
            else:
                print(f"{C_YELLOW}⚠ No se pudo registrar la sincronización en la nube (Status: {response.status}).{C_RESET}")
    except Exception as e:
        print(f"{C_YELLOW}⚠ Sincronización offline (No se pudo registrar en {WEB_APP_URL}).{C_RESET}")

def check_ollama_status():
    """Verifica si Ollama está corriendo en segundo plano."""
    req = urllib.request.Request(f"{DEFAULT_OLLAMA_URL}/api/tags", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=2) as response:
            if response.status == 200:
                print(f"{C_GREEN}✓ Motor Ollama detectado en {DEFAULT_OLLAMA_URL}{C_RESET}")
                return True
    except Exception:
        pass
    print(f"{C_YELLOW}⚠ Ollama no detectado en {DEFAULT_OLLAMA_URL}. Asegúrate de iniciarlo antes de chatear.{C_RESET}")
    return False

def run_server():
    server_address = ("0.0.0.0", BRIDGE_PORT)
    httpd = HTTPServer(server_address, BridgeHandler)
    
    # Dibujar Banner espectacular
    print(C_BOLD + C_BLUE + "=====================================================" + C_RESET)
    print(C_BOLD + C_GREEN + "                 WIGUEL-AI GPU BRIDGE                " + C_RESET)
    print(C_BOLD + C_BLUE + "=====================================================" + C_RESET)
    print(f" {C_BOLD}Código PIN:{C_RESET} {C_GREEN}{C_BOLD}{SYNC_PIN}{C_RESET}")
    print(f" {C_BOLD}Puerto del Puente:{C_RESET} {C_BLUE}{BRIDGE_PORT}{C_RESET}")
    print(f" {C_BOLD}Plataforma web de origen:{C_RESET} {C_CYAN}{WEB_APP_URL}{C_RESET}")
    print(C_BLUE + "-----------------------------------------------------" + C_RESET)
    
    # Verificar estado de Ollama local
    check_ollama_status()
    
    # Obtener IPs locales
    local_urls = get_local_ips()
    print(f" {C_BOLD}Direcciones del puente detectadas:{C_RESET}")
    for url in local_urls:
        print(f"  - {url}")
    print(C_BLUE + "-----------------------------------------------------" + C_RESET)

    # Registrar el puente en segundo plano de manera asíncrona
    threading.Thread(target=register_with_web_app, args=(SYNC_PIN, local_urls), daemon=True).start()

    print(f"{C_GREEN}✓ Puente iniciado y escuchando peticiones locales de forma segura...{C_RESET}")
    print("Presiona Ctrl+C para detener el puente.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}Deteniendo puente de forma segura...{C_RESET}")
        httpd.server_close()
        print(f"{C_GREEN}✓ Puente detenido.{C_RESET}")

if __name__ == "__main__":
    run_server()
