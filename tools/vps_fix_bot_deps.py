#!/usr/bin/env python3
"""Fix VPS bot deps, env, systemd and restart the service."""
from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

import paramiko

DEFAULT_VPS_ENV = Path("/Users/darya_botova/abhazbereg-bot/.env.vps.local")
DEFAULT_SSH_KEY = Path.home() / ".ssh" / "id_ed25519_github"


def load_vps_env() -> None:
    if os.getenv("VPS_HOST", "").strip() and os.getenv("VPS_USER", "").strip():
        return
    for path in (
        Path(os.environ.get("VPS_ENV_FILE", str(DEFAULT_VPS_ENV))),
        Path(__file__).resolve().parents[1] / ".env.vps.local",
    ):
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return


load_vps_env()
HOST = os.environ.get("VPS_HOST", "").strip()
USER = os.environ.get("VPS_USER", "").strip()
PASSWORD = os.environ.get("VPS_PASSWORD", "").strip()
SSH_KEY = Path(os.environ.get("VPS_SSH_KEY", str(DEFAULT_SSH_KEY))).expanduser()
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
    if not HOST or not USER:
        print("Missing VPS_HOST/VPS_USER. Set env or create .env.vps.local", file=sys.stderr)
        return 2
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print("Connecting to VPS ...")
    connect_kwargs: dict[str, object] = {
        "hostname": HOST,
        "username": USER,
        "timeout": 30,
        "allow_agent": False,
        "look_for_keys": False,
    }
    if SSH_KEY.is_file():
        connect_kwargs["key_filename"] = str(SSH_KEY)
    elif PASSWORD:
        connect_kwargs["password"] = PASSWORD
    else:
        print("Missing VPS_SSH_KEY or VPS_PASSWORD for SSH auth", file=sys.stderr)
        return 2
    client.connect(**connect_kwargs)

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
