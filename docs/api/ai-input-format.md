# 麻雀アドバイス生成アプリ 入力JSON仕様（バックエンドチーム向け）

## 1. 概要

- **1局面 = 1つのオブジェクト**。複数の巡目・複数の局は、オブジェクトの配列にする。生成AIに「この局面で、なぜAIの打牌のほうが良いか」のアドバイスを書かせるための入力。
- 元データは、Akochan（mjai-reviewer v1.5.10）が出力したレポートHTML 1ファイルのみ。外部サイト・APIは使わない。半荘全部（複数局）のレポートに対応する。
  - 評価値（候補の表）: HTMLの局面エントリ（`details.entry`）から取得
  - 河・副露・他家の状況・他家の手牌: HTMLに埋め込まれた天鳳形式JSON（局ごとに `<textarea>` が1つ）から復元
  - 「自分」の席は、レポートのメタデータ（`player id`）から取る。0〜3のどの席でもよい。他家は、自分から見た位置（下家・対面・上家）で表す。
- 生成スクリプト: `apps/v2/tools/reconstruct_table_state.py`（卓の状況の復元）、`apps/v2/tools/build_ai_input.py`（入力JSONの統合）。
- サンプル出力: `shared/samples/ai_input_sample_east1.json`（東1局・席0・18局面）、`apps/v2/data/dummy_backend_response.json`（半荘・席2・6局・63局面）。
- 出力側（バックエンド）で必要な変更は、「差が閾値以上の局面だけ生成AIに入力し、返ってきた文を `commentary` に入れる」処理。返り値の形式は、第6章。

## 2. 全体構造

```
{
  "meta":        局の基本情報
  "situation":   判断が必要になった場面
  "self":        自分の情報（手牌・副露・河）
  "others":      他家3人の見える情報（河・副露・点数・リーチ）
  "hidden_info": 他家の手牌（実戦では見えない情報）
  "decision":    自分とAIの選択、評価値、候補一覧
  "commentary":  生成AIのアドバイス文（入力時は null）
}
```

## 3. 牌の表記

| 表記 | 意味 |
|---|---|
| `1m`〜`9m` | 萬子 |
| `1p`〜`9p` | 筒子 |
| `1s`〜`9s` | 索子 |
| `e` `s` `w` `n` | 東・南・西・北 |
| `p` `f` `c` | 白・發・中 |
| `5mr` `5pr` `5sr` | 赤5（萬・筒・索） |

- 注意: `s` は「南」、`p` は「白」。数牌の `1s` や `3p` と混同しない。
- ドラ表示牌 `e`（東）のドラは、次の牌の `s`（南）。

## 4. 各要素の説明

### 4.1 `meta`（局の基本情報）

| キー | 型 | 説明 | 例 |
|---|---|---|---|
| `kyoku` | string | 局（本場は `honba` に分ける） | `"東1局"` |
| `dora_indicators` | string[] | その局面で表示されているドラ表示牌（ドラそのものではない）。カンのたびに増える | `["e"]` |
| `engine` | string | 評価エンジン名 | `"Akochan"` |
| `honba` | int | 本場数 | `0` |
| `kyotaku` | int | 供託の本数。リーチの宣言牌が通ると増える | `0` |

### 4.2 `situation`（判断が必要になった場面）

| キー | 型 | 説明 | 例 |
|---|---|---|---|
| `turn` | int | 自分の巡目（レポートの `Turn N`） | `8` |
| `wall_remaining` | int | 山の残り枚数（配牌後は70枚。嶺上牌を含め、ツモのたびに1枚減る） | `44` |
| `trigger` | string | きっかけ。`draw`（自分のツモ）／`opponent_discard`（他家の打牌への鳴き・ロン判断） | `"draw"` |
| `trigger_tile` | string | きっかけの牌（ツモ牌、または他家が切った牌） | `"6p"` |
| `trigger_actor` | string | 誰の牌か。`自分`／`下家`／`対面`／`上家` | `"自分"` |

### 4.3 `self`（自分の情報）

| キー | 型 | 説明 |
|---|---|---|
| `wind` | string | 自家の風（`east`/`south`/`west`/`north`）。親が `east` |
| `score` | int | 持ち点（リーチ棒を払った後は、1000点引く） |
| `hand_with_trigger_tile` | string[] | 閉じた手牌。`trigger_tile`を含む（ツモ牌、または他家の打牌）。副露した面子は含まない |
| `melds` | object[] | 副露。下記参照 |
| `river` | 配列 | 自分の河（古い順）。表記は第5章を参照 |
| `is_dealer` | bool | 親かどうか |

手牌の枚数は、副露なしでツモなら14枚。副露1つ（3枚）につき3枚少なくなる（例: 中ポン後のツモは11枚）。

`melds` の要素:

| キー | 説明 | 例 |
|---|---|---|
| `type` | `pon` / `chi` / `daiminkan` / `kakan` / `ankan` | `"pon"` |
| `tiles` | 面子の牌。カン（`daiminkan`・`kakan`・`ankan`）は4枚。`chi` は、鳴いた牌が先頭 | `["c","c","c"]` |
| `called` | 鳴いた牌。暗槓は `null` | `"c"` |
| `from` | 出し元。自分から見た位置（`上家`/`対面`/`下家`）。暗槓は `null` | `"下家"` |

