"""（再）安いモデル（1K・Lite）で、11/28の第2弾と同じ6つのアイコンを描いて比べる（試し。マージしない）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from autopost import imagegen  # noqa: E402

subjects = ["a kitchen faucet pouring clear water into a glass",
            "a restaurant table setting with a bread basket and a folded napkin",
            "a bank card next to a small piggy bank",
            "a plastic water bottle with a small coin beside it",
            "a red supermarket shopping cart with a coin slot on the handle",
            "small food samples on toothpicks on a tray"]
out = Path(__file__).parent / "cheap"
out.mkdir(exist_ok=True)
imagegen.generate_icons(subjects, [out / f"icon{i}.png" for i in range(1, 7)], style=imagegen.ICON_STYLES["clay"])
