import gzip
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from autopost import research


class FakeClient:
    """business_discovery の返事をまねる（2ページに分かれた投稿）。"""

    def __init__(self):
        self.calls = []

    def _call(self, method, path, params=None, retries=3):
        fields = params["fields"]
        self.calls.append(fields)
        if "nobody" in fields:
            raise research.InstagramError("Invalid user id")
        if "after(" not in fields:
            media = {"data": [{"id": "1", "like_count": 5}, {"id": "2", "like_count": 7}],
                     "paging": {"cursors": {"after": "CUR"}}}
        else:
            media = {"data": [{"id": "3", "like_count": 9}], "paging": {"cursors": {}}}
        return {"business_discovery": {"username": "someone", "followers_count": 100, "media": media}}


class ResearchTest(unittest.TestCase):
    def test_parse_targets(self):
        self.assertEqual(research.parse_targets("@Foo, bar.baz　qux_1\nfoo、bad!name"),
                         ["foo", "bar.baz", "qux_1"])
        self.assertEqual(research.parse_targets("@Foo, foo,bar"), ["foo", "bar"])
        self.assertEqual(research.parse_targets("bad!name"), [])

    def test_collect_pages_and_errors(self):
        result = research.collect(FakeClient(), "123", ["someone", "nobody"], limit=3)
        ok, ng = result["accounts"]
        self.assertTrue(ok["ok"])
        self.assertEqual([m["id"] for m in ok["media"]], ["1", "2", "3"])
        self.assertFalse(ng["ok"])
        self.assertIn("Invalid user id", ng["error"])

    @unittest.skipUnless(shutil.which("openssl"), "openssl がない")
    def test_encrypt_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pub_b64 = research.keygen(tmp / "key")
            import base64
            data = gzip.compress(json.dumps({"hello": "世界"}, ensure_ascii=False).encode())
            research.encrypt(data, base64.b64decode(pub_b64), tmp / "out")
            self.assertNotIn(b"hello", (tmp / "out" / "data.enc").read_bytes())
            back = research.decrypt(tmp / "key" / "priv.pem", tmp / "out")
            self.assertEqual(json.loads(gzip.decompress(back)), {"hello": "世界"})


if __name__ == "__main__":
    unittest.main()
