from __future__ import annotations

import os
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_FILE = BASE_DIR / "cashback-data.json"
SYNC_DEFAULT_DATA_ON_START = (
    os.environ.get("SYNC_DEFAULT_DATA_ON_START", "1").strip().lower() not in {"0", "false", "no"}
)
DATA_FILE = Path(
    os.environ.get(
        "CASHBACK_DATA_FILE",
        str(
            Path(os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", BASE_DIR))
            / "cashback-data.json"
        ),
    )
).resolve()
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8765"))


def read_json_file(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def ensure_data_file() -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not DATA_FILE.exists():
        if DEFAULT_DATA_FILE.exists() and DEFAULT_DATA_FILE.resolve() != DATA_FILE:
            DATA_FILE.write_text(DEFAULT_DATA_FILE.read_text(encoding="utf-8"), encoding="utf-8")
            return

        write_json_file(
            DATA_FILE,
            {
                "version": 1,
                "banks": [],
                "months": {},
            },
        )
        return

    if (
        SYNC_DEFAULT_DATA_ON_START
        and DEFAULT_DATA_FILE.exists()
        and DEFAULT_DATA_FILE.resolve() != DATA_FILE
    ):
        default_payload = read_json_file(DEFAULT_DATA_FILE)
        live_payload = read_json_file(DATA_FILE)
        if default_payload != live_payload:
            write_json_file(DATA_FILE, default_payload)


class CashbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed_path = urlparse(self.path).path

        if parsed_path == "/api/data":
            self._serve_data()
            return

        self._serve_static(parsed_path)

    def do_POST(self) -> None:
        parsed_path = urlparse(self.path).path

        if parsed_path != "/api/data":
            self.send_error(HTTPStatus.NOT_FOUND, "Маршрут не найден")
            return

        self._save_data()

    def log_message(self, format: str, *args) -> None:
        return

    def _serve_data(self) -> None:
        ensure_data_file()
        payload = DATA_FILE.read_text(encoding="utf-8")
        self._send_bytes(
            payload.encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _serve_static(self, raw_path: str) -> None:
        path = "/" if raw_path in ("", "/") else raw_path
        relative = "index.html" if path == "/" else path.lstrip("/")
        target = (BASE_DIR / relative).resolve()

        if BASE_DIR not in target.parents and target != BASE_DIR:
            self.send_error(HTTPStatus.FORBIDDEN, "Доступ запрещен")
            return

        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Файл не найден")
            return

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._send_bytes(target.read_bytes(), content_type)

    def _save_data(self) -> None:
        ensure_data_file()
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Некорректный JSON")
            return

        if not isinstance(payload, dict):
            self.send_error(HTTPStatus.BAD_REQUEST, "Ожидается JSON-объект")
            return

        write_json_file(DATA_FILE, payload)

        self._send_bytes(
            json.dumps({"ok": True}, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _send_bytes(self, payload: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    ensure_data_file()
    server = ThreadingHTTPServer((HOST, PORT), CashbackHandler)
    print(f"Cashback Tracker: http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
