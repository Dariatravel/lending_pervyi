#!/usr/bin/env python3
"""Fix VPS bot deps, env, systemd and restart the service."""
from __future__ import annotations

import os
import sys
import textwrap

import paramiko

HOST = os.environ.get("VPS_HOST", "81.31.247.74")
USER = os.environ.get("VPS_USER", "root")
PASSWORD = os.environ["VPS_PASSWORD"]
PROJECT = "/srv/lending_pervyi"

ENV_OVERRIDES = {
    "TELEGRAM_NEW_OBJECTS_SCAN_LIMIT": "120",
    "TELEGRAM_NEW_OBJECTS_SCAN_DAYS": "45",
    "TELEGRAM_NEW_OBJECTS_SCAN_RECENT_ALL": "0",
    "TG_SCRIPT_TIMEOUT_SECONDS": "7200",
    "TG_CONNECT_TIMEOUT_SECONDS": "120",
}


def run(client: paramiko.SSHClient, command: str, *, timeout: int = 600) -> int:
    print(f"\n$ {command}")
    _, stdout, stderr = client.exec_command(command, get_pty=True, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip())
    if err.strip() and code != 0:
        print(err.rstrip(), file=sys.stderr)
    return code


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST} ...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

    run(client, f"cd {PROJECT} && git pull --ff-only origin main", timeout=300)
    run(client, f"cd {PROJECT} && .venv/bin/pip install -r requirements-site-update-bot.txt", timeout=900)

    patch_env = textwrap.dedent(
        f"""
        python3 - <<'PY'
        from pathlib import Path

        path = Path("{PROJECT}/.env.site-update-bot")
        overrides = {ENV_OVERRIDES!r}
        lines = path.read_text(encoding="utf-8").splitlines()
        seen = set()
        out = []
        for line in lines:
            key = line.split("=", 1)[0].strip() if "=" in line else ""
            if key in overrides:
                out.append(f"{{key}}={{overrides[key]}}")
                seen.add(key)
            else:
                out.append(line)
        for key, value in overrides.items():
            if key not in seen:
                out.append(f"{{key}}={{value}}")
        path.write_text("\\n".join(out).rstrip() + "\\n", encoding="utf-8")
        PY
        """
    ).strip()
    run(client, patch_env)

    systemd_unit = textwrap.dedent(
        f"""
        cat > /etc/systemd/system/abhazbereg-site-update-bot.service <<'EOF'
        [Unit]
        Description=Abhazbereg Telegram site update bot
        After=network-online.target
        Wants=network-online.target

        [Service]
        Type=simple
        WorkingDirectory={PROJECT}
        EnvironmentFile={PROJECT}/.env.site-update-bot
        ExecStart={PROJECT}/.venv/bin/python {PROJECT}/scripts/site_update_bot.py
        Restart=always
        RestartSec=10
        KillMode=control-group
        TimeoutStopSec=30

        [Install]
        WantedBy=multi-user.target
        EOF
        """
    ).strip()
    run(client, systemd_unit)
    run(client, "systemctl daemon-reload")

    run(client, "pkill -f 'scripts/watch_telegram_updates.py' || true")
    run(client, "pkill -f 'scripts/site_update_bot.py' || true")
    run(client, "systemctl reset-failed abhazbereg-site-update-bot || true")
    run(client, "systemctl restart abhazbereg-site-update-bot")
    run(client, "systemctl is-active abhazbereg-site-update-bot")
    client.close()
    print("\nVPS bot updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
