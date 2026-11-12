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
        self.assertEqual(base, build.render_hash(dict(self.data, caption="別の文", date="2027-01-01"), self.cfg))
        self.assertNotEqual(base, build.render_hash(dict(self.data, top="別の表紙"), self.cfg))


if __name__ == "__main__":
    unittest.main()
