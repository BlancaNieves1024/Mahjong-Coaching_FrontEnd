# 麻雀牌譜検討アプリ（v2） 起動方法

Flask製のアプリ（`app.py`）を起動し、ブラウザで牌譜検討の結果画面を確認する手順。

## 1. 必要なもの

| 項目 | 内容 |
|---|---|
| Python | 3.9以上を推奨（動作確認は Python 3.12） |
| パッケージ | `flask`（動作確認は Flask 3.1） |
| ブラウザ | Chrome など（牌の表示にSVGを使う） |

外部サイトへの通信は不要。画面の牌はHTML内のSVGで描画する。

## 2. ファイルの配置

リポジトリ内の関係するファイル:

```
Mahjong-Coaching_FrontEnd/
├ requirements.txt                       ← 依存パッケージ（flask / beautifulsoup4 / jinja2 / lxml）
├ docs/api/ai-input-format.md            ← バックエンドとのJSON仕様
├ shared/samples/
│   └ ai_input_sample_east1.json         ← 仕様どおりの完全な形のサンプル（東1局・18局面）
└ apps/v2/
    ├ app.py
    ├ data/
    │   ├ dummy_backend_response.json    ← ダミーのバックエンド返り値（Akochanの実出力から作成。半荘・6局・63局面。入力JSON仕様と同じ入れ子の形式）
    │   ├ sample_render_data.json        ← 画面に渡すJSON（data.json）のサンプル。テンプレートだけを触るとき用
    │   └ archive/                       ← 旧形式のデータ（参照用）
    ├ templates/
    │   ├ index.html                     ← 入力画面
    │   ├ error.html                     ← エラー画面
    │   └ result_manyhands.html          ← 結果画面
    └ tools/
        ├ build_ai_input.py                  ← Akochanのレポート(HTML)から、入力JSONを作る。ダミーの再生成にも使う
        └ reconstruct_table_state.py         ← 上のスクリプトが使う、河・副露・他家の手牌の復元
```

- `app.py` は `apps/v2/` で起動する。ダミーは `apps/v2/data/` から読む。
- HTMLは `templates` フォルダに置く（Flaskの決まり）。
- `index.html` のフォームは、次の条件を満たすこと。
  - 送信先: `/analyze`、方式: `POST`
  - ファイルを送る場合: `enctype="multipart/form-data"`
  - 項目名: `input_data`（テキスト）、`file`（ファイル）、`seat`（自家の席 0〜3）

## 3. 起動手順

### 3-1. 仮想環境を作る（初回のみ・推奨）

macOS / Linux:

```
cd Mahjong-Coaching_FrontEnd        # リポジトリのルート
python3 -m venv .venv
source .venv/bin/activate
```

Windows（PowerShell）:

```
cd Mahjong-Coaching_FrontEnd        # リポジトリのルート
py -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3-2. パッケージを入れる（初回のみ）

リポジトリのルートで実行する。

```
pip install -r requirements.txt
```

### 3-3. 起動する

```
cd apps/v2
python app.py
```

ターミナルに次のように出れば起動している。

```
 * Running on http://127.0.0.1:8080
```

ブラウザで `http://127.0.0.1:8080/` を開く。

### 3-4. 終了する

ターミナルで `Ctrl + C`。

## 4. 動作確認

### 4-1. ダミー（半荘・6局）を表示する

1. `http://127.0.0.1:8080/` を開く。
2. テキスト欄に `https://example.com` と入力して送信する。ファイルを選んで送信しても、同じダミーが出る。
3. 次のとおり表示されれば正常。

| 見る場所 | 期待する表示 |
|---|---|
| 目次 | 東1局、東1局 1本場、東1局 2本場、東2局、東2局 1本場、東2局 2本場（6局） |
| メタデータ | 局数 6／局面数 63／AI一致率 33/63 = 52.381%／注意局面 17/63 |
| 東1局 2本場 0巡目 | 「期待値差を算出できませんでした」（Akochanが評価できなかった局面） |
| 東1局 2本場 3巡目 | プレイヤー「大明槓 西」、AI「スルー」、期待値差 2.17907。手牌の右に、白のポンが見える |
| 東2局 14巡目・15巡目 | 14巡目はプレイヤーもAIも「加槓 南」。15巡目は、副露の南が4枚（鳴いた牌の上に重ねて表示） |
| 東2局 2本場 2巡目 | プレイヤーもAIも「打 4s 立直」 |
| 各局面の手牌の下 | 4人の河（自分・下家・対面・上家）。1段に6枚。横向きの牌は立直宣言牌、薄い牌は鳴かれた牌、牌の下の青い線はツモ切り（ページ上部に凡例） |

### 4-2. バックエンドのJSONを貼り付けて表示する

テキスト欄にJSONを貼って送信すると、それをバックエンドの返り値として表示する。形式は、入力JSON仕様（`ai-input-format.md`）と同じ。次は、画面に必要な項目だけの最小の例。

