"""アカウントのアイコンの案を Gemini で描く（試し。マージしない）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from autopost import imagegen  # noqa: E402

BASE = ("Square profile icon for a social media account, centered single subject, bold simple shapes that stay "
        "readable when shown very small as a circle, plain solid background color, no border. ")
ICONS = {
    "money_a": "Cute glossy 3D clay style young Japanese mom with a short bob and an apron, smiling and holding a "
               "big shiny gold coin with both hands, mint green background",
    "money_b": "Cute glossy 3D clay style chubby pink piggy bank character wearing round glasses, winking, a gold "
               "coin popping out of the top, bright sunny yellow background",
    "money_c": "Cute glossy 3D clay style young Japanese dad and a toddler giving a high five, a small gold coin "
               "sparkling between their hands, deep forest green background",
    "eigo_a": "Cute glossy 3D clay style friendly round blue bird mascot with a big empty white speech bubble next "
              "to its beak, sky blue background",
    "eigo_b": "Anime style cheerful young woman teacher with a ponytail, pointing up with one finger, a big empty "
              "white speech bubble beside her, bright coral orange background",
    "eigo_c": "Cute glossy 3D clay style little owl wearing big headphones and a tiny graduation cap, eyes sparkling, "
              "turquoise background",
    "kaigai_a": "Full-color webtoon comic style friendly blond foreign traveler with a backpack giving a big thumbs "
                "up, small Mount Fuji behind him, bold black outlines, bright red background",
    "kaigai_b": "Full-color webtoon comic style cute smiling planet Earth character with little arms hugging a "
                "small Japanese flag, bold black outlines, warm orange background",
    "kaigai_c": "Full-color webtoon comic style close-up of a foreign woman with curly red hair gasping in happy "
                "surprise, hands on cheeks, comic burst lines behind her, bold black outlines, yellow background",
}

out = Path(__file__).parent / "out"
out.mkdir(exist_ok=True)
for name, desc in ICONS.items():
    imagegen.generate(BASE + desc, out / f"{name}.jpg", aspect="1:1", size="1K", kind="icon_full",
                      models=["gemini-3-pro-image", "gemini-nano-banana-2.1"])
