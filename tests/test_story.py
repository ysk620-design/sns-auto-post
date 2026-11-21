import copy
import json
import unittest
from pathlib import Path

from autopost import config, posts, story, validate
from autopost.story import build, design

ROOT = Path(__file__).resolve().parent.parent


class StoryTest(unittest.TestCase):
    def setUp(self):
        self.accounts = config.load_accounts(ROOT)
        self.cfg = self.accounts["kaigai_hokkori"]
        self.data = json.loads((ROOT / "examples/kaigai_hokkori/post.json").read_text(encoding="utf-8"))

    def test_example_is_valid_story(self):
        self.assertTrue(story.is_story(self.data))
        self.assertEqual(validate.validate_post(self.data, self.accounts), [])

    def test_catches_story_mistakes(self):
        bad = copy.deepcopy(self.data)
        bad["icon"] = "dragon"
        bad["scenes"] = bad["scenes"][:3]
        bad["reel_script"]["nar"] = bad["reel_script"]["nar"][:9]
        bad["comments"][0][2] = "<b>太字</b>"
        bad["sources"] = []
        errors = "\n".join(validate.validate_post(bad, self.accounts))
        for word in ("icon", "scenes", "nar", "<br>", "sources"):
            self.assertIn(word, errors)

    def test_story_only_for_story_accounts(self):
        other = dict(self.data, account="eigo_1phrase")
        self.assertTrue(any("story" in e for e in validate.validate_post(other, self.accounts)))

    def test_all_icons_and_pages_build(self):
        for name in story.ICONS:
            self.assertIn("<svg", design.icon(name, 100))
        html = design.carousel(self.data, self.cfg["name"], self.cfg["display_handle"])
        self.assertEqual(html.count("<section"), 1 + 4 + 2 + 2)
        reel = dict(self.data, comments=self.data["reel_script"]["comments"])
        pages = design.reel_pages(reel, self.cfg["name"], self.cfg["display_handle"], "クレジット")
        self.assertEqual(pages.count("<section"), len(self.data["reel_script"]["nar"]))
        self.assertIn("クレジット", pages)

    def test_reel_caption_gets_voice_credit(self):
        caption = posts.compose_reel_caption(self.data, self.cfg)
        self.assertTrue(caption.endswith("VOICEVOX:冥鳴ひまり"))
        self.assertEqual(posts.compose_reel_caption(self.data, self.accounts["eigo_1phrase"]),
                         posts.compose_caption(self.data))

    def test_render_hash_ignores_caption_but_not_story(self):
        base = build.render_hash(self.data, self.cfg)
        self.assertEqual(base, build.render_hash(dict(self.data, caption="別の文"), self.cfg))
        self.assertNotEqual(base, build.render_hash(dict(self.data, top="別の表紙"), self.cfg))
        self.assertNotEqual(base, build.render_hash(dict(self.data, color="purple" if design.palette_name(self.data) != "purple" else "green"), self.cfg))

    def test_palette_rotates_by_date_and_can_be_fixed(self):
        names = {design.palette_name({"date": f"2026-12-0{d}"}) for d in range(1, 6)}
        self.assertEqual(names, set(design.PALETTES))
        self.assertEqual(design.palette_name({"date": "2026-12-01", "color": "teal"}), "teal")
        html = design.carousel(dict(self.data, color="green"), "n", "@h")
        self.assertIn("#16a86c", html)
        self.assertNotIn("#ff4a3d 0 6deg", html)
        self.assertEqual(len(design.reel_motion(self.data)), 1 + len(self.data["scenes"]) + len(self.data["comments"]) + 2)


if __name__ == "__main__":
    unittest.main()


class CommentReelTest(unittest.TestCase):
    def test_items_prefer_unused_and_resolve_names(self):
        from autopost.story import design
        p = {"title": "テスト", "chat_title": "x",
             "comments": [["🇺🇸", "米国の母親（記事より）", "こんなの初めて見た"], ["🇺🇸", "同じ母親", "子どもも大喜び"],
                          ["🇬🇧", "英国の旅行者", "信じられない"], ["🇫🇷", "フランスの学生", "日本に住みたい"]],
             "reel_script": {"comments": [["🇺🇸", "米国の母親", "こんなの初めて見た"]], "nar": []}}
        items = design.comment_reel_items(p)
        self.assertEqual([c[2] for c in items], ["子どもも大喜び", "信じられない", "日本に住みたい"])
        self.assertEqual(items[0][1], "米国の母親")  # 「同じ母親」を元の呼び方に
        script = design.comment_reel_script(p)
        self.assertEqual(len(script), len(items) + 2)
        self.assertTrue(script[0].startswith("テスト"))
        self.assertEqual(len(design.comment_reel_motion(p)), len(items) + 2)

    def test_due_reel2(self):
        import json as _json, tempfile
        from datetime import datetime
        from pathlib import Path
        from autopost import config, publish
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            f = root / "posted" / "kaigai_hokkori" / "2026-11-22-a"
            f.mkdir(parents=True)
            (f / "published.json").write_text(_json.dumps({"reel2_status": "pending", "reel2_due": "2026-11-24"}))
            cfg = {"kaigai_hokkori": {"handle": "kaigai_hokkori", "enabled": True,
                                      "reel2": {"enabled": True, "post_hour_jst": 18, "post_window_hours": 3}}}
            tz = config.now_jst().tzinfo
            orig = config.get_token
            config.get_token = lambda c: "x"
            try:
                self.assertEqual(publish.find_due_reel2(cfg, datetime(2026, 11, 24, 12, tzinfo=tz), root=root), [])
                self.assertEqual(publish.find_due_reel2(cfg, datetime(2026, 11, 23, 19, tzinfo=tz), root=root), [])
                self.assertEqual(len(publish.find_due_reel2(cfg, datetime(2026, 11, 24, 18, 20, tzinfo=tz), root=root)), 1)
            finally:
                config.get_token = orig
