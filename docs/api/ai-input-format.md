# 麻雀アドバイス生成アプリ 入力JSON仕様（バックエンドチーム向け）

## 1. 概要

- **1局面 = 1つのJSON**。生成AIに「この局面で、なぜAIの打牌のほうが良いか」のアドバイスを書かせるための入力。
- 元データは、Akochan（mjai-reviewer v1.5.10）が出力したレポートHTML 1ファイルのみ。外部サイト・APIは使わない。
  - 評価値（候補打牌の表）: HTMLの局面エントリ（`details.entry`）から取得
  - 河・副露・他家の状況・他家の手牌: HTMLに埋め込まれた天鳳形式JSON（`<textarea>` 内）から復元
- 生成スクリプト: `reconstruct_table_state.py`（卓の状況の復元）、`build_ai_input.py`（入力JSONの統合）。サンプル出力は `ai_input.json`（東1局・18局面）。
- 出力側（バックエンド）で必要な変更は、「差が閾値以上の局面だけ生成AIに入力し、返ってきた文を `commentary` に入れる」処理。

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
| `kyoku` | string | 局 | `"東1局"` |
| `dora_indicators` | string[] | ドラ表示牌（ドラそのものではない） | `["e"]` |
| `engine` | string | 評価エンジン名（実出力のみ） | `"Akochan"` |
| `honba` | int | 本場数（実出力のみ） | `0` |
| `kyotaku` | int | 供託の本数（実出力のみ） | `0` |

### 4.2 `situation`（判断が必要になった場面）

| キー | 型 | 説明 | 例 |
|---|---|---|---|
| `turn` | int | 自分の巡目（レポートの `Turn N`） | `8` |
| `wall_remaining` | int | 山の残り枚数（配牌後は70枚、ツモのたびに減る） | `44` |
| `trigger` | string | きっかけ。`draw`（自分のツモ）／`opponent_discard`（他家の打牌への鳴き・ロン判断） | `"draw"` |
| `trigger_tile` | string | きっかけの牌（ツモ牌、または他家が切った牌） | `"6p"` |
| `trigger_actor` | string | 誰の牌か。`自分`／`下家`／`対面`／`上家`（実出力のみ） | `"自分"` |

### 4.3 `self`（自分の情報）

| キー | 型 | 説明 |
|---|---|---|
| `wind` | string | 自家の風（`east`/`south`/`west`/`north`） |
| `score` | int | 持ち点 |
| `hand_with_trigger_tile` | string[] | 閉じた手牌。`trigger_tile`を含む（ツモ牌、または他家の打牌）。副露した面子は含まない |
| `melds` | object[] | 副露。下記参照 |
| `river` | 配列 | 自分の河（古い順）。表記は第5章を参照 |
| `is_dealer` | bool | 親かどうか（実出力のみ） |

手牌の枚数は、副露なしでツモなら14枚。副露1つ（3枚）につき3枚少なくなる（例: 中ポン後のツモは11枚）。

`melds` の要素:

| キー | 説明 | 例 |
|---|---|---|
| `type` | `pon` / `chi` / `daiminkan` / `kakan` / `ankan` | `"pon"` |
| `tiles` | 面子の牌 | `["c","c","c"]` |
| `called` | 鳴いた牌（実出力のみ） | `"c"` |
| `from` | 出し元。`上家`/`対面`/`下家` | `"下家"` |

### 4.4 `others`（他家の見える情報）

キーは `shimocha`（下家）、`toimen`（対面）、`kamicha`（上家）。

| キー | 型 | 説明 |
|---|---|---|
| `score` | int | 持ち点 |
| `riichi` | bool | リーチ済みか |
| `river` | 配列 | その家の河（古い順）。鳴かれた牌も含む。表記は第5章を参照 |
| `wind` | string | 風（実出力のみ） |
| `is_dealer` | bool | 親かどうか（実出力のみ） |
| `melds` | object[] | その家の副露。形式は `self.melds` と同じ（実出力のみ） |
| `genbutsu` | string[] | その家が切った牌の一覧＝現物（実出力のみ） |

### 4.5 `hidden_info`（他家の手牌・実戦では見えない情報）

| キー | 型 | 説明 |
|---|---|---|
| `note` | string | 「実戦中は見えない情報」という注記 |
| `hands` | object | キーは `shimocha`/`toimen`/`kamicha`。値はその家の閉じた手牌（副露がなければ13枚） |

- 牌譜（配牌・ツモ・打牌）から計算で復元した値。レポートの表示と直接照合できるのは自分の手牌のみ（18局面で一致を確認）。他家分は同じ計算だが、直接の照合はしていない。

### 4.6 `decision`（選択と評価値）

