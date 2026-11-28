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
        self.assertIn(">厳選お得<", html)
        self.assertNotIn("#06", html)

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
        # 2026-11-28 からカルーセルの翌日リールは止めている（reel.enabled false）。仕組みのテストでは有効にして確かめる
        for cfg in self.accounts.values():
            cfg["reel"]["enabled"] = True

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


class CoverArtTest(unittest.TestCase):
    def test_art_is_drawn_and_validated(self):
        from autopost import templates, validate, cover_art
        cfg = {"display_handle": "@x", "series": "S",
               "theme": {"main": "#111111", "base": "#eeeeee", "accent": "#aa0000", "accent_soft": "#ffcc00", "muted": "#888888"}}
        for art in cover_art.ARTS:
            html = templates.build_html({"slides": [{"layout": "cover", "top": "T", "art": art}]}, cfg)
            self.assertIn('class="art', html)
            self.assertIn("withart", html)
        errs = []
        validate._check_slide(1, {"layout": "cover", "top": "T", "art": "mario"}, errs)
        self.assertTrue(errs)
        errs = []
        validate._check_slide(1, {"layout": "cover", "top": "T", "art": "food", "art_labels": ["300円", "800円"]}, errs)
        self.assertEqual(errs, [])


class StoryShareTest(unittest.TestCase):
    def test_story_image_and_publish(self):
        import tempfile
        from PIL import Image
        from autopost import story_share
        with tempfile.TemporaryDirectory() as d:
            cover = Path(d) / "slide01.jpg"
            Image.new("RGB", (1080, 1350), "#336699").save(cover)
            out = story_share.make_story_image(cover, Path(d) / "story.jpg", "@x", {"main": "#1d3c32", "accent_soft": "#efc75e"})
            with Image.open(out) as im:
                self.assertEqual(im.size, (1080, 1920))
        self.assertTrue(story_share.wanted({}))
        self.assertFalse(story_share.wanted({"story_share": False}))
        calls = []

        def fake_call(method, path, params=None, retries=3):
            calls.append(params)
            if path.endswith("/media") and method == "POST":
                return {"id": "c1"}
            if path.endswith("/media_publish"):
                return {"id": "s1"}
            return {"status_code": "FINISHED"}

        client = Client("EAAdummy", "123", sleep=lambda s: None)
        client._call = fake_call
        self.assertEqual(client.publish_story_image("https://x/story.jpg"), "s1")
        self.assertEqual(calls[0]["media_type"], "STORIES")


class ReadTimeTest(unittest.TestCase):
    def test_counts_and_seconds(self):
        from autopost import readtime as r
        self.assertEqual(r.count("I'm full."), (0, 2))
        jp, en = r.count("「お腹いっぱい」は？")
        self.assertEqual((jp, en), (7, 0))  # 「お腹いっぱいは」の7字。かっこ・記号は数えない
        self.assertEqual(r.count("60,000円")[0], 3.5)  # 数字は0.5字
        # 12字（2秒）＋ 英語5語（3秒）＋ 目の移動0.8秒
        self.assertAlmostEqual(r.screen_seconds("あいうえおかきくけこさし", "one two three four five"), 5.8)
        self.assertEqual(r.screen_seconds("あ"), r.MIN_SEC)


class QuizReelTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((Path(__file__).parent / "quiz_sample.json").read_text(encoding="utf-8"))

    def test_parse_and_plan(self):
        from autopost import quizreel
        qs, levels, errors = quizreel.parse(self.data)
        self.assertEqual(errors, [])
        self.assertEqual([q["answer"] for q in qs], [1, 0, 2, 1, 0])
        self.assertEqual(qs[0]["choices"][1], "I'm full.")
        self.assertEqual(len(levels), 4)
        screens = quizreel.plan(self.data)
        self.assertEqual([s["kind"] for s in screens], ["question", "answer"] * 3 + ["end"])
        # 問題の画面は「読む時間＋選ぶ間」なので、正解の画面より長い
        self.assertGreater(screens[0]["sec"], screens[1]["sec"])
        self.data["reel_questions"] = [1, 2, 3, 4, 5]
        self.assertTrue(quizreel.plan(self.data)[-1]["full"])

    def test_validate_catches_broken_quiz(self):
        from autopost import quizreel
        self.assertEqual(quizreel.validate(self.data), [])
        broken = json.loads(json.dumps(self.data))
        broken["slides"][6]["rows"] = broken["slides"][6]["rows"][:4]
        broken["reel_questions"] = [6]
        errors = quizreel.validate(broken)
        self.assertTrue(any("Q5" in e for e in errors))
        self.assertTrue(any("reel_questions" in e for e in errors))