- 加槓（`kakan`）は、元のポンの `called`・`from` を引き継ぎ、`tiles` が4枚になる（最後の1枚が、加えた牌）。

### 4.4 `others`（他家の見える情報）

キーは `shimocha`（下家）、`toimen`（対面）、`kamicha`（上家）。

| キー | 型 | 説明 |
|---|---|---|
| `score` | int | 持ち点（リーチ棒を払った後は、1000点引く） |
| `riichi` | bool | リーチ宣言済みか（宣言牌を切った後は `true`） |
| `river` | 配列 | その家の河（古い順）。鳴かれた牌も含む。表記は第5章を参照 |
| `wind` | string | 風 |
| `is_dealer` | bool | 親かどうか |
| `melds` | object[] | その家の副露。形式は `self.melds` と同じ。ただし `from` は自分から見た位置で、`自分`/`下家`/`対面`/`上家` のどれか |
| `genbutsu` | string[] | その家が切った牌の一覧＝現物 |

### 4.5 `hidden_info`（他家の手牌・実戦では見えない情報）

| キー | 型 | 説明 |
|---|---|---|
| `note` | string | 「実戦中は見えない情報」という注記 |
| `hands` | object | キーは `shimocha`/`toimen`/`kamicha`。値はその家の閉じた手牌（副露がなければ13枚） |

- 牌譜（配牌・ツモ・打牌）から計算で復元した値。レポートの表示と直接照合できるのは自分の手牌のみ（18局面で一致を確認）。他家分は同じ計算だが、直接の照合はしていない。

### 4.6 `decision`（選択と評価値）

| キー | 型 | 説明 | 例 |
|---|---|---|---|
| `player_choice` | object | 実際に自分が選んだ行動。表記は下の「行動の種類」 | `{"type":"discard","tile":"2m"}` |
| `ai_choice` | object | Akochanの選択（評価値が最大の行動） | `{"type":"discard","tile":"2s"}` |
| `player_pt_ev` | float / null | 自分の選択のpt期待値。評価できない局面は `null` | `-1.60` |
| `ai_pt_ev` | float / null | AIの選択のpt期待値。評価できない局面は `null` | `-0.70` |
| `loss` | float / null | `ai_pt_ev − player_pt_ev`。0以上。0なら選択が一致（または同評価）。評価できない局面は `null` | `0.89` |
| `candidates` | object[] | 候補の全行動。`pt_ev` の降順（1件目がAIの選択） | 8巡目は10件 |

行動の種類（`player_choice`、`ai_choice`、`candidates[].action` で共通）:

| 行動 | 表記 | 備考 |
|---|---|---|
| 打牌 | `{"type":"discard","tile":"2m"}` | 立直宣言つきの打牌は、`"riichi": true` を足す。例 `{"type":"discard","tile":"4s","riichi":true}` |
| ポン・チー | `{"type":"pon","with_tiles":["c","c"],"then_discard":"9s"}` | `type` は `pon` か `chi`。`with_tiles` は鳴きに使う手牌の2枚、`then_discard` は鳴いたあとに切る牌 |
| カン | `{"type":"daiminkan","tile":"w"}` | `type` は `daiminkan`（他家の打牌を鳴く）／`kakan`（ポン済みの牌に加える）／`ankan`（自分の4枚）。レポートの表記は、どれも `Kan` なので、局面から判定する |
| スルー | `{"type":"skip"}` | 鳴き・ロンをしない |
| ロン | `{"type":"ron"}` | |
| ツモ | `{"type":"tsumo"}` | ツモ和了。この牌譜には現れず、未確認 |

`candidates` の要素:

| キー | 説明 |
|---|---|
| `action` | 行動。表記は上の「行動の種類」 |
| `pt_ev` | その行動のpt期待値 |
| `deal_in_pct` | 放銃確率（%単位） |
| `post_deal_in_pt_ev` | 放銃した場合のpt期待値 |
| `tile_passes_pt_ev` | その牌が通った場合のpt期待値 |

- スキップ・ロン、放銃率0%の行は、`post_deal_in_pt_ev` と `tile_passes_pt_ev` が `null`（元は `N/A`）。
- Akochanが評価できなかった局面（候補の表が `N/A` だけ）は、候補が1行だけで、`pt_ev` などがすべて `null`。この場合、`player_pt_ev`・`ai_pt_ev`・`loss` も `null`（ダミーに3件）。
- `pt_ev` の定義はレポートに記載がない。「順位ptの期待値」は読み取りによる解釈。
- 打牌行では `pt_ev ≒ (1−放銃率)×通過時 ＋ 放銃率×放銃後` が成り立つ（鳴きの行では一致しないことがある）。

### 4.7 `commentary`

| 型 | 説明 |
|---|---|
| string / null | 入力時は `null`。生成AIが書いたアドバイス文を、バックエンドが格納して画面に返す |

## 5. 河の表記

