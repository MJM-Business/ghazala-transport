"""Launch the app with the portable Python included in the standalone ZIP."""
from pathlib import Path
import argparse
import runpy
import socket
import sys
import threading
import time
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def free_port(host, requested):
    for port in range(requested, min(requested + 11, 65536)):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind((host, port))
            return port
        except OSError:
            continue
    raise RuntimeError("No free port found. Close the old server, then try again.")


def open_when_ready(address):
    for _ in range(60):
        try:
            with urlopen(address, timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(address)
                    return
        except OSError:
            time.sleep(0.25)
    print("The browser did not open automatically. Open this address: " + address, flush=True)


def main():
    parser = argparse.ArgumentParser(description="Start Ghazala Transport locally")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    port = free_port(args.host, args.port)
    address = "http://127.0.0.1:" + str(port) + "/"
    print("\nGhazala Transport - standalone local app", flush=True)
    print("Address: " + address, flush=True)
    if port != args.port:
        print("Port " + str(args.port) + " is busy; using " + str(port) + ".", flush=True)
    print("Keep this window open. Press Ctrl+C to stop the app.\n", flush=True)
    if args.host == "0.0.0.0":
        print("For a phone on the same Wi-Fi: http://YOUR-PC-IP:" + str(port) + "/", flush=True)
        print("Use ipconfig to find the PC's current IPv4 address.\n", flush=True)
    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(address,), daemon=True).start()
    sys.argv = [str(ROOT / "server.py"), "--host", args.host, "--port", str(port)]
    try:
        runpy.run_path(str(ROOT / "server.py"), run_name="__main__")
    except KeyboardInterrupt:
        print("\nGhazala Transport stopped.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\nCould not start Ghazala Transport: " + str(exc), file=sys.stderr, flush=True)
        raise SystemExit(1)
