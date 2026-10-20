# 麻雀牌譜検討アプリ 起動方法

Flask製のアプリ（`app.py`）を起動し、ブラウザで牌譜検討の結果画面を確認する手順。

## 1. 必要なもの

| 項目 | 内容 |
|---|---|
| Python | 3.9以上を推奨（動作確認は Python 3.12） |
| パッケージ | `flask`（動作確認は Flask 3.1） |
| ブラウザ | Chrome など（牌の表示にSVGを使う） |

外部サイトへの通信は不要。画面の牌はHTML内のSVGで描画する。

## 2. ファイルの配置

```
プロジェクト/
├ app.py
├ data/
│   └ dummy_backend_response.json  ← ダミーのバックエンド返り値（半荘全部・109局面）
└ templates/
    ├ index.html                   ← 入力画面（お手元のもの）
    ├ error.html                   ← エラー画面（お手元のもの）
    └ result_manyhands.html        ← 結果画面
```

- `dummy_backend_response.json` は `app.py` と同じフォルダの `data/` に置く。
- HTMLは `templates` フォルダに置く（Flaskの決まり）。
- `index.html` のフォームは、次の条件を満たすこと。
  - 送信先: `/analyze`、方式: `POST`
  - ファイルを送る場合: `enctype="multipart/form-data"`
  - 項目名: `input_data`（テキスト）、`file`（ファイル）、`seat`（自家の席 0〜3）

## 3. 起動手順

### 3-1. 仮想環境を作る（初回のみ・推奨）

macOS / Linux:

```
cd プロジェクトのフォルダ
python3 -m venv .venv
source .venv/bin/activate
```

Windows（PowerShell）:

```
cd プロジェクトのフォルダ
py -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3-2. Flaskを入れる（初回のみ）

```
pip install flask
```

### 3-3. 起動する

```
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

### 4-1. ダミー（半荘全部）を表示する

1. `http://127.0.0.1:8080/` を開く。
2. テキスト欄に `https://example.com` と入力して送信する。ファイルを選んで送信しても、同じダミーが出る。
3. 次のとおり表示されれば正常。

| 見る場所 | 期待する表示 |
|---|---|
| 目次 | 東1局、東2局 1本場、東3局、東4局、東4局 1本場、南1局、南2局、南3局、南4局（9局） |
| メタデータ | 局数 9／局面数 109／AI一致率 75/109 = 68.807%／注意局面 29/109 |
| 東1局 | 21局面。⚠️がついた局面だけ開いていて、AIアドバイス欄がある |
| 東1局 6巡目 | プレイヤー「[7s][8s] チー」、AI「スルー」、期待値差 0.17004 |
| 東1局 7巡目 | 手牌の右に副露（6sが横向きの6s7s8s）。ツモ牌の表示なし |
| 南1局 2巡目 | 「対面打」の南。プレイヤーもAIも「南南 ポン」 |

### 4-2. バックエンドのJSONを貼り付けて表示する

テキスト欄にJSONを貼って送信すると、それをバックエンドの返り値として表示する。

```json
{
  "kyoku": "東1局",
  "turn": 8,
  "tehai": ["4m","6m","9p","9p","3s","3s","4s","4s","5sr","7s","8s","8s","c","1s"],
  "player_discard": "6m",
  "ai_discard": "1s",
  "loss": 5.31,
  "commentary": "ここにAIからのコメントが入ります。"
}
```

- 8巡目が1件表示され、⚠️・期待値差 5.31000・コメントが出れば正常。
- 複数巡目は、同じ形式のオブジェクトを `[ ... , ... ]` の配列にして貼る。
- 形式の詳細は `app.py` の冒頭コメントを参照。

### 4-3. エラー画面を確認する

| 操作 | 期待する結果 |
|---|---|
| 何も入れずに送信 | 400のエラー画面 |
| `abc` のような文字列を送信 | 400のエラー画面 |
| `tehai` に `21` のような数字を入れたJSONを貼る | 400のエラー画面（理由はターミナルに表示） |
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

送信のたびに、`app.py` と同じフォルダに `data.json` が作られる（画面に渡したJSONそのもの）。

- `kyokus` の数が 9、各局の `entries` の数が 21 / 16 / 10 / 8 / 13 / 6 / 9 / 11 / 15 なら想定どおり。
- 送信のたびに上書きされる。

## 7. うまくいかないとき

| 症状 | 原因と対処 |
|---|---|
| `ModuleNotFoundError: No module named 'flask'` | `pip install flask` を実行する（仮想環境を使う場合は有効化してから） |
| `TemplateNotFound` | `templates` フォルダの場所とファイル名を確認する |
| `FileNotFoundError: dummy_backend_response.json` | `app.py` と同じフォルダの `data/` に置く |
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
- 以前のやり取りで作った次のファイルは、この `app.py` からは使わない。
  `report_adapter.py`、`build_ai_input.py`、`reconstruct_table_state.py`、`sample_ai_input.json`、`extract_dummy_backend_response.py`