河（`self.river`、`others.*.river`）は、古い順の配列。1枚ごとにオブジェクトで表す。

```json
{"tile": "2p", "tsumogiri": true, "riichi": false, "called_by": null}
```

- `tsumogiri`: ツモ切りか。`riichi`: リーチの宣言牌か。
- `called_by`: 誰に鳴かれたか。`null` | `"自分"` | `"下家"` | `"対面"` | `"上家"`（自分から見た位置）。自分の河にも、他家の河にも付く。鳴かれた牌も、河には残る。

## 6. 返り値（画面に返すJSON）

バックエンドの返り値は、入力JSON（本書の第2〜5章）と同じ形式で、`commentary` にAIのアドバイスを入れたもの。`commentary` 以外の項目は、入力JSONと同じ値で返す。

- 複数の局面は、オブジェクトの配列で返す（局面が1件なら、オブジェクト単独でもよい）。
- `commentary` が必要なのは、注意局面（`decision.loss` の絶対値が0.15以上）だけ。他の局面は `null` のままでよい。
- 牌コードは、第3章の表記だけ。天鳳形式の数字コードは、画面側が受け付けない（400エラー）。
- 画面（`apps/v2`）が読む項目は、次のとおり。読まない項目は、中身が壊れていても検査しない。河が無い局面は、河の欄を出さない。

| 画面の情報 | JSONの場所 |
|---|---|
| 局の見出し・目次 | `meta.kyoku`、`meta.honba` |
| 巡目 | `situation.turn` |
| 手牌 | `self.hand_with_trigger_tile` |
| 自摸・他家の打牌 | `situation.trigger`、`situation.trigger_actor`、`situation.trigger_tile` |
| 副露 | `self.melds`（`tiles`・`called`・`from`） |
| 各家の河 | `self.river`、`others.shimocha.river`、`others.toimen.river`、`others.kamicha.river`（`tile`・`tsumogiri`・`riichi`・`called_by`） |
| プレイヤーの行動・AIの行動 | `decision.player_choice`、`decision.ai_choice` |
| 期待値差・注意局面 | `decision.loss` |
| AIのアドバイス | `commentary` |

## 7. 実際のJSONの例

7.1・7.2は `shared/samples/ai_input_sample_east1.json`（東1局・席0・18局面）、7.3・7.4は `apps/v2/data/dummy_backend_response.json`（半荘・席2・63局面）の実データを、そのまま整形したもの。候補はすべて載せている。

### 7.1 打牌の判断（8巡目・自分のツモ）

- 局面: 自分のツモ6pのあと。自分は2m切り、Akochanは2s切り（`loss` は0.89）。
- 自分は下家から中をポン済み。全員25000点でリーチなし。
- `commentary` は入力時は `null`。

