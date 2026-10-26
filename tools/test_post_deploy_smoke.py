"""Редиректор abhazbereg.com в post_deploy_smoke: одиночный обрыв связи — не тревога.

Запуск: python3 -m unittest tools/test_post_deploy_smoke.py
"""
import io
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parent))
import post_deploy_smoke as smoke  # noqa: E402


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class RedirectorRetryTest(unittest.TestCase):
    def test_one_connection_reset_then_ok(self):
        calls = [URLError(ConnectionResetError(104, "Connection reset by peer")),
                 FakeResponse("<a href='https://абхазберег.рф/'>абхазберег.рф</a>".encode())]

        def fake_urlopen(request, timeout):
            item = calls.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with mock.patch.object(smoke, "urlopen", fake_urlopen), mock.patch.object(smoke.time, "sleep"):
            result, problems = smoke.check_share_domain_redirector(5)
        self.assertEqual(problems, [])
        self.assertEqual(result["status"], 200)

    def test_persistent_failure_still_reported(self):
        def always_down(request, timeout):
            raise URLError(ConnectionResetError(104, "Connection reset by peer"))

        with mock.patch.object(smoke, "urlopen", always_down), mock.patch.object(smoke.time, "sleep"):
            _, problems = smoke.check_share_domain_redirector(5)
        self.assertEqual(len(problems), 1)
        self.assertIn("недоступен", problems[0])


if __name__ == "__main__":
    unittest.main()
