#!/usr/bin/env python3
"""One-time VPS setup for site_update_bot via SSH."""
from __future__ import annotations

import os
import sys
import textwrap
import time
from pathlib import Path

import paramiko

DEFAULT_VPS_ENV = Path("/Users/darya_botova/abhazbereg-bot/.env.vps.local")
DEFAULT_SSH_KEY = Path.home() / ".ssh" / "id_ed25519_github"
PROJECT = "/srv/lending_pervyi"
LOCAL_ROOT = Path(os.environ.get("LOCAL_BOT_ROOT", "/Users/darya_botova/abhazbereg-bot/lending_pervyi"))


def load_vps_env() -> None:
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


def run(client: paramiko.SSHClient, command: str, *, timeout: int = 600) -> tuple[int, str, str]:
    print(f"\n$ {command}")
    stdin, stdout, stderr = client.exec_command(command, get_pty=True, timeout=timeout)
    del stdin
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip())
    if err.strip() and code != 0:
        print(err.rstrip(), file=sys.stderr)
    return code, out, err


def upload_file(sftp: paramiko.SFTPClient, local: Path, remote: str, mode: int = 0o600) -> None:
    print(f"upload {local.name} -> {remote}")
    sftp.put(str(local), remote)
    sftp.chmod(remote, mode)


def main() -> int:
    if not LOCAL_ROOT.exists():
        print(f"Missing local bot root: {LOCAL_ROOT}", file=sys.stderr)
        return 2
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

    code, out, _ = run(
        client,
        "export DEBIAN_FRONTEND=noninteractive; "
        "apt-get update -y && apt-get install -y git git-lfs python3 python3-venv python3-pip ca-certificates",
        timeout=900,
    )
    if code != 0:
        return code

    run(client, "git lfs install --system || git lfs install")

    code, _, _ = run(client, f"test -d {PROJECT}/.git")
    if code != 0:
        code, _, _ = run(
            client,
            f"git clone https://github.com/Dariatravel/lending_pervyi.git {PROJECT}",
            timeout=900,
        )
        if code != 0:
            return code
    else:
        run(client, f"cd {PROJECT} && git fetch origin && git checkout main && git pull --ff-only origin main")

    run(client, f"cd {PROJECT} && python3 -m venv .venv")
    code, _, _ = run(
        client,
        f"cd {PROJECT} && .venv/bin/pip install -U pip && "
        f".venv/bin/pip install -r requirements-site-update-bot.txt",
        timeout=900,
    )
    if code != 0:
        return code

    run(client, f"cd {PROJECT} && .venv/bin/python scripts/rebuild_from_catalog_snapshot.py")

    deploy_key_path = "/root/.ssh/abhabereg_deploy"
    run(client, "mkdir -p /root/.ssh && chmod 700 /root/.ssh")
    code, _, _ = run(client, f"test -f {deploy_key_path}")
    if code != 0:
        run(
            client,
            f"ssh-keygen -t ed25519 -N '' -f {deploy_key_path} -C 'abhazbereg-site-update-bot'",
        )
    _, pub_out, _ = run(client, f"cat {deploy_key_path}.pub")
    pub_key = pub_key.strip() if (pub_key := pub_out.strip()) else ""
    if not pub_key:
        print("Failed to read deploy public key", file=sys.stderr)
        return 3
    print("\nDEPLOY_PUBLIC_KEY_START")
    print(pub_key)
    print("DEPLOY_PUBLIC_KEY_END")

    sftp = client.open_sftp()
    secrets = [
        (LOCAL_ROOT / ".env.site-update-bot", f"{PROJECT}/.env.site-update-bot"),
        (LOCAL_ROOT / ".env.yandex.local", f"{PROJECT}/.env.yandex.local"),
        (LOCAL_ROOT / "google-service-account.json", f"{PROJECT}/google-service-account.json"),
        (LOCAL_ROOT / "tg_session.session", f"{PROJECT}/tg_session.session"),
    ]
    for local, remote in secrets:
        if not local.exists():
            print(f"Missing secret file: {local}", file=sys.stderr)
            return 4
        upload_file(sftp, local, remote)

    env_text = (LOCAL_ROOT / ".env.site-update-bot").read_text(encoding="utf-8")
    env_text = env_text.replace(
        "TG_SESSION=/Users/darya_botova/abhazbereg-bot/lending_pervyi/tg_session",
        f"TG_SESSION={PROJECT}/tg_session",
    )
    with sftp.open(f"{PROJECT}/.env.site-update-bot", "w") as remote_env:
        remote_env.write(env_text)
    sftp.chmod(f"{PROJECT}/.env.site-update-bot", 0o600)
    sftp.close()

    run(
        client,
        textwrap.dedent(
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
        ).strip(),
    )
    run(client, "systemctl daemon-reload && systemctl enable abhazbereg-site-update-bot")

    ssh_config = textwrap.dedent(
        f"""
        Host github.com
          HostName github.com
          User git
          IdentityFile {deploy_key_path}
          IdentitiesOnly yes
          StrictHostKeyChecking accept-new
        """
    ).strip()
    run(client, f"cat > /root/.ssh/config <<'EOF'\n{ssh_config}\nEOF\nchmod 600 /root/.ssh/config")
    run(client, f"chmod 600 {deploy_key_path} && chmod 644 {deploy_key_path}.pub")
    run(client, f"cd {PROJECT} && git remote set-url origin git@github.com:Dariatravel/lending_pervyi.git")

    client.close()
    print("\nBase VPS setup finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