```json
{
  "meta": {
    "engine": "Akochan",
    "kyoku": "東1局",
    "honba": 0,
    "kyotaku": 0,
    "dora_indicators": ["e"]
  },
  "situation": {"turn": 8, "wall_remaining": 44, "trigger": "draw", "trigger_actor": "自分", "trigger_tile": "6p"},
  "self": {
    "wind": "east",
    "is_dealer": true,
    "score": 25000,
    "hand_with_trigger_tile": ["1m", "2m", "2m", "3m", "4m", "5p", "2s", "3s", "4s", "5s", "6p"],
    "melds": [
      {
        "type": "pon",
        "tiles": ["c", "c", "c"],
        "called": "c",
        "from": "下家"
      }
    ],
    "river": [
      {"tile": "w", "tsumogiri": false, "riichi": false, "called_by": null},
      {"tile": "8m", "tsumogiri": false, "riichi": false, "called_by": null},
      {"tile": "e", "tsumogiri": false, "riichi": false, "called_by": null},
      {"tile": "9s", "tsumogiri": false, "riichi": false, "called_by": null},
      {"tile": "8s", "tsumogiri": false, "riichi": false, "called_by": null},
      {"tile": "2p", "tsumogiri": true, "riichi": false, "called_by": null},
      {"tile": "9s", "tsumogiri": true, "riichi": false, "called_by": null}
    ]
  },
  "others": {
    "shimocha": {
      "wind": "south",
      "is_dealer": false,
      "score": 25000,
      "river": [
        {"tile": "n", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "p", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "c", "tsumogiri": false, "riichi": false, "called_by": "自分"},
        {"tile": "e", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "1m", "tsumogiri": true, "riichi": false, "called_by": null},
        {"tile": "3m", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "4s", "tsumogiri": false, "riichi": false, "called_by": null}
      ],
      "melds": [],
      "riichi": false,
      "genbutsu": ["1m", "3m", "4s", "c", "e", "n", "p"]
    },
    "toimen": {
      "wind": "west",
      "is_dealer": false,
      "score": 25000,
      "river": [
        {"tile": "p", "tsumogiri": true, "riichi": false, "called_by": null},
        {"tile": "7s", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "9s", "tsumogiri": true, "riichi": false, "called_by": null},
        {"tile": "1s", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "2s", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "9m", "tsumogiri": false, "riichi": false, "called_by": null}
      ],
      "melds": [],
      "riichi": false,
      "genbutsu": ["1s", "2s", "7s", "9m", "9s", "p"]
    },
    "kamicha": {
      "wind": "north",
      "is_dealer": false,
      "score": 25000,
      "river": [
        {"tile": "w", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "1m", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "e", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "n", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "w", "tsumogiri": true, "riichi": false, "called_by": null},
        {"tile": "8p", "tsumogiri": false, "riichi": false, "called_by": null}
      ],
      "melds": [],
      "riichi": false,
      "genbutsu": ["1m", "8p", "e", "n", "w"]
    }
  },
  "hidden_info": {
    "note": "牌譜から復元した他家の手牌。実戦中は見えない情報。助言の根拠にする場合は『結果から見ると』と明示すること。",
    "hands": {
      "shimocha": ["5p", "6m", "6m", "7m", "7m", "7p", "7p", "7s", "8s", "9p", "9p", "f", "f"],
      "toimen": ["3p", "3s", "4m", "4m", "4p", "4s", "5sr", "6m", "8p", "9p", "9p", "s", "s"],
      "kamicha": ["2p", "2p", "3p", "3s", "4p", "4p", "5m", "5pr", "6p", "7m", "7s", "8s", "9m"]
    }
  },
  "decision": {
    "player_choice": {"type": "discard", "tile": "2m"},
    "ai_choice": {"type": "discard", "tile": "2s"},
    "loss": 0.8943,
    "player_pt_ev": -1.59801,
    "ai_pt_ev": -0.70371,
    "candidates": [
      {
        "action": {"type": "discard", "tile": "2s"},
        "pt_ev": -0.70371,
        "deal_in_pct": 0.1521,
        "post_deal_in_pt_ev": -31.66179,
        "tile_passes_pt_ev": -0.65655
      },
      {
        "action": {"type": "discard", "tile": "1m"},
        "pt_ev": -0.72898,
        "deal_in_pct": 0.05425,
        "post_deal_in_pt_ev": -31.73605,
        "tile_passes_pt_ev": -0.71215
      },
      {
        "action": {"type": "discard", "tile": "5s"},
        "pt_ev": -0.76191,
        "deal_in_pct": 0.32745,
        "post_deal_in_pt_ev": -31.66843,
        "tile_passes_pt_ev": -0.66037
      },
      {
        "action": {"type": "discard", "tile": "2m"},
        "pt_ev": -1.59801,
        "deal_in_pct": 0.20172,
        "post_deal_in_pt_ev": -31.70391,
        "tile_passes_pt_ev": -1.53716
      },
      {
        "action": {"type": "discard", "tile": "4m"},
        "pt_ev": -1.74873,
        "deal_in_pct": 0.3062,
        "post_deal_in_pt_ev": -31.71843,
        "tile_passes_pt_ev": -1.65668
      },
      {
        "action": {"type": "discard", "tile": "6p"},
        "pt_ev": -3.64457,
        "deal_in_pct": 0.46217,
        "post_deal_in_pt_ev": -31.68758,
        "tile_passes_pt_ev": -3.51437
      },
      {
        "action": {"type": "discard", "tile": "5p"},
        "pt_ev": -3.78423,
        "deal_in_pct": 0.28162,
        "post_deal_in_pt_ev": -31.67477,
        "tile_passes_pt_ev": -3.70546
      },
      {
        "action": {"type": "discard", "tile": "3m"},
        "pt_ev": -3.83916,
        "deal_in_pct": 0.15022,
        "post_deal_in_pt_ev": -32.09072,
        "tile_passes_pt_ev": -3.79666
      },
      {
        "action": {"type": "discard", "tile": "3s"},
        "pt_ev": -4.98069,
        "deal_in_pct": 0.24715,
        "post_deal_in_pt_ev": -31.69893,
        "tile_passes_pt_ev": -4.91449
      },
      {
        "action": {"type": "discard", "tile": "4s"},
        "pt_ev": -5.76405,
        "deal_in_pct": 0.07652,
        "post_deal_in_pt_ev": -32.72083,
        "tile_passes_pt_ev": -5.74341
      }
    ]
  },
  "commentary": null
}
```

### 7.2 副露の判断（3巡目・下家が切った中をポンするか）

- 局面: 下家が中を切った。自分は中を2枚持っていて、ポンできる。
- 自分は「中ポン→9s切り」、Akochanは「中ポン→5p切り」（`loss` は0.31）。ポンすること自体は一致していて、ポンのあとの打牌が違う。
- 候補は11件。そのうち `skip`（ポンしない）は5位で、`pt_ev` は-2.33。

打牌の判断（7.1）との違い:

| 項目 | 7.1 打牌の判断 | 7.2 副露の判断 |
|---|---|---|
| `situation.trigger` | `draw` | `opponent_discard` |
| `situation.trigger_actor` | `自分` | `下家`（切った人） |
| `self.hand_with_trigger_tile` | 自分のツモ牌を含む | 下家が切った牌（中）を含む。鳴く前なので14枚 |
| `self.melds` | 副露済みの面子 | 空（まだ鳴いていない） |
| `decision` の行動 | `{"type":"discard","tile":"2m"}` | `{"type":"pon","with_tiles":["c","c"],"then_discard":"9s"}` |
| `candidates` | 打牌のみ | ポン＋打牌の組み合わせと、`skip`（ポンしない） |
| `skip` の行 | なし | 放銃率・放銃後・通過時のpt EVは `null` |