class PostedRecentlyTest(unittest.TestCase):
    def test_posted_recently(self):
        from datetime import timedelta
        from autopost import config, publish
        now = config.now_jst()
        fmt = "%Y-%m-%dT%H:%M:%S%z"
        self.assertTrue(publish.posted_recently({"timestamp": (now - timedelta(minutes=20)).strftime(fmt)}, 3))
        self.assertFalse(publish.posted_recently({"timestamp": (now - timedelta(hours=5)).strftime(fmt)}, 3))
        self.assertFalse(publish.posted_recently({}, 3))


class ReelOnlyTest(unittest.TestCase):
    def test_validate_and_schedule(self):
        import shutil, tempfile
        from datetime import datetime
        from autopost import config, posts, publish, validate
        data = json.loads((Path(__file__).parent / "matome_sample.json").read_text(encoding="utf-8"))
        accounts = config.load_accounts()
        self.assertEqual(validate.validate_post(data, accounts), [])
        bad = dict(data, post_hour_jst=None)
        self.assertTrue(validate.validate_post(bad, accounts))
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            q = root / "queue" / "gensen_otoku"
            (q / "2026-11-21-a").mkdir(parents=True)
            (q / "2026-11-21-a" / "post.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tz = config.now_jst().tzinfo
            cfg = {"gensen_otoku": dict(accounts["gensen_otoku"])}
            early = datetime(2026, 11, 21, 18, 30, tzinfo=tz)
            late = datetime(2026, 11, 21, 19, 20, tzinfo=tz)
            # 時刻前は出さない（トークンの確認だけ差しかえて確かめる）
            orig = config.get_token
            config.get_token = lambda c: "x"
            try:
                self.assertEqual(publish.find_due_reel_only(cfg, early, root=root), [])
                self.assertEqual(len(publish.find_due_reel_only(cfg, late, root=root)), 1)
            finally:
                config.get_token = orig
            # 通常の投稿の順番には入らない
            self.assertIsNone(posts.next_post("gensen_otoku", late.date(), root))


class PopTest(unittest.TestCase):
    """にぎやかな1枚まとめ（pop / tiles / tier）と、その絵（art / imagegen）。"""

    def setUp(self):
        self.accounts = config.load_accounts()
        self.cfg = self.accounts["eigo_1phrase"]

    def _post(self, slide):
        return {"account": "eigo_1phrase", "date": "2026-11-29", "type": "reel_only", "post_hour_jst": 18,
                "slides": [slide], "caption": "テスト", "hashtags": []}

    def _pop(self, n=6):
        return {"layout": "pop", "title": "英語で出てこない<br>ひと言10選",
                "items": [{"left": f"日本語{i}", "right": "No way!", "right_sub": "ノー ウェイ",
                           "icon": "a surprised little character"} for i in range(n)]}

    def test_validate_pop_tiles_tier(self):
        self.assertEqual(validate.validate_post(self._post(self._pop()), self.accounts), [])
        tiles = {"layout": "tiles", "title": "日本では無料", "cols": 3, "summary": {"label": "合計", "big": "0円"},
                 "tiles": [{"label": "お冷や", "icon": "a glass of water", "a": "日本：無料", "b": "海外：有料"}] * 6}
        self.assertEqual(validate.validate_post(self._post(tiles), self.accounts), [])
        tier = {"layout": "tier", "title": "Tier表",
                "tiers": [{"rank": r, "items": [{"name": "温水便座", "icon": "a toilet"}]} for r in "SABC"]}
        self.assertEqual(validate.validate_post(self._post(tier), self.accounts), [])
        bad = self._pop(3)
        bad["items"][0]["icon"] = "日本語の説明"
        bad["items"][1]["left"] = "とても長い日本語の言い方がここに入ります"
        errors = " ".join(validate.validate_post(self._post(bad), self.accounts))
        self.assertIn("5〜12行", errors)
        self.assertIn("英語の短い説明", errors)
        self.assertIn("長すぎます", errors)
        carousel = self._post(self._pop())
        carousel["type"] = "carousel"
        carousel["slides"].append({"layout": "cta", "title": "x"})
        self.assertIn("reel_only", " ".join(validate.validate_post(carousel, self.accounts)))

    def test_html_number_and_missing_art(self):
        html = templates.build_html(self._post(self._pop()), self.cfg)
        self.assertIn('<span class="ppnum">10</span>選', html)
        self.assertIn("フォローで", html)
        self.assertNotIn("data:image", html.split("<body>")[1][:100])

    def test_art_paths_rotation_and_state(self):
        from autopost import art

        self.assertEqual(art.slug("A Cup of Coffee"), art.slug("a cup  of coffee"))
        self.assertTrue(art.slug("a cup of coffee").startswith("a-cup-of-coffee-"))
        data = self._post(self._pop())
        icons, bgs = art.wanted(data, self.cfg)
        self.assertEqual(icons, ["a surprised little character"])
        self.assertEqual(len(bgs), 1)  # 背景は accounts の art.backgrounds から日替わり
        data2 = json.loads(json.dumps(data))
        data2["date"] = "2026-11-30"
        self.assertNotEqual(art.wanted(data2, self.cfg)[1], bgs)
        with tempfile.TemporaryDirectory() as tmp:
            old = art.ASSETS
            art.ASSETS = Path(tmp)
            try:
                self.assertEqual(art.state(data, self.cfg), [])
                p = art.icon_path(icons[0], self.cfg)
                p.parent.mkdir(parents=True)
                p.write_bytes(b"x")
                self.assertEqual(art.state(data, self.cfg), [p.name])
                h1 = posts.render_hash(data, self.cfg)
                p.unlink()
                self.assertNotEqual(posts.render_hash(data, self.cfg), h1)  # 絵ができたら作り直す
                self.assertEqual(art.ensure([(data, self.cfg)], log=lambda *a: None), 0)  # キーが無いときは何もしない
            finally:
                art.ASSETS = old

    def test_slice_sheet(self):
        from PIL import Image, ImageDraw

        from autopost import imagegen

        with tempfile.TemporaryDirectory() as tmp:
            sheet = Path(tmp) / "sheet.jpg"
            im = Image.new("RGB", (900, 600), "white")
            d = ImageDraw.Draw(im)
            for i in range(5):  # 3列×2行に5個（最後のマスは空）
                r, c = divmod(i, 3)
                d.ellipse((c * 300 + 90, r * 300 + 90, c * 300 + 210, r * 300 + 210), fill=(200, 80 + i * 20, 60))
            im.save(sheet)
            pieces = imagegen.slice_sheet(sheet, 5, 3, 2)
            self.assertEqual(len(pieces), 5)
            self.assertTrue(all(p is not None and p.size == (360, 360) for p in pieces))
            self.assertEqual(imagegen.grid_for(5), (3, 2, "3:2"))
            self.assertEqual(imagegen.grid_for(10), (4, 3, "4:3"))

    def test_still_seconds_two_days_each(self):
        from datetime import date

        from autopost import reel

        cfg = {"reel_only_seconds": [5, 7]}
        got = [reel.still_seconds(cfg, date(2026, 11, d)) for d in range(24, 30)]
        self.assertEqual(got, [5, 5, 7, 7, 5, 5])
        self.assertEqual(reel.still_seconds({}, date(2026, 11, 24)), 7.0)


class MusicTest(unittest.TestCase):
    def test_pick_is_stable_and_falls_back(self):
        from autopost import music

        old_file, old_env = music.TRACKS_FILE, os.environ.get("MUSIC_CACHE")
        with tempfile.TemporaryDirectory() as tmp:
            try:
                music.TRACKS_FILE = Path(tmp) / "tracks.json"
                os.environ["MUSIC_CACHE"] = str(Path(tmp) / "cache")
                self.assertIsNone(music.pick("2026-11-29-x"))  # 一覧が無ければ自作のBGM
                music.TRACKS_FILE.write_text(json.dumps({"tracks": [
                    {"id": "a", "url": "https://example.com/a.mp3", "moods": ["bright"]},
                    {"id": "b", "url": "https://example.com/b.mp3", "moods": ["calm"]}]}), encoding="utf-8")
                self.assertIsNone(music.pick("2026-11-29-x"))  # まだダウンロードしていない
                (Path(tmp) / "cache").mkdir()
                for t in ("a", "b"):
                    (Path(tmp) / "cache" / f"{t}.mp3").write_bytes(b"0" * 60_000)
                first = music.pick("2026-11-29-x")["id"]
                self.assertEqual(music.pick("2026-11-29-x")["id"], first)
                self.assertEqual(music.pick("x", mood="calm")["id"], "b")
            finally:
                music.TRACKS_FILE = old_file
                if old_env is None:
                    os.environ.pop("MUSIC_CACHE", None)
                else:
                    os.environ["MUSIC_CACHE"] = old_env


class ComicTest(unittest.TestCase):
    """海外反応の漫画（Gemini で描いた6コマ）。"""

    def setUp(self):
        self.accounts = config.load_accounts()
        self.data = json.loads((ROOT / "examples/kaigai_hokkori/post.json").read_text(encoding="utf-8"))
        self.data["art"] = {"cast": "Emma: a cheerful American woman with wavy blonde hair and a green sweater",
                            "cover": "Emma gasps in surprise at a ticket counter", "end": "Emma waves goodbye, smiling"}
        for i, sc in enumerate(self.data["scenes"]):
            sc["art"] = f"Emma on the right in scene {i + 1}"
            sc.pop("say_side", None)

    def test_validate(self):
        from autopost import art

        self.assertEqual(validate.validate_post(self.data, self.accounts), [])
        self.assertEqual(len(art.story_panels_wanted(self.data)), 6)
        bad = json.loads(json.dumps(self.data))
        bad["scenes"][1]["art"] = "日本語の説明"
        bad["scenes"][2]["say_side"] = "up"
        del bad["art"]["end"]
        errors = " ".join(validate.validate_post(bad, self.accounts))
        self.assertIn("cast", errors)
        self.assertIn("場面2: art", errors)
        self.assertIn("say_side", errors)
        self.assertIsNone(art.story_panels_wanted(bad))
        plain = json.loads(json.dumps(self.data))
        del plain["art"]
        for sc in plain["scenes"]:
            del sc["art"]
        self.assertEqual(validate.validate_post(plain, self.accounts), [])
        self.assertEqual(art.story_paths(plain), [])  # art が無ければ今までの絵

    def test_slice_grid(self):
        from PIL import Image, ImageDraw

        from autopost import imagegen

        def sheet(cols, rows, path):
            im = Image.new("RGB", (1200, 1200), "white")
            d = ImageDraw.Draw(im)
            g, m = 30, 20
            pw, ph = (1200 - 2 * m - (cols - 1) * g) / cols, (1200 - 2 * m - (rows - 1) * g) / rows
            for r in range(rows):
                for c in range(cols):
                    x0, y0 = m + c * (pw + g), m + r * (ph + g)
                    d.rectangle([x0, y0, x0 + pw, y0 + ph], fill=(90 + 30 * c, 120, 60 + 40 * r), outline="black", width=5)
            im.save(path)

        with tempfile.TemporaryDirectory() as tmp:
            sheet(2, 3, Path(tmp) / "ok.png")
            sheet(3, 2, Path(tmp) / "ng.png")
            pieces = imagegen.slice_grid(Path(tmp) / "ok.png", 2, 3)
            self.assertEqual(len(pieces), 6)
            self.assertTrue(all(1.3 < p.width / p.height < 1.7 for p in pieces))
            self.assertEqual(imagegen.slice_grid(Path(tmp) / "ng.png", 2, 3), [])  # コマ割りが違えば失敗

    def test_design_uses_panels(self):
        from autopost.story import design

        cfg = self.accounts["kaigai_hokkori"]
        panels = [f"data:image/jpeg;base64,P{i}" for i in range(6)]
        html = design.carousel(self.data, cfg["name"], "@x", panels)
        self.assertEqual(html.count('class="p stage art"'), 4)
        self.assertIn("P0", html)
        self.assertIn("P5", html)
        self.assertNotIn("stage art", design.carousel(self.data, cfg["name"], "@x", []))
        reel = self.data | {"comments": self.data["reel_script"]["comments"]}
        self.assertEqual(design.reel_pages(reel, cfg["name"], "@x", "", panels).count('class="p stage art"'), 4)


class PodiumTest(unittest.TestCase):
    def test_podium(self):
        from autopost import art

        accounts = config.load_accounts()
        data = json.loads((ROOT / "queue/kaigai_hokkori/2026-11-25-prefecture-ranking/post.json").read_text(encoding="utf-8")) \
            if (ROOT / "queue/kaigai_hokkori/2026-11-25-prefecture-ranking/post.json").exists() else None
        if data is None:
            self.skipTest("サンプルの投稿がありません")
        self.assertEqual(validate.validate_post(data, accounts), [])
        self.assertEqual(len(art.icons_of(data["slides"][0])), len(data["slides"][0]["items"]))
        bad = json.loads(json.dumps(data))
        bad["slides"][0]["items"][0]["num"] = 1
        self.assertIn("num の大きい順", " ".join(validate.validate_post(bad, accounts)))


class TreeTest(unittest.TestCase):
    def test_tree(self):
        from autopost import templates

        accounts = config.load_accounts()
        f = ROOT / "queue/gensen_otoku/2026-11-25-education-tree/post.json"
        if not f.exists():
            self.skipTest("サンプルの投稿がありません")
        data = json.loads(f.read_text(encoding="utf-8"))
        self.assertEqual(validate.validate_post(data, accounts), [])
        bad = json.loads(json.dumps(data))
        bad["slides"][0]["routes"].reverse()
        self.assertIn("線が交差しない", " ".join(validate.validate_post(bad, accounts)))


class OpenerTest(unittest.TestCase):
    def test_opener_triggers_render(self):
        from autopost.story import build

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertEqual(build.opener_digest(folder), "")
            (folder / "opener.mp4").write_bytes(b"video")
            self.assertEqual(len(build.opener_digest(folder)), 16)