```json
{
  "meta": {"kyoku": "東1局", "honba": 0},
  "situation": {"turn": 8, "trigger": "draw", "trigger_actor": "自分", "trigger_tile": "1s"},
  "self": {
    "hand_with_trigger_tile": ["4m","6m","9p","9p","3s","3s","4s","4s","5sr","7s","8s","8s","c","1s"],
    "melds": []
  },
  "decision": {
    "player_choice": {"type": "discard", "tile": "6m"},
    "ai_choice": {"type": "discard", "tile": "1s"},
    "loss": 5.31
  },
  "commentary": "ここにAIからのコメントが入ります。"
}
```

- 8巡目が1件表示され、⚠️・期待値差 5.31000・コメントが出れば正常。
- 複数巡目は、同じ形式のオブジェクトを `[ ... , ... ]` の配列にして貼る。
- 各家の河（`self.river`、`others.*.river`）は読んで、画面に出す。河が無いJSON（上の最小の例）では、河の欄が出ない。`others` の河以外、`hidden_info`、`decision.candidates` などは、あっても読まない。仕様どおりの完全な形（東1局・自分の席0・18局面）は `shared/samples/ai_input_sample_east1.json` にあり、ファイルの中身をそのまま貼って確認できる（注意局面は3巡目と8巡目の2件）。ダミー（`apps/v2/data/dummy_backend_response.json`）も同じ形式なので、中身を貼って確認できる（約280KB）。
- 画面が読む項目の一覧は、`app.py` の冒頭コメントを参照。
- 旧形式（`kyoku` / `tehai` / `player_discard` ... の平らな形式）を貼ると、400のエラー画面になる。

### 4-3. エラー画面を確認する

| 操作 | 期待する結果 |
|---|---|
| 何も入れずに送信 | 400のエラー画面 |
| `abc` のような文字列を送信 | 400のエラー画面 |
| `self.hand_with_trigger_tile` に `21` のような数字を入れたJSONを貼る | 400のエラー画面（理由はターミナルに表示） |
| 旧形式（`tehai` などの平らな形式）のJSONを貼る | 400のエラー画面 |
| `http://127.0.0.1:8080/nope` を開く | 404のエラー画面 |
| `app.py` の `raise Exception(...)` のコメントを外して送信 | 500のエラー画面 |

500の確認のあとは、コメントを元に戻す。

## 5. コマンドで確認する（フォームなしでも可）

サーバーを起動したまま、別のターミナルで実行する。

```
curl -s -X POST http://127.0.0.1:8080/analyze -F "input_data=https://example.com" -o out.html -w "%{http_code}\n"
```

- `200` と表示されれば成功。`out.html` をブラウザで開くと結果画面が見られる。
- `-F` を付けずに実行すると `400` になる。
- Windows の PowerShell では `curl` ではなく `curl.exe` と入力する。

## 6. 画面に渡したJSONを確認する

送信のたびに、`apps/v2/data.json` が作られる（画面に渡したJSONそのもの。Git管理外）。

- `kyokus` の数が 9、各局の `entries` の数が 21 / 16 / 10 / 8 / 13 / 6 / 9 / 11 / 15 なら想定どおり。
- 送信のたびに上書きされる。

## 7. うまくいかないとき

| 症状 | 原因と対処 |
|---|---|
| `ModuleNotFoundError: No module named 'flask'` | リポジトリのルートで `pip install -r requirements.txt` を実行する（仮想環境を使う場合は有効化してから） |
| `TemplateNotFound` | `templates` フォルダの場所とファイル名を確認する |
| `FileNotFoundError: dummy_backend_response.json` | `apps/v2/data/` に置く。`apps/v2/` で `python app.py` を実行しているか確認する |
| 送信すると必ず400になる | `index.html` のフォームの項目名・送信先・方式を確認する（2章） |
| ファイルを送ると400になる | フォームに `enctype="multipart/form-data"` があるか確認する |
| 牌が `[xx]` と文字で出る | 牌コードが想定外。ターミナルのメッセージを確認する |
| `Address already in use` | ポートが使用中。`app.py` 末尾の `port=8080` を変える |
| 画面が古いまま | ブラウザを再読み込みする（`Ctrl + F5`） |

## 8. 補足

- 起動は開発用（`debug=True`）。公開環境ではそのまま使わない。`debug=True` では、コードを保存すると自動で再起動する。
- 今のバックエンドはダミー。本物をつなぐときは、`app.py` の `call_backend()` の中身だけ差し替える。
- AIコメントは、ダミーでは注意局面にだけ固定文が付く。
- 注意局面の基準は `EV_WARNING_THRESHOLD`（0.15）。
- バックエンドの返り値の形式は `docs/api/ai-input-format.md`。入力JSONの `commentary` にAIのアドバイスを入れたもの。`app.py` は、その中から画面に必要な項目だけを読む（読む項目の一覧は `app.py` の冒頭コメント）。
- ダミー（`data/dummy_backend_response.json`）を作り直すときは、リポジトリのルートで次を実行する。実行時には使わない。
  `python apps/v2/tools/build_ai_input.py <AkochanのレポートHTML> apps/v2/data/dummy_backend_response.json --lines`
  - 複数局のレポート、自分の席が0以外のレポートにも対応している。`--lines` は、1局面を1行で書き出す指定。
  - 元のレポートHTMLには、プレイヤー名（対局のID）が含まれるため、リポジトリには入れていない。手元のファイルを指定する。
  - 手牌・副露がレポートの表示と一致しない局面があると、エラーで止まる。