- `with_tiles` は、鳴きに使う自分の手牌の2枚。`then_discard` は、鳴いたあとに切る牌。
- 他家の打牌への判断は、スキップ・ロンの場合も同じ形式（`{"type":"skip"}` / `{"type":"ron"}`）。この牌譜では、ポン1件、スキップ4件、ロン1件。

```json
{
  "meta": {
    "engine": "Akochan",
    "kyoku": "東1局",
    "honba": 0,
    "kyotaku": 0,
    "dora_indicators": ["e"]
  },
  "situation": {"turn": 3, "wall_remaining": 60, "trigger": "opponent_discard", "trigger_actor": "下家", "trigger_tile": "c"},
  "self": {
    "wind": "east",
    "is_dealer": true,
    "score": 25000,
    "hand_with_trigger_tile": ["1m", "2m", "2m", "3m", "4m", "5p", "3s", "4s", "5s", "8s", "9s", "c", "c", "c"],
    "melds": [],
    "river": [
      {"tile": "w", "tsumogiri": false, "riichi": false, "called_by": null},
      {"tile": "8m", "tsumogiri": false, "riichi": false, "called_by": null},
      {"tile": "e", "tsumogiri": false, "riichi": false, "called_by": null}
    ]
  },
  "others": {
    "shimocha": {
      "wind": "south",
      "is_dealer": false,
      "score": 25000,
      "river": [
        {"tile": "n", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "p", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "c", "tsumogiri": false, "riichi": false, "called_by": null}
      ],
      "melds": [],
      "riichi": false,
      "genbutsu": ["c", "n", "p"]
    },
    "toimen": {
      "wind": "west",
      "is_dealer": false,
      "score": 25000,
      "river": [
        {"tile": "p", "tsumogiri": true, "riichi": false, "called_by": null},
        {"tile": "7s", "tsumogiri": false, "riichi": false, "called_by": null}
      ],
      "melds": [],
      "riichi": false,
      "genbutsu": ["7s", "p"]
    },
    "kamicha": {
      "wind": "north",
      "is_dealer": false,
      "score": 25000,
      "river": [
        {"tile": "w", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "1m", "tsumogiri": false, "riichi": false, "called_by": null}
      ],
      "melds": [],
      "riichi": false,
      "genbutsu": ["1m", "w"]
    }
  },
  "hidden_info": {
    "note": "牌譜から復元した他家の手牌。実戦中は見えない情報。助言の根拠にする場合は『結果から見ると』と明示すること。",
    "hands": {
      "shimocha": ["3m", "4s", "6m", "6m", "7m", "7m", "7p", "7p", "8s", "9p", "e", "f", "f"],
      "toimen": ["1s", "2s", "3p", "4m", "4m", "4p", "4s", "5sr", "6m", "9p", "9p", "s", "s"],
      "kamicha": ["2p", "2p", "3p", "3s", "4p", "5m", "7m", "7s", "8p", "8s", "9m", "e", "n"]
    }
  },
  "decision": {
    "player_choice": {
      "type": "pon",
      "with_tiles": ["c", "c"],
      "then_discard": "9s"
    },
    "ai_choice": {
      "type": "pon",
      "with_tiles": ["c", "c"],
      "then_discard": "5p"
    },
    "loss": 0.30556,
    "player_pt_ev": -2.03563,
    "ai_pt_ev": -1.73007,
    "candidates": [
      {
        "action": {
          "type": "pon",
          "with_tiles": ["c", "c"],
          "then_discard": "5p"
        },
        "pt_ev": -1.73007,
        "deal_in_pct": 0.00575,
        "post_deal_in_pt_ev": -31.31508,
        "tile_passes_pt_ev": -1.72837
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["c", "c"],
          "then_discard": "9s"
        },
        "pt_ev": -2.03563,
        "deal_in_pct": 0.00291,
        "post_deal_in_pt_ev": -31.31862,
        "tile_passes_pt_ev": -2.03478
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["c", "c"],
          "then_discard": "1m"
        },
        "pt_ev": -2.08634,
        "deal_in_pct": 0.00236,
        "post_deal_in_pt_ev": -31.27444,
        "tile_passes_pt_ev": -2.08565
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["c", "c"],
          "then_discard": "8s"
        },
        "pt_ev": -2.08955,
        "deal_in_pct": 0.00368,
        "post_deal_in_pt_ev": -31.31548,
        "tile_passes_pt_ev": -2.08847
      },
      {
        "action": {"type": "skip"},
        "pt_ev": -2.33358,
        "deal_in_pct": null,
        "post_deal_in_pt_ev": null,
        "tile_passes_pt_ev": null
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["c", "c"],
          "then_discard": "2m"
        },
        "pt_ev": -3.00951,
        "deal_in_pct": 0.00354,
        "post_deal_in_pt_ev": -31.31551,
        "tile_passes_pt_ev": -3.00851
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["c", "c"],
          "then_discard": "4m"
        },
        "pt_ev": -3.68744,
        "deal_in_pct": 0.00525,
        "post_deal_in_pt_ev": -31.30276,
        "tile_passes_pt_ev": -3.68599
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["c", "c"],
          "then_discard": "3m"
        },
        "pt_ev": -5.48772,
        "deal_in_pct": 0.00413,
        "post_deal_in_pt_ev": -31.3146,
        "tile_passes_pt_ev": -5.48665
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["c", "c"],
          "then_discard": "5s"
        },
        "pt_ev": -5.70272,
        "deal_in_pct": 0.00576,
        "post_deal_in_pt_ev": -31.31535,
        "tile_passes_pt_ev": -5.70125
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["c", "c"],
          "then_discard": "3s"
        },
        "pt_ev": -5.70659,
        "deal_in_pct": 0.0044,
        "post_deal_in_pt_ev": -31.31549,
        "tile_passes_pt_ev": -5.70546
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["c", "c"],
          "then_discard": "4s"
        },
        "pt_ev": -6.50624,
        "deal_in_pct": 0.00567,
        "post_deal_in_pt_ev": -31.30973,
        "tile_passes_pt_ev": -6.50484
      }
    ]
  },
  "commentary": null
}
```

