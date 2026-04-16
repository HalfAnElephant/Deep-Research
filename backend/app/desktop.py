from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn


APP_DIR_NAME = "ResearchFlow"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _default_data_dir() -> Path:
    local_appdata = os.getenv("LOCALAPPDATA", "").strip()
    if local_appdata:
        return Path(local_appdata) / APP_DIR_NAME
    return Path.home() / f".{APP_DIR_NAME.lower()}"


def _bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _pick_port(host: str) -> int:
    preferred = os.getenv("DR_PORT", "").strip()
    if preferred.isdigit():
        return int(preferred)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, timeout_seconds: float = 20.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.25)
    raise RuntimeError(f"服务启动超时：{url}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch the packaged Research Flow desktop app.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for the local HTTP server")
    parser.add_argument("--port", type=int, default=None, help="Bind port for the local HTTP server")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically")
    parser.add_argument("--real-mode", action="store_true", help="Disable mock mode and use real providers")
    args = parser.parse_args()

    bundle_dir = _bundle_dir()
    _load_env_file(bundle_dir / "desktop.env")

    os.environ.setdefault("DR_DATA_DIR", str(_default_data_dir()))
    os.environ.setdefault("DR_USE_MOCK_SOURCES", "true")
    if args.real_mode:
        os.environ["DR_USE_MOCK_SOURCES"] = "false"

    host = args.host
    port = args.port or _pick_port(host)
    os.environ["DR_PORT"] = str(port)

    from app.main import app

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=False)
    server_thread.start()

    url = f"http://{host}:{port}"
    try:
        _wait_for_server(f"{url}/healthz")
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not args.no_browser:
        webbrowser.open(url)

    print(f"Research Flow is running at {url}")
    print("Close this window to stop the local server.")

    try:
        server_thread.join()
    except KeyboardInterrupt:
        server.should_exit = True
        server_thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
