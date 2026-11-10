# sns-auto-post

Instagramの自動投稿の仕組みです。

```
毎週（Claudeのルーティン）
  来週分の投稿データを作って、プルリクエストを出す
        ↓
GitHub Actions「スライド画像を作る」
  スライド画像を自動で作ってプルリクエストに追加
        ↓
本人がスマホで確認して「マージ」  ← ここだけ人の作業
        ↓
GitHub Actions「Instagramに投稿」（毎時チェック）
  各アカウントの投稿時間になったら、その日の分を投稿
```

## 最初にやること：トークンの登録

アカウントごとに、Instagramに投稿するための鍵（アクセストークン）をGitHubに登録します。

1. [Meta for Developers](https://developers.facebook.com/apps/) でアプリ「SNS Auto Post」を開く
2. ユースケース →「Instagramでメッセージとコンテンツを管理」→「カスタマイズ」→「API setup with Unified login」
3. 「2. アクセストークンを生成する」で、アカウントの横の「トークンを生成」を押し、表示されたトークンをコピー
4. このリポジトリの Settings → Secrets and variables → Actions →「New repository secret」
5. Name と Secret を入れて「Add secret」

| アカウント | Name |
|---|---|
| @eigo_1phrase | `IG_TOKEN_EIGO_1PHRASE` |
| @gensen_otoku | `IG_TOKEN_GENSEN_OTOKU` |

トークンはパスワードと同じです。ここ以外（チャットやファイル）には貼らないでください。

## 投稿のテスト

Actions →「Instagramに投稿」→「Run workflow」

- mode `dry-run`：投稿せず、次に投稿される内容をログに表示するだけ
- mode `now`：時間に関係なく、キューの一番古い投稿を今すぐ投稿

## 毎週の確認

1. Claudeから「週次投稿」のプルリクエストが届く
2. 各投稿フォルダの `preview.jpg`（全スライドの一覧）と、本文の「確認してほしい点」を見る
3. 直したいところがあれば、プルリクエストにコメントするか、post.json を直接編集する（画像は自動で作り直される）
4. よければ「Merge pull request」を押す。マージした投稿だけが投稿の予定に入ります

## よくある変更

- **投稿時間**：`accounts/<アカウント>.json` の `post_hour_jst`（日本時間の時。7なら7時台に投稿）
- **一時停止**：同じファイルの `enabled` を `false` にする
- **色**：同じファイルの `theme`
- **投稿方針**：`accounts/<アカウント>.md`
- **アカウントの追加**：`accounts/` に設定ファイルと方針を足し、`.github/workflows/publish.yml` の env にトークンの行を足す

## スライドの種類

| layout | 用途 | 主な項目 |
|---|---|---|
| cover | 表紙 | top / ng / bottom / sub |
| callout | よくある間違い・ポイント | label / title / body / note / style（ng か ok） |
| cards | フレーズや項目のカード（1〜3個） | title / cards / note |
| points | 箇条書き（1〜6個） | title / points / note / numbered |
| table | まとめ早見表（1〜6行） | title / rows |
| quiz | 復習クイズ＋フォローの呼びかけ | question / answer / cta |
| cta | コメント募集などの締め | title / body / cta |

見本：[examples/eigo_1phrase](examples/eigo_1phrase)、[examples/gensen_otoku](examples/gensen_otoku)

## 注意

- このリポジトリは公開されています。投稿前の画像や文章も誰でも見られます。トークンは Secrets に保存されるので見えません
- 投稿は1アカウント1日1回まで。投稿済みのものは `posted/` に移り、`published.json` に投稿のURLが残ります

## 手元で動かす（開発用）

```
pip install -r requirements.txt
python -m autopost.validate --examples
python -m autopost.render examples --all
python -m unittest discover -s tests -t .
```