### 7.3 立直宣言つきの打牌（東2局 2本場・2巡目）

- 局面: 自分のツモ北のあと。自分もAIも、4sを切って立直する（`loss` は0）。
- 立直宣言つきの打牌は、`"riichi": true` を持つ（`player_choice`、`ai_choice`、`candidates` の1件目）。
- 自分の席は2番。東2局の親は席1なので、自分の `wind` は `south`。

```json
{
  "meta": {
    "engine": "Akochan",
    "kyoku": "東2局",
    "honba": 2,
    "kyotaku": 0,
    "dora_indicators": ["2s"]
  },
  "situation": {"turn": 2, "wall_remaining": 65, "trigger": "draw", "trigger_actor": "自分", "trigger_tile": "n"},
  "self": {
    "wind": "south",
    "is_dealer": false,
    "score": 7400,
    "hand_with_trigger_tile": ["1m", "1m", "1m", "3m", "4m", "5m", "1p", "2p", "3p", "4s", "7s", "8s", "n", "n"],
    "melds": [],
    "river": [
      {"tile": "9m", "tsumogiri": false, "riichi": false, "called_by": null}
    ]
  },
  "others": {
    "shimocha": {
      "wind": "west",
      "is_dealer": false,
      "score": 1000,
      "river": [
        {"tile": "3m", "tsumogiri": false, "riichi": false, "called_by": "対面"}
      ],
      "melds": [],
      "riichi": false,
      "genbutsu": ["3m"]
    },
    "toimen": {
      "wind": "north",
      "is_dealer": false,
      "score": 52600,
      "river": [
        {"tile": "2p", "tsumogiri": false, "riichi": false, "called_by": null}
      ],
      "melds": [
        {
          "type": "chi",
          "tiles": ["3m", "2m", "4m"],
          "called": "3m",
          "from": "下家"
        }
      ],
      "riichi": false,
      "genbutsu": ["2p"]
    },
    "kamicha": {
      "wind": "east",
      "is_dealer": true,
      "score": 39000,
      "river": [
        {"tile": "p", "tsumogiri": true, "riichi": false, "called_by": null},
        {"tile": "f", "tsumogiri": false, "riichi": false, "called_by": null}
      ],
      "melds": [],
      "riichi": false,
      "genbutsu": ["f", "p"]
    }
  },
  "hidden_info": {
    "note": "牌譜から復元した他家の手牌。実戦中は見えない情報。助言の根拠にする場合は『結果から見ると』と明示すること。",
    "hands": {
      "shimocha": ["3p", "4p", "5p", "7m", "7p", "7p", "7s", "8m", "9s", "c", "s", "s", "w"],
      "toimen": ["3s", "3s", "4m", "5s", "6m", "6m", "6p", "6s", "7s", "8p"],
      "kamicha": ["1p", "1p", "1s", "2m", "2p", "3s", "5m", "5p", "6p", "7m", "7p", "8m", "e"]
    }
  },
  "decision": {
    "player_choice": {"type": "discard", "tile": "4s", "riichi": true},
    "ai_choice": {"type": "discard", "tile": "4s", "riichi": true},
    "loss": 0.0,
    "player_pt_ev": -33.15405,
    "ai_pt_ev": -33.15405,
    "candidates": [
      {
        "action": {"type": "discard", "tile": "4s", "riichi": true},
        "pt_ev": -33.15405,
        "deal_in_pct": 0.00141,
        "post_deal_in_pt_ev": -77.58057,
        "tile_passes_pt_ev": -33.15343
      },
      {
        "action": {"type": "discard", "tile": "7s"},
        "pt_ev": -36.30497,
        "deal_in_pct": 0.00095,
        "post_deal_in_pt_ev": -74.88161,
        "tile_passes_pt_ev": -36.30461
      },
      {
        "action": {"type": "discard", "tile": "8s"},
        "pt_ev": -36.34657,
        "deal_in_pct": 0.00076,
        "post_deal_in_pt_ev": -75.61536,
        "tile_passes_pt_ev": -36.34627
      },
      {
        "action": {"type": "discard", "tile": "n"},
        "pt_ev": -37.40466,
        "deal_in_pct": 0.00061,
        "post_deal_in_pt_ev": -67.66676,
        "tile_passes_pt_ev": -37.40447
      },
      {
        "action": {"type": "discard", "tile": "1m"},
        "pt_ev": -37.43818,
        "deal_in_pct": 0.00224,
        "post_deal_in_pt_ev": -79.63769,
        "tile_passes_pt_ev": -37.43723
      },
      {
        "action": {"type": "discard", "tile": "2p"},
        "pt_ev": -37.43865,
        "deal_in_pct": 8e-05,
        "post_deal_in_pt_ev": -100.59864,
        "tile_passes_pt_ev": -37.43859
      },
      {
        "action": {"type": "discard", "tile": "3p"},
        "pt_ev": -37.4388,
        "deal_in_pct": 0.0009,
        "post_deal_in_pt_ev": -74.76962,
        "tile_passes_pt_ev": -37.43846
      },
      {
        "action": {"type": "discard", "tile": "4s"},
        "pt_ev": -37.43881,
        "deal_in_pct": 0.00141,
        "post_deal_in_pt_ev": -77.58057,
        "tile_passes_pt_ev": -37.43824
      },
      {
        "action": {"type": "discard", "tile": "1p"},
        "pt_ev": -37.43888,
        "deal_in_pct": 0.00023,
        "post_deal_in_pt_ev": -98.51518,
        "tile_passes_pt_ev": -37.43874
      },
      {
        "action": {"type": "discard", "tile": "3m"},
        "pt_ev": -37.43893,
        "deal_in_pct": 0.00292,
        "post_deal_in_pt_ev": -76.52964,
        "tile_passes_pt_ev": -37.43779
      },
      {
        "action": {"type": "discard", "tile": "5m"},
        "pt_ev": -37.43927,
        "deal_in_pct": 0.00612,
        "post_deal_in_pt_ev": -76.11356,
        "tile_passes_pt_ev": -37.43691
      },
      {
        "action": {"type": "discard", "tile": "4m"},
        "pt_ev": -37.43928,
        "deal_in_pct": 0.00612,
        "post_deal_in_pt_ev": -76.10928,
        "tile_passes_pt_ev": -37.43691
      }
    ]
  },
  "commentary": null
}
```

