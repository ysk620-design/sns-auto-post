"""ほかのアカウント（ビジネス／クリエイター）の公開データを集めて、暗号化して渡す。

Instagram の「ビジネス発見」の仕組みで、フォロワー数と、投稿ごとのいいね数・コメント数・
日時・種類・キャプションを取る。再生数や保存数など、本人しか見られない数字は取れない。
個人アカウントのデータも取れない。

公開リポジトリなので、調べたアカウント名や数字は、ログにもリポジトリにも読める形で残さない。
- 調べるアカウントと公開鍵は、ワークフローを実行するときの入力で渡す（ログには出ない）
- 結果は渡された公開鍵で暗号化して、research-data ブランチに置く（毎回上書き）
- 読めるのは、秘密鍵を持っている人（調査を頼んだ Claude）だけ

使い方（Claude 側）:
  1. python -m autopost.research keygen /tmp/research-key
     → 鍵を作り、公開鍵（base64）を表示する。秘密鍵はコミットしない
  2. GitHub Actions の「他アカウント調査」（research.yml）を実行する
     入力：targets（ユーザーネームをカンマ区切り）、pubkey（1の公開鍵）、request_id（任意の英数字）
  3. research-data ブランチの meta.json・key.enc・data.enc を取り出して
     python -m autopost.research decrypt /tmp/research-key <取り出したフォルダ>
     → 集めたデータ（JSON）を表示する

結果をもとに書く投稿方針などには、ほかのアカウントの名前やキャプションを書き写さない。
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from . import config
from .instagram import Client, InstagramError

PROFILE_FIELDS = "username,name,biography,followers_count,follows_count,media_count"
MEDIA_FIELDS = "timestamp,media_type,media_product_type,like_count,comments_count,caption,permalink"
MAX_TARGETS = 30
OAEP = ["-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256"]
CIPHER = ["-aes-256-cbc", "-pbkdf2", "-iter", "100000"]


def _openssl(*args: str) -> None:
    subprocess.run(["openssl", *args], check=True, capture_output=True)


# ---------- 鍵と暗号化 ----------

def keygen(key_dir: Path) -> str:
    key_dir.mkdir(parents=True, exist_ok=True)
    priv, pub = key_dir / "priv.pem", key_dir / "pub.pem"
    _openssl("genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:3072", "-out", str(priv))
    os.chmod(priv, 0o600)
    _openssl("pkey", "-in", str(priv), "-pubout", "-out", str(pub))
    return base64.b64encode(pub.read_bytes()).decode()


def encrypt(data: bytes, pub_pem: bytes, out_dir: Path) -> None:
    """data を AES で暗号化し、その鍵を公開鍵（RSA-OAEP）で暗号化する。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "pub.pem").write_bytes(pub_pem)
        (tmp / "key.txt").write_text(secrets.token_hex(32))
        (tmp / "data.bin").write_bytes(data)
        _openssl("pkeyutl", "-encrypt", "-pubin", "-inkey", str(tmp / "pub.pem"), *OAEP,
                 "-in", str(tmp / "key.txt"), "-out", str(out_dir / "key.enc"))
        _openssl("enc", *CIPHER, "-salt", "-in", str(tmp / "data.bin"),
                 "-out", str(out_dir / "data.enc"), "-pass", f"file:{tmp / 'key.txt'}")


def decrypt(priv_pem: Path, in_dir: Path) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _openssl("pkeyutl", "-decrypt", "-inkey", str(priv_pem), *OAEP,
                 "-in", str(in_dir / "key.enc"), "-out", str(tmp / "key.txt"))
        _openssl("enc", "-d", *CIPHER, "-in", str(in_dir / "data.enc"),
                 "-out", str(tmp / "data.bin"), "-pass", f"file:{tmp / 'key.txt'}")
        return (tmp / "data.bin").read_bytes()


# ---------- データ集め ----------

def parse_targets(text: str) -> list[str]:
    names = []
    for raw in re.split(r"[\s,、]+", text or ""):
        name = raw.strip().lstrip("@").lower()
        if re.fullmatch(r"[a-z0-9._]{1,30}", name) and name not in names:
            names.append(name)
    return names[:MAX_TARGETS]


def fetch_account(client: Client, ig_user_id: str, username: str, limit: int) -> dict:
    profile: dict | None = None
    media: list[dict] = []
    after = None
    while len(media) < limit:
        n = min(50, limit - len(media))
        edge = f"media.after({after}).limit({n})" if after else f"media.limit({n})"
        fields = f"business_discovery.username({username}){{{PROFILE_FIELDS},{edge}{{{MEDIA_FIELDS}}}}}"
        bd = client._call("GET", ig_user_id, {"fields": fields}).get("business_discovery") or {}
        if profile is None:
            profile = {k: bd.get(k) for k in PROFILE_FIELDS.split(",")}
        page = bd.get("media") or {}
        items = page.get("data") or []
        media.extend(items)
        after = ((page.get("paging") or {}).get("cursors") or {}).get("after")
        if not items or not after:
            break
    profile = profile or {"username": username}
    profile["media"] = media[:limit]
    return profile


def collect(client: Client, ig_user_id: str, usernames: list[str], limit: int) -> dict:
    accounts = []
    for name in usernames:
        try:
            accounts.append({"ok": True, **fetch_account(client, ig_user_id, name, limit)})
        except InstagramError as e:
            accounts.append({"ok": False, "username": name, "error": str(e)[:300]})
    return {"fetched_at": config.now_jst().isoformat(timespec="seconds"), "accounts": accounts}


def _event_inputs() -> dict:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8")).get("inputs") or {}
    return {}


def run_collect(out_dir: Path) -> int:
    inputs = _event_inputs()
    usernames = parse_targets(inputs.get("targets", ""))
    pub_pem = base64.b64decode(inputs.get("pubkey", "") or b"")
    if not usernames or b"PUBLIC KEY" not in pub_pem:
        print("::error::targets（ユーザーネーム）と pubkey（公開鍵）を入力してください")
        return 1
    limit = max(1, min(int(inputs.get("limit") or 50), 200))
    cfg = next((c for c in config.load_accounts().values() if config.get_token(c)), None)
    if not cfg:
        print("::error::トークンが登録されているアカウントがありません")
        return 1
    client = Client(config.get_token(cfg), cfg["ig_user_id"])
    result = collect(client, cfg["ig_user_id"], usernames, limit)
    encrypt(gzip.compress(json.dumps(result, ensure_ascii=False).encode()), pub_pem, out_dir)
    ok = sum(1 for a in result["accounts"] if a["ok"])
    meta = {
        "request_id": re.sub(r"[^A-Za-z0-9_-]", "", str(inputs.get("request_id") or ""))[:40],
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "total": len(usernames),
        "ok": ok,
        "pubkey_sha256": hashlib.sha256(pub_pem).hexdigest(),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    # ログには件数だけを出す（アカウント名や数字は出さない）
    print(f"::notice title=他アカウント調査::{len(usernames)}件中 {ok}件のデータを暗号化しました")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "keygen":
        print(keygen(Path(argv[1])))
        return 0
    if len(argv) >= 2 and argv[0] == "collect":
        return run_collect(Path(argv[1]))
    if len(argv) >= 3 and argv[0] == "decrypt":
        data = decrypt(Path(argv[1]) / "priv.pem", Path(argv[2]))
        sys.stdout.write(gzip.decompress(data).decode())
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