| キー | 型 | 説明 | 例 |
|---|---|---|---|
| `player_choice` | string / object | 実際に自分が選んだ行動 | `"2m"` |
| `ai_choice` | string / object | Akochanの選択（評価値が最大の行動） | `"2s"` |
| `player_pt_ev` | float | 自分の選択のpt期待値 | `-1.60` |
| `ai_pt_ev` | float | AIの選択のpt期待値 | `-0.70` |
| `loss` | float | `ai_pt_ev − player_pt_ev`。0以上。0なら選択が一致（または同評価） | `0.89` |
| `candidates` | object[] | 候補の全行動。`pt_ev` の降順（1件目がAIの選択） | 8巡目は10件 |
| `player_deal_in_pct` / `ai_deal_in_pct` | float | 放銃確率（%）。サンプルにあるが実出力にはない（第6章） | `0.20` / `0.15` |

`candidates` の要素（実出力）:

| キー | 説明 |
|---|---|
| `action` | 行動。`{"type":"discard","tile":"2m"}`、`{"type":"pon","with_tiles":["c","c"],"then_discard":"9s"}`、`{"type":"skip"}`、`{"type":"ron"}` など |
| `pt_ev` | その行動のpt期待値 |
| `deal_in_pct` | 放銃確率（%単位） |
| `post_deal_in_pt_ev` | 放銃した場合のpt期待値 |
| `tile_passes_pt_ev` | その牌が通った場合のpt期待値 |

- スキップ・ロン、放銃率0%の行は、`post_deal_in_pt_ev` と `tile_passes_pt_ev` が `null`（元は `N/A`）。
- `pt_ev` の定義はレポートに記載がない。「順位ptの期待値」は読み取りによる解釈。
- 打牌行では `pt_ev ≒ (1−放銃率)×通過時 ＋ 放銃率×放銃後` が成り立つ（168行中158行、誤差0.01以内）。例外はすべて鳴き候補の行。

### 4.7 `commentary`

| 型 | 説明 |
|---|---|
| string / null | 入力時は `null`。生成AIが書いたアドバイス文を、バックエンドが格納して画面に返す |

## 5. 河の表記（サンプルと実出力の違い）

サンプルJSON（説明用の短縮表記）:

| 表記 | 意味 |
|---|---|
| `"2p*"` | ツモ切り |
| `"c(自分が鳴いた)"` | 自分に鳴かれた牌 |

実出力は、1枚ごとのオブジェクト。

```json
{"tile": "2p", "tsumogiri": true, "riichi": false}
```

他家の河には `"called_by": null | "自分" | "下家" | "対面" | "上家"` が付く。

## 6. サンプルJSONと実出力（`ai_input.json`）の差異

| 項目 | サンプル | 実出力 |
|---|---|---|
| `river` | 文字列（`*` 等の記号つき） | オブジェクト（`tile`/`tsumogiri`/`riichi`/`called_by`） |
| `player_choice` / `ai_choice` | `"2m"`（文字列） | `{"type":"discard","tile":"2m"}`（鳴き・スキップ・ロンを表すため） |
| `player_deal_in_pct` / `ai_deal_in_pct` | あり | なし（`candidates` から取得できる。必要なら出力側に追加） |
| `candidates` | `["...10候補..."]` | オブジェクトの配列（第4.6章） |
| `meta.engine` `honba` `kyotaku` | なし | あり |
| `situation.trigger` | `draw` | `draw` または `opponent_discard` |
| `situation.trigger_actor` | なし | あり |
| `self.is_dealer` | なし | あり |
| `others.*.wind` `is_dealer` `melds` `genbutsu` | なし | あり |

バックエンドは、実出力（`ai_input.json`）の形式に合わせて実装する。

## 7. 実際のJSONの例

`ai_input.json`（東1局・18局面）の実出力を、そのまま整形したもの。候補はすべて載せている。

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
      {"tile": "w", "tsumogiri": false, "riichi": false},
      {"tile": "8m", "tsumogiri": false, "riichi": false},
      {"tile": "e", "tsumogiri": false, "riichi": false},
      {"tile": "9s", "tsumogiri": false, "riichi": false},
      {"tile": "8s", "tsumogiri": false, "riichi": false},
      {"tile": "2p", "tsumogiri": true, "riichi": false},
      {"tile": "9s", "tsumogiri": true, "riichi": false}
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
      {"tile": "w", "tsumogiri": false, "riichi": false},
      {"tile": "8m", "tsumogiri": false, "riichi": false},
      {"tile": "e", "tsumogiri": false, "riichi": false}
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

## 8. 未検証・要確認事項

- 生成AIへの指示文と、生成されたアドバイスの質は未検証。
- 警告の閾値（`loss` 0.15以上）はpt期待値の単位での妥当性が未確認の暫定値。
- リーチ・カンを含む牌譜での復元は未検証（今回の牌譜にない）。
- 複数局のレポートは未対応（先頭の1局のみ）。
- Mortal版のHTMLに同じ `<textarea>` があるかは未確認。
- 牌譜の `<textarea>` を削除すると、河・副露・他家の情報が復元できなくなる。