### 7.4 カンの判断（東1局 2本場・3巡目・下家が切った西を大明槓するか）

- 局面: 下家が西を切った。自分は西を3枚持っていて、大明槓できる。自分は大明槓、Akochanはスルー（`loss` は2.17907）。
- カンは、`{"type":"daiminkan","tile":"w"}` の形。自分のツモ番で、ポン済みの牌に加えるときは `kakan`、手牌の4枚でするときは `ankan`。
- 自分は、白のポンを済ませている（`self.melds`）。

```json
{
  "meta": {
    "engine": "Akochan",
    "kyoku": "東1局",
    "honba": 2,
    "kyotaku": 0,
    "dora_indicators": ["9p"]
  },
  "situation": {"turn": 3, "wall_remaining": 59, "trigger": "opponent_discard", "trigger_actor": "下家", "trigger_tile": "w"},
  "self": {
    "wind": "west",
    "is_dealer": false,
    "score": 18900,
    "hand_with_trigger_tile": ["2m", "3m", "1p", "4p", "6p", "7p", "8p", "w", "w", "w", "w"],
    "melds": [
      {
        "type": "pon",
        "tiles": ["p", "p", "p"],
        "called": "p",
        "from": "上家"
      }
    ],
    "river": [
      {"tile": "1s", "tsumogiri": false, "riichi": false, "called_by": null},
      {"tile": "c", "tsumogiri": false, "riichi": false, "called_by": null},
      {"tile": "9m", "tsumogiri": false, "riichi": false, "called_by": null}
    ]
  },
  "others": {
    "shimocha": {
      "wind": "north",
      "is_dealer": false,
      "score": 6900,
      "river": [
        {"tile": "9s", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "p", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "w", "tsumogiri": false, "riichi": false, "called_by": null}
      ],
      "melds": [],
      "riichi": false,
      "genbutsu": ["9s", "p", "w"]
    },
    "toimen": {
      "wind": "east",
      "is_dealer": true,
      "score": 55300,
      "river": [
        {"tile": "n", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "9m", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "c", "tsumogiri": false, "riichi": false, "called_by": null}
      ],
      "melds": [],
      "riichi": false,
      "genbutsu": ["9m", "c", "n"]
    },
    "kamicha": {
      "wind": "south",
      "is_dealer": false,
      "score": 18900,
      "river": [
        {"tile": "p", "tsumogiri": true, "riichi": false, "called_by": "自分"},
        {"tile": "5s", "tsumogiri": false, "riichi": false, "called_by": null},
        {"tile": "7s", "tsumogiri": false, "riichi": false, "called_by": null}
      ],
      "melds": [],
      "riichi": false,
      "genbutsu": ["5s", "7s", "p"]
    }
  },
  "hidden_info": {
    "note": "牌譜から復元した他家の手牌。実戦中は見えない情報。助言の根拠にする場合は『結果から見ると』と明示すること。",
    "hands": {
      "shimocha": ["1p", "2p", "3m", "4m", "4s", "6p", "7p", "8m", "8m", "8p", "9m", "f", "s"],
      "toimen": ["2m", "2p", "2s", "4m", "5m", "5m", "5s", "6p", "6s", "7s", "9p", "e", "f"],
      "kamicha": ["1m", "1m", "2p", "3p", "4m", "4p", "4p", "5m", "5p", "7m", "8m", "e", "e"]
    }
  },
  "decision": {
    "player_choice": {"type": "daiminkan", "tile": "w"},
    "ai_choice": {"type": "skip"},
    "loss": 2.17907,
    "player_pt_ev": 2.99103,
    "ai_pt_ev": 5.1701,
    "candidates": [
      {
        "action": {"type": "skip"},
        "pt_ev": 5.1701,
        "deal_in_pct": null,
        "post_deal_in_pt_ev": null,
        "tile_passes_pt_ev": null
      },
      {
        "action": {"type": "daiminkan", "tile": "w"},
        "pt_ev": 2.99103,
        "deal_in_pct": 0.0,
        "post_deal_in_pt_ev": null,
        "tile_passes_pt_ev": null
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["w", "w"],
          "then_discard": "4p"
        },
        "pt_ev": 2.25181,
        "deal_in_pct": 0.01249,
        "post_deal_in_pt_ev": -31.54645,
        "tile_passes_pt_ev": 2.25603
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["w", "w"],
          "then_discard": "2m"
        },
        "pt_ev": -0.40731,
        "deal_in_pct": 0.00798,
        "post_deal_in_pt_ev": -31.54897,
        "tile_passes_pt_ev": -0.40482
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["w", "w"],
          "then_discard": "3m"
        },
        "pt_ev": -0.55119,
        "deal_in_pct": 0.00956,
        "post_deal_in_pt_ev": -31.54688,
        "tile_passes_pt_ev": -0.54822
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["w", "w"],
          "then_discard": "1p"
        },
        "pt_ev": -0.68962,
        "deal_in_pct": 0.00624,
        "post_deal_in_pt_ev": -46.28241,
        "tile_passes_pt_ev": -0.68678
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["w", "w"],
          "then_discard": "8p"
        },
        "pt_ev": -3.18136,
        "deal_in_pct": 0.00798,
        "post_deal_in_pt_ev": -31.54897,
        "tile_passes_pt_ev": -3.1791
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["w", "w"],
          "then_discard": "7p"
        },
        "pt_ev": -3.25218,
        "deal_in_pct": 0.00956,
        "post_deal_in_pt_ev": -31.54688,
        "tile_passes_pt_ev": -3.24948
      },
      {
        "action": {
          "type": "pon",
          "with_tiles": ["w", "w"],
          "then_discard": "6p"
        },
        "pt_ev": -4.12191,
        "deal_in_pct": 0.01249,
        "post_deal_in_pt_ev": -31.54645,
        "tile_passes_pt_ev": -4.11849
      }
    ]
  },
  "commentary": null
}
```

