#!/usr/bin/env python3
"""Fix missing VPS deps and generate output/current_pages.json."""
from __future__ import annotations

import os
import sys

import paramiko

HOST = os.environ.get("VPS_HOST", "81.31.247.74")
USER = os.environ.get("VPS_USER", "root")
PASSWORD = os.environ["VPS_PASSWORD"]
PROJECT = "/srv/lending_pervyi"


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

    code = run(client, f"cd {PROJECT} && .venv/bin/pip install Pillow")
    if code != 0:
        return code

    code = run(client, f"cd {PROJECT} && .venv/bin/python scripts/rebuild_from_catalog_snapshot.py", timeout=900)
    if code != 0:
        return code

    code = run(client, f"test -f {PROJECT}/output/current_pages.json")
    if code != 0:
        return code

    run(client, "systemctl restart abhazbereg-site-update-bot")
    run(client, "systemctl is-active abhazbereg-site-update-bot")
    client.close()
    print("\nVPS bot deps fixed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
