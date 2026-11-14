"""動作確認のテスト。実行: python -m unittest discover -s tests"""
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from autopost import config, posts, publish, templates, validate
from autopost.instagram import Client

ROOT = config.ROOT


class ValidateTest(unittest.TestCase):
    def setUp(self):
        self.accounts = config.load_accounts()

    def test_examples_are_valid(self):
        for path in sorted((ROOT / "examples").glob("*/post.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(validate.validate_post(data, self.accounts), [], path)

    def test_catches_common_mistakes(self):
        data = json.loads((ROOT / "examples/eigo_1phrase/post.json").read_text(encoding="utf-8"))
        data["hashtags"] = ["#a", "#b", "#c", "#d", "#e", "#f"]
        data["caption"] = "答えは明日のストーリーズで #01"
        data["slides"][0]["layout"] = "unknown"
        errors = " ".join(validate.validate_post(data, self.accounts))
        self.assertIn("5個まで", errors)
        self.assertIn("ストーリーズ", errors)
        self.assertIn("# を書かない", errors)
        self.assertIn("unknown", errors)


class TemplateTest(unittest.TestCase):
    def test_escape_keeps_only_allowed_tags(self):
        out = templates.esc('<script>x</script>A<br>B<span class="hl">C</span>\nD')
        self.assertNotIn("<script>", out)
        self.assertIn('<span class="hl">C</span>', out)
        self.assertEqual(out.count("<br>"), 2)

    def test_caption_with_pr_and_tags(self):
        cap = posts.compose_caption({"caption": "本文", "hashtags": ["#a", "#b"], "pr": True})
        self.assertEqual(cap, "【PR】\n本文\n\n#a #b")

    def test_cover_with_big_number_and_badge(self):
        cfg = config.load_accounts()["gensen_otoku"]
        data = json.loads((ROOT / "examples/gensen_otoku/post.json").read_text(encoding="utf-8"))
        html = templates.build_html(data, cfg)
        self.assertIn('class="big"', html)
        self.assertIn('class="badge"', html)
        self.assertIn("<small>円/月</small>", html)
        self.assertIn("厳選お得 #06", html)

    def test_reel_durations(self):
        from autopost import reel

        self.assertEqual(reel.durations(6), [5.0, 5.0, 5.0, 5.0, 6.0, 3.0])
        self.assertLess(reel.HOOK + sum(reel.durations(6)), 35)
        self.assertEqual(reel.default_title({"caption": "一行目\n二行目"}), "一行目")


class DueTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / "accounts", self.root / "accounts")
        self.accounts = config.load_accounts(self.root)
        self.token_env = {"IG_TOKEN_EIGO_1PHRASE": "dummy"}

    def tearDown(self):
        shutil.rmtree(self.root)

    def add_post(self, folder, day):
        d = self.root / "queue" / "eigo_1phrase" / folder
        d.mkdir(parents=True)
        data = json.loads((ROOT / "examples/eigo_1phrase/post.json").read_text(encoding="utf-8"))
        data["date"] = day
        (d / "post.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return d

    def due(self, when, **kw):
        now = datetime.fromisoformat(when).replace(tzinfo=config.JST)
        old = dict(os.environ)
        os.environ.update(self.token_env)
        try:
            return publish.find_due(self.accounts, now, root=self.root, **kw)
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_posts_oldest_due_post_in_window(self):
        self.add_post("2026-11-12-b", "2026-11-12")
        self.add_post("2026-11-11-a", "2026-11-11")
        due = self.due("2026-11-12T07:20")
        self.assertEqual([p.id for _, p in due], ["2026-11-11-a"])

    def test_skips_outside_window_future_and_already_posted(self):
        self.add_post("2026-11-20-x", "2026-11-20")
        self.assertEqual(self.due("2026-11-12T07:20"), [])  # まだ予定日ではない
        self.add_post("2026-11-12-y", "2026-11-12")
        self.assertEqual(self.due("2026-11-12T12:20"), [])  # 時間外
        done = self.root / "posted" / "eigo_1phrase" / "2026-11-11-z"
        done.mkdir(parents=True)
        (done / "published.json").write_text('{"posted_date": "2026-11-12"}', encoding="utf-8")
        self.assertEqual(self.due("2026-11-12T07:20"), [])  # 今日は投稿済み
        self.assertEqual(len(self.due("2026-11-12T12:20", force=True)), 1)  # 手動の今すぐ投稿

    def test_skips_account_without_token(self):
        self.token_env = {}
        self.add_post("2026-11-12-y", "2026-11-12")
        self.assertEqual(self.due("2026-11-12T07:20"), [])


class BoostTest(DueTest):
    """立ち上げ期間（boost）は1日に2回投稿する。"""

    def setUp(self):
        super().setUp()
        self.accounts["eigo_1phrase"]["boost"] = {"until": "2026-11-13", "post_hours_jst": [7, 20],
                                                   "reel_hours_jst": [12, 17]}

    def mark_posted(self, name, day):
        d = self.root / "posted" / "eigo_1phrase" / name
        d.mkdir(parents=True)
        (d / "published.json").write_text(json.dumps({"posted_date": day}), encoding="utf-8")

    def test_two_slots_during_boost_then_one(self):
        self.add_post("2026-11-12-a", "2026-11-12")
        self.add_post("2026-11-12-b", "2026-11-12")
        self.assertEqual(len(self.due("2026-11-12T07:20")), 1)
        self.mark_posted("x1", "2026-11-12")
        self.assertEqual(self.due("2026-11-12T08:20"), [])   # 朝の分は投稿済み
        self.assertEqual(self.due("2026-11-12T15:20"), [])   # 時間外
        self.assertEqual(len(self.due("2026-11-12T20:20")), 1)  # 夜の分
        self.mark_posted("x2", "2026-11-12")
        self.assertEqual(self.due("2026-11-12T21:20"), [])
        # 期間が終わったら、post_hour_jst の1回だけ
        self.assertEqual(self.due("2026-11-14T20:20"), [])
        self.assertEqual(len(self.due("2026-11-14T07:20")), 1)

    def test_reel_slots_during_boost(self):
        cfg = self.accounts["eigo_1phrase"]
        self.assertEqual(publish.daily_slots(cfg, datetime(2026, 11, 13).date(), reel=True)[0], [12, 17])
        self.assertEqual(publish.daily_slots(cfg, datetime(2026, 11, 14).date(), reel=True)[0], [12])


class DelayedReelTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / "accounts", self.root / "accounts")
        self.accounts = config.load_accounts(self.root)

    def tearDown(self):
        shutil.rmtree(self.root)

    def add_posted(self, folder, info):
        d = self.root / "posted" / "eigo_1phrase" / folder
        d.mkdir(parents=True)
        (d / "published.json").write_text(json.dumps(info), encoding="utf-8")
        return d

    def due(self, when, **kw):
        now = datetime.fromisoformat(when).replace(tzinfo=config.JST)
        old = dict(os.environ)
        os.environ.update({"IG_TOKEN_EIGO_1PHRASE": "dummy"})
        try:
            return publish.find_due_reels(self.accounts, now, root=self.root, **kw)
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_accounts_post_reel_next_day_at_noon(self):
        for cfg in self.accounts.values():
            self.assertTrue(publish.reel_delayed(cfg))
            self.assertEqual((cfg["reel"]["delay_days"], cfg["reel"]["post_hour_jst"]), (1, 12))

    def test_pending_reel_is_due_next_day_in_reel_window(self):
        self.add_posted("2026-11-12-a", {"posted_date": "2026-11-12", "reel_status": "pending", "reel_due": "2026-11-13"})
        self.assertEqual(self.due("2026-11-12T12:20"), [])  # まだ翌日ではない
        self.assertEqual(self.due("2026-11-13T07:20"), [])  # リールの時間外
        due = self.due("2026-11-13T12:20")
        self.assertEqual([f.name for _, f in due], ["2026-11-12-a"])

    def test_one_reel_per_day_and_skips_posted_or_failed(self):
        self.add_posted("2026-11-10-x", {"reel_status": "failed", "reel_due": "2026-11-11"})
        self.add_posted("2026-11-11-y", {"reel_status": "posted", "reel_due": "2026-11-12", "reel_posted_date": "2026-11-13"})
        self.add_posted("2026-11-12-z", {"reel_status": "pending", "reel_due": "2026-11-13"})
        self.assertEqual(self.due("2026-11-13T12:20"), [])  # 今日はもう1本投稿済み
        self.assertEqual([f.name for _, f in self.due("2026-11-14T12:20")], ["2026-11-12-z"])
        self.assertEqual(len(self.due("2026-11-13T20:20", force=True)), 1)  # 手動の今すぐ投稿


class InstagramTest(unittest.TestCase):
    def test_carousel_flow(self):
        calls = []

        def fake_call(method, path, params=None, retries=3):
            calls.append((method, path, params))
            if path.endswith("/media") and method == "POST":
                return {"id": f"c{len(calls)}"}
            if path.endswith("/media_publish"):
                return {"id": "media1"}
            return {"status_code": "FINISHED"}

        client = Client("EAAdummy", "123", sleep=lambda s: None)
        self.assertTrue(client.base.startswith("https://graph.facebook.com/"))
        client._call = fake_call
        media_id = client.publish_carousel(["https://x/1.jpg", "https://x/2.jpg"], "cap")
        self.assertEqual(media_id, "media1")
        carousel = [c for c in calls if c[2] and c[2].get("media_type") == "CAROUSEL"][0]
        self.assertEqual(carousel[2]["caption"], "cap")
        self.assertEqual(Client("IGAAdummy", "1").base.split("/")[2], "graph.instagram.com")


if __name__ == "__main__":
    unittest.main()