## 8. 検証状況と、未検証・要確認事項

検証済み（`apps/v2/tools/build_ai_input.py`）:

- 自分の手牌・副露が、レポートの表示と一致すること。全局面で照合し、一致しなければ、変換がエラーで止まる。
- 和了者の手牌が、和了の形になること（半荘・6局の和了6件すべて）。他家の手牌は、レポートに表示がなく、直接の照合ができないため、この確認で代える。
- 各局の牌譜（ツモ・打牌）を使い切ること、ドラ表示牌の数が牌譜と一致すること。
- 複数局、自分の席が0以外（席2）、チー・ポン・大明槓・加槓、リーチ（自分と他家）の復元。
- 河（4人分）: 各局の終了時に、枚数・立直の位置・ツモ切りの数・手出しの牌の並びが、牌譜の記録と一致すること。局面が進むにつれて、河は伸びるだけであること。

未検証・要確認:

- 暗槓、ダブロン、流局、包（パオ）、抜きドラ（三麻）、搶槓は、牌譜に現れておらず、未検証。
- ツモ和了の判断（`tsumo`）は、この牌譜に現れておらず、未確認。
- 生成AIへの指示文と、生成されたアドバイスの質は未検証。
- 警告の閾値（`loss` 0.15以上）は、pt期待値の単位での妥当性が未確認の暫定値。
- Akochanが評価できない局面（候補の表が `N/A` だけ）がある（63局面中3件）。原因は不明。`loss` などは `null` になる。
- 牌譜の `<textarea>` を削除すると、河・副露・他家の情報が復元できなくなる。
