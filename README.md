# Mahjong-Coaching_FrontEnd

麻雀AI牌譜添削ツールのフロントエンド（Flask + Jinja2）。牌譜URLやバックエンドの解析結果（JSON）を受け取り、AIの選択と自分の選択の期待値差を画面に表示する。

## バージョン

| 版 | フォルダ | 内容 | 状態 |
|---|---|---|---|
| v2 | [apps/v2](apps/v2/) | 半荘全部（全局・全巡目）を表示。期待値差 0.15 以上の局面に⚠️とAIアドバイス欄。副露・鳴き・他家打牌に対応 | **現行版** |
| v1 | [apps/v1](apps/v1/) | 最大期待値ロスの1局面だけを表示 | 参照用 |

入力画面（`templates/index.html`）は v1・v2 で共通。

## 起動方法（v2）

```
pip install -r requirements.txt
cd apps/v2
python app.py
```

ブラウザで http://127.0.0.1:8080/ を開く。詳しい手順と動作確認の方法は [apps/v2/README.md](apps/v2/README.md)。

## フォルダ構成

```
apps/
  v1/            旧版（1局面表示・参照用）
  v2/            現行版（半荘全部表示）
    data/        ダミーのバックエンド返り値、サンプル
    tools/       ダミーデータ生成スクリプト
prototypes/      開発途中の検証（01: akochan出力からの悪手抽出、02: 画面HTML試作、11: HTML整形、99: 旧ファイル）
shared/samples/  牌譜URLのサンプル（v1・v2 共通）
docs/
  project/       進捗報告・WBS
  images/        画面キャプチャ（prototype / v1 / v2 / shared）
```

v2 のダミーデータは `prototypes/02_ScreenHTML/template_manyhands_v2.html` から `apps/v2/tools/extract_dummy_backend_response.py` で生成している。

## 旧構成からの対応

| 旧 | 新 |
|---|---|
| `00_Projects/` | `docs/project/` |
| `01_WorstExtractionFromAkochan/` | `prototypes/01_WorstExtractionFromAkochan/` |
| `02_ScreenHTML/` | `prototypes/02_ScreenHTML/` |
| `03_InputOutputHTML/` | `apps/v1/` |
| `11_HTMLConversion/` | `prototypes/11_HTMLConversion/` |
| `12_images/` | `docs/images/` |
| `13_sampledata/tenhou_sample.txt` | `shared/samples/tenhou_sample_urls.txt` |
| `23_InputOutputHTML/` | `apps/v2/` |
| `99_old/` | `prototypes/99_old/` |

整理前の状態はタグ `archive/before-reorg` で参照できる。
