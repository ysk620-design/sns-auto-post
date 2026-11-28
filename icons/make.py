"""新しい2アカウントのアイコン案（虚構図鑑のキャラ3案・シゴトの差2案）。試し。マージしない。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from autopost import imagegen  # noqa: E402

ICON = ("Profile icon for social media: one character, large and centered, filling most of the square, readable at a "
        "tiny size, bold clean shapes, high quality illustration, plain solid background color.")
jobs = {
    "zukan_a": "A cute but slightly eerie monster that is an old leather-bound encyclopedia book: the front cover has "
               "one big round eye, the pages flap like little wings, tiny legs, holding a feather quill. "
               "Vintage storybook illustration with ink lines and soft watercolor. Solid deep red background.",
    "zukan_b": "A cute tapir-like dream eater creature (baku) wearing tiny round glasses, hugging an old open "
               "encyclopedia and nibbling a paper speech bubble. Vintage storybook illustration with ink lines and "
               "soft watercolor. Solid mustard yellow background.",
    "zukan_c": "A round black fluffy furball creature with two big glowing yellow eyes, peeking out from between the "
               "pages of an old open encyclopedia. Vintage storybook illustration with ink lines and soft watercolor. "
               "Solid parchment beige background.",
    "shigoto_a": "A young Japanese office worker with short black hair and a navy suit, upper body, confident smile, "
                 "pointing up with one finger. Cute 3D clay render, soft studio lighting. Solid bright orange background.",
    "shigoto_b": "A young Japanese office worker with short black hair and a navy suit, upper body, confident smile, "
                 "pointing up with one finger. Flat vector illustration, bold simple shapes. Solid bright orange background.",
}
out = Path(__file__).parent / "new"
out.mkdir(exist_ok=True)
for name, desc in jobs.items():
    imagegen.generate(f"{desc} {ICON}", out / f"{name}.jpg", aspect="1:1", size="1K", kind="comic")
