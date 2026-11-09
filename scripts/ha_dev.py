"""Local HA development commands; Python standard library only."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".ha-dev"
SOURCE = ROOT / "custom_components" / "sihas"


def initialize():
    config = STATE / "config"
    config.mkdir(parents=True, exist_ok=True)
    target = config / "configuration.yaml"
    if not target.exists():
        shutil.copyfile(ROOT / "dev" / "configuration.yaml", target)
    (STATE / "image.env").touch(exist_ok=True)


def compose(*args):
    return ["docker", "compose", "--project-name", "sihas-dev",
            "--env-file", str(STATE / "image.env"),
            "-f", str(ROOT / "compose.dev.yaml"), *args]


def snapshot(directory):
    """Hash content so atomic saves and preserved timestamps are supported."""
    result = {}
    for path in directory.rglob("*"):
        if path.suffix not in {".py", ".json"} or "__pycache__" in path.parts:
            continue
        try:
            result[str(path.relative_to(directory))] = hashlib.sha256(path.read_bytes()).digest()
        except FileNotFoundError:
            pass  # An editor may replace/delete a file during this scan.
    return result


class RestartWatcher:
    def __init__(self, initial, start_restart):
        self.previous = initial
        self.start_restart = start_restart
        self.changed_at = None
        self.process = None

    def tick(self, current, now):
        if current != self.previous:
            self.previous = current
            self.changed_at = now
        if self.process is not None:
            code = self.process.poll()
            if code is None:
                return
            self.process = None
            if code:
                print("HA restart failed; check Docker output. Save again to retry.", flush=True)
        if self.changed_at is not None and now - self.changed_at >= 1:
            print("Source changed; restarting development HA…", flush=True)
            self.process = self.start_restart()
            self.changed_at = None


def watch():
    # Baseline before startup: changes during startup are picked up on the first tick.
    watcher = RestartWatcher(snapshot(SOURCE),
                             lambda: subprocess.Popen(compose("restart", "homeassistant")))
    subprocess.run(compose("up", "-d"), check=True)
    logs = subprocess.Popen(compose("logs", "--tail", "100", "--follow", "homeassistant"))
    print("Watching SiHAS .py/.json files (1s debounce). Ctrl+C stops watching, not HA.", flush=True)
    try:
        while True:
            watcher.tick(snapshot(SOURCE), time.monotonic())
            time.sleep(0.25)
    finally:
        logs.terminate()
        logs.wait()
        if watcher.process is not None:
            watcher.process.wait()


def pin():
    container = subprocess.check_output(compose("ps", "-q", "homeassistant"), text=True).strip()
    if not container:
        raise RuntimeError("Start and verify HA before pinning its image.")
    image_id = subprocess.check_output(
        ["docker", "inspect", "--format", "{{.Image}}", container], text=True).strip()
    digests = json.loads(subprocess.check_output(
        ["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", image_id], text=True))
    digest = next((d for d in digests or []
                   if d.startswith("ghcr.io/home-assistant/home-assistant@")), None)
    if not digest:
        raise RuntimeError("Running image has no official registry digest; cannot pin it.")
    (STATE / "image.env").write_text(f"HA_IMAGE={digest}\n")
    print(f"Pinned verified image: {digest}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "up", "watch", "restart", "logs", "down", "pin"])
    args = parser.parse_args()
    initialize()
    if args.command == "watch":
        watch()
    elif args.command == "pin":
        pin()
    elif args.command != "init":
        commands = {"up": ["up", "-d"], "restart": ["restart", "homeassistant"],
                    "logs": ["logs", "--tail", "100", "--follow", "homeassistant"],
                    "down": ["down"]}
        subprocess.run(compose(*commands[args.command]), check=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
