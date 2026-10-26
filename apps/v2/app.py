import json
import os
import re

from flask import Flask, render_template, request, abort

app = Flask(__name__)


# =============================================================================
# バックエンドから渡されるJSON（入力JSON仕様 ai-input-format.md と同じ形式）
# -----------------------------------------------------------------------------
# 返り値は「入力JSONの commentary 欄に、AIのアドバイスを入れたもの」。入力JSONと形式の差はない。
# 1局面 = 1オブジェクト。複数巡目・複数局は配列で渡す（局面が1件なら単独のオブジェクトでも可）。
#
#   {
#     "meta":        { "kyoku": "東1局", "honba": 0, ... },
#     "situation":   { "turn": 8, "trigger": "draw", "trigger_actor": "自分", "trigger_tile": "6p", ... },
#     "self":        { "hand_with_trigger_tile": [...], "melds": [...], ... },
#     "others":      ...  ← 画面では使わない（読まない）
#     "hidden_info": ...  ← 画面では使わない（読まない）
#     "decision":    { "player_choice": {...}, "ai_choice": {...}, "loss": 0.89, ... },
#     "commentary":  "AIのアドバイス文"
#   }
#
# 画面に出す情報は、下の表の項目だけをJSONから抽出する（extract 処理: entry_view / build_report）。
#
#   画面の情報          JSONの場所                                  備考
#   ------------------  ------------------------------------------  ------------------------------------------
#   局の見出し・目次    meta.kyoku （+ meta.honba）                  honba が1以上なら「東2局 1本場」と表示
#   巡目                situation.turn
#   手牌                self.hand_with_trigger_tile                 きっかけの牌（下記）を末尾に分けて表示
#   自摸/他家の打牌     situation.trigger / trigger_actor /          draw → 「自摸」
#                       trigger_tile                                 opponent_discard → 「上家打」「対面打」「下家打」
#                                                                    trigger が null → ツモ牌なし（鳴いた直後）
#   副露                self.melds                                  tiles / called / from（type は使わない）
#   プレイヤーの行動    decision.player_choice
#   AIの行動            decision.ai_choice
#   期待値差・注意局面  decision.loss                               絶対値が EV_WARNING_THRESHOLD 以上で注意
#   AIのアドバイス      commentary                                  注意局面にだけ表示
#
#   読まない項目: situation.wall_remaining、self の wind / score / river / is_dealer、others、hidden_info、
#                 decision の candidates と各期待値、meta の engine / dora_indicators / kyotaku
#                 （読まないので、中身が不正でも検査しない）
#
# 行動（player_choice / ai_choice）は {"type": ...} のオブジェクト
#   {"type": "discard", "tile": "6m"}                                   打牌
#   {"type": "pon" | "chi", "with_tiles": ["c","c"], "then_discard": "9s"}   鳴き（then_discard は省略可）
#   {"type": "skip"} / {"type": "ron"} / {"type": "tsumo"} / {"type": "riichi"}
#
# 牌コードは mjai 表記のみ（天鳳形式の数字コードは受け付けない）
#   萬子 1m〜9m / 筒子 1p〜9p / 索子 1s〜9s / 赤5 5mr・5pr・5sr
#   字牌 e s w n（東南西北） p f c（白發中）   ← 's' は南、'p' は白
# =============================================================================

# =============================================================================
# 変更メモ（旧app.py「1局・1巡目だけ抜粋して表示」版からの変更点）
# -----------------------------------------------------------------------------
#  1. 表示するHTMLを result.html → result_manyhands.html（複数局・複数巡目のレポート画面）に変更。
#  2. バックエンドの返り値を、1局面のオブジェクトから「局面のリスト」に変更（単独のオブジェクトも可）。
#     同じ局の局面は1つの局にまとめ、目次・局見出しをつけて出力する（build_report() 参照）。
#  3. 手牌の絵文字変換（convert_tile_detail）は廃止。画面側が牌のSVG（#pai-<牌コード>）で描画する。
#     TILE_MAP は「有効な牌コードの一覧」として残し、字牌キーの修正メモも維持している。
#  4. 期待値差（loss）が EV_WARNING_THRESHOLD 以上の局面だけ、⚠️・展開・AIアドバイス欄を表示。
#  5. バックエンド呼び出しは call_backend() に分離。今はダミーを返す（旧版の固定 result の代わり）。
#     本物のバックエンドをつなぐときは、この関数の中身だけ差し替える。
#  6. 【今回】バックエンドの返り値の形式が変わった。
#       旧: 画面用に平らにした形式 {kyoku, turn, tehai, player_discard, ai_discard, loss, commentary, trigger, melds}
#       新: 入力JSON仕様と同じ入れ子の形式 {meta, situation, self, others, hidden_info, decision, commentary}
#           （入力JSONの commentary にAIのアドバイスを入れるだけ。他の差はない）
#     これに合わせて、返り値から画面に必要な項目だけを抽出する処理を入れた（上の表）。
#     画面に出す情報は変えていない（残り枚数は、JSONにあるが従来どおり表示しない）。
#     旧形式のJSONが貼り付けられたときは、400エラーにする（黙ってダミーを出さない）。
# =============================================================================


# 牌の変換テーブル（赤ドラはベースの牌文字に設定）
#
# --- 修正メモ（字牌が表示されないエラーの対応） -----------------------------
# 字牌（東西南北・白發中）のうち「南」と「白」のキーが誤っていたため、
# バックエンドから渡される牌コードと一致せず、該当牌だけ
# 素の文字列表示になっていました。
#
#   修正前: 's_n': '🀁'  →  修正後: 's': '🀁'   （南 / South wind）
#   修正前: 'h':   '🀆'  →  修正後: 'p': '🀆'   （白 / Haku, White Dragon）
#
# mjai記法では風牌は e/s/w/n（東南西北）、三元牌は p/f/c（白/發/中）の
# 1文字コードなので、南は 's'、白は 'p' が正しいキーです。
# 東(e)・西(w)・北(n)・發(f)・中(c) は元々正しいキーだったため変更していません。
#
# 【今回】画面側は絵文字ではなくSVGの #pai-<牌コード> で描くため、
#         このテーブルは「有効な牌コードの一覧」(VALID_TILES) として使う。
# ---------------------------------------------------------------------------
TILE_MAP = {
    '1m': '🀇', '2m': '🀈', '3m': '🀉', '4m': '🀊', '5m': '🀋', '6m': '🀌', '7m': '🀍', '8m': '🀎', '9m': '🀏',
    '5mr': '🀋', # 赤5萬
    '1p': '🀙', '2p': '🀚', '3p': '🀛', '4p': '🀜', '5p': '🀝', '6p': '🀞', '7p': '🀟', '8p': '🀠', '9p': '🀡',
    '5pr': '🀝', # 赤5筒
    '1s': '🀐', '2s': '🀑', '3s': '🀒', '4s': '🀓', '5s': '🀔', '6s': '🀕', '7s': '🀖', '8s': '🀗', '9s': '🀘',
    '5sr': '🀔', # 赤5索
    'e': '🀀', 's': '🀁', 'w': '🀂', 'n': '🀃',  # 東/南/西/北 ← 'south' のキーを 's_n' から 's' に修正
    'p': '🀆', 'f': '🀅', 'c': '🀄︎'        # 白/發/中   ← 'haku' のキーを 'h' から 'p' に修正
}
VALID_TILES = set(TILE_MAP)

# 期待値差（loss）がこの値以上の局面を「注意」にする（決定事項: 0.15）
EV_WARNING_THRESHOLD = 0.15
REPORT_TITLE = "牌譜検討"
AI_LABEL = "AI"                                              # 画面の「AI: 打 ○」の表示名

DATA_PATH = os.path.join(app.root_path, "data.json")                         # 画面に渡したJSON（確認用）
DUMMY_PATH = os.path.join(app.root_path, "data", "dummy_backend_response.json")  # ダミーのバックエンド返り値
KYOKU_WINDS = "東南西北"

# situation.trigger の値
TRIGGER_KINDS = {"draw", "opponent_discard"}
TRIGGER_ACTORS = {"上家", "対面", "下家"}                    # opponent_discard のときの trigger_actor
# 行動（choice）の type
CHOICE_NO_ARG = {"skip", "ron", "tsumo", "riichi"}
MELD_TYPES = {"chi", "pon", "daiminkan", "kakan", "ankan"}
MELD_FROM = {"上家", "対面", "下家"}
NESTED_KEYS = ("meta", "situation", "self", "decision")      # 新形式のトップキー
LEGACY_KEYS = ("tehai", "player_discard", "ai_discard")      # 旧形式（平らな形式）のキー


# -----------------------------------------------------------------------------
# バックエンド呼び出し（今はダミー）
# -----------------------------------------------------------------------------
def dummy_backend_response(source_type, seat):
    """ダミーのバックエンド返り値。半荘全部（9局・109局面）を新形式で返す。

    本物のバックエンドは、AIのアドバイスを commentary に入れて返す。ダミーでは、注意局面にだけ固定文を入れる。
    """
    with open(DUMMY_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)
    note = f"【入力ソース: {source_type} / 自家: {seat}番】ここにAIからのコメントが入ります。"
    for rec in records:
        loss = rec["decision"]["loss"]
        if loss is not None and abs(loss) >= EV_WARNING_THRESHOLD and rec.get("commentary") is None:
            rec["commentary"] = note
    return records


def first_record(obj):
    return obj[0] if isinstance(obj, list) and obj else obj


def looks_like_backend_response(obj):
    """貼り付けられたJSONが、新形式の返り値（局面のオブジェクト or そのリスト）か"""
    first = first_record(obj)
    return isinstance(first, dict) and any(k in first for k in NESTED_KEYS)


def looks_like_legacy_response(obj):
    """貼り付けられたJSONが、旧形式（kyoku / tehai / player_discard ... の平らな形式）か"""
    first = first_record(obj)
    return isinstance(first, dict) and any(k in first for k in LEGACY_KEYS) and not looks_like_backend_response(obj)


def call_backend(source_type, input_data, seat):
    """バックエンドを呼び出して、局面のリストを返す。

    今はダミー。本物のバックエンドをつなぐときは、この関数の中身だけ差し替える。
    （テスト用: JSONの貼り付けが新形式なら、それをバックエンドの返り値として使う）
    """
    if source_type == "json":
        parsed = json.loads(input_data)
        if looks_like_legacy_response(parsed):
            raise ValueError("旧形式（kyoku / tehai / player_discard ...）のJSONです。"
                             "新形式（meta / situation / self / decision / commentary）で渡してください")
        if looks_like_backend_response(parsed):
            return parsed, "貼り付けられたJSONをバックエンドの返り値として使用"
    return dummy_backend_response(source_type, seat), "ダミーのバックエンド返り値を使用"


# -----------------------------------------------------------------------------
# バックエンドの返り値の検査（画面で使う項目だけを検査する）
# -----------------------------------------------------------------------------
def is_tenhou_code(code):
    return isinstance(code, int) or (isinstance(code, str) and re.fullmatch(r"\d{2}", code) is not None)


def check_tile(code, path):
    """牌コード1つが mjai 表記か検査する。不正なら ValueError"""
    if isinstance(code, str) and code in VALID_TILES:
        return
    kind = "天鳳形式の数字コード" if is_tenhou_code(code) else "未定義の牌コード"
    raise ValueError(
        f"{path} = {code!r} は{kind}です。牌は 1m〜9m, 1p〜9p, 1s〜9s, 5mr/5pr/5sr, "
        f"e/s/w/n/p/f/c の形式で渡してください"
    )


def require_dict(parent, key, path):
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{path}.{key} がありません（オブジェクトで渡してください）")
    return value


def parse_choice(choice, path):
    """行動 {"type": ...} → 画面用の辞書（検査つき）。不正なら ValueError

    {"type":"discard","tile":"6m"} / {"type":"pon","with_tiles":["c","c"],"then_discard":"9s"} /
    {"type":"skip"} など。then_discard は省略可。
    """
    if not isinstance(choice, dict) or "type" not in choice:
        raise ValueError(f'{path} は {{"type": ...}} のオブジェクトで渡してください: {choice!r}')
    kind = choice["type"]
    if kind == "discard":
        check_tile(choice.get("tile"), f"{path}.tile")
        return {"type": "discard", "tile": choice["tile"]}
    if kind in ("pon", "chi"):
        tiles = choice.get("with_tiles")
        if not isinstance(tiles, list) or len(tiles) != 2:
            raise ValueError(f"{path}.with_tiles は手牌の2枚の配列にしてください: {tiles!r}")
        for j, code in enumerate(tiles):
            check_tile(code, f"{path}.with_tiles[{j}]")
        out = {"type": kind, "with_tiles": list(tiles)}
        if choice.get("then_discard") is not None:
            check_tile(choice["then_discard"], f"{path}.then_discard")
            out["then_discard"] = choice["then_discard"]
        return out
    if kind in CHOICE_NO_ARG:
        return {"type": kind}
    raise ValueError(f"{path}.type = {kind!r} は不正です。"
                     f"discard / pon / chi / skip / ron / tsumo / riichi のどれかにしてください")


def validate_meld(meld, path):
    if not isinstance(meld, dict):
        raise ValueError(f"{path} がオブジェクトではありません")
    if meld.get("type") is not None and meld["type"] not in MELD_TYPES:      # type は任意（画面では使わない）
        raise ValueError(f"{path}.type は {sorted(MELD_TYPES)} のどれかにしてください: {meld['type']!r}")
    tiles = meld.get("tiles")
    if not isinstance(tiles, list) or not 3 <= len(tiles) <= 4:
        raise ValueError(f"{path}.tiles は3〜4枚の配列にしてください: {tiles!r}")
    for j, code in enumerate(tiles):
        check_tile(code, f"{path}.tiles[{j}]")
    if meld.get("called") is not None:
        check_tile(meld["called"], f"{path}.called")
    if meld.get("from") is not None and meld["from"] not in MELD_FROM:
        raise ValueError(f"{path}.from は {sorted(MELD_FROM)} のどれかにしてください: {meld['from']!r}")


def validate_record(rec, i):
    """局面1件のうち、画面で使う項目を検査する。不正なら ValueError"""
    path = f"[{i}]"
    if not isinstance(rec, dict):
        raise ValueError(f"{path} がオブジェクトではありません")

    # --- meta: 局 ---
    meta = require_dict(rec, "meta", path)
    if not isinstance(meta.get("kyoku"), str) or not meta["kyoku"].strip():
        raise ValueError(f"{path}.meta.kyoku は空でない文字列にしてください: {meta.get('kyoku')!r}")
    honba = meta.get("honba")
    if honba is not None and (not isinstance(honba, int) or isinstance(honba, bool) or honba < 0):
        raise ValueError(f"{path}.meta.honba は0以上の整数にしてください: {honba!r}")

    # --- situation: 巡目ときっかけ ---
    sit = require_dict(rec, "situation", path)
    if not isinstance(sit.get("turn"), int) or isinstance(sit["turn"], bool):
        raise ValueError(f"{path}.situation.turn は整数にしてください: {sit.get('turn')!r}")
    for key in ("trigger", "trigger_tile"):
        if key not in sit:
            raise ValueError(f"{path}.situation に必須キー '{key}' がありません（ツモ牌なしの局面は null）")
    trigger = sit["trigger"]
    if trigger is None:                                        # 鳴いた直後など、ツモ牌・他家の打牌がない局面
        if sit["trigger_tile"] is not None:
            raise ValueError(f"{path}.situation.trigger が null のとき、trigger_tile も null にしてください")
    else:
        if trigger not in TRIGGER_KINDS:
            raise ValueError(f"{path}.situation.trigger は {sorted(TRIGGER_KINDS)} か null にしてください: {trigger!r}")
        check_tile(sit["trigger_tile"], f"{path}.situation.trigger_tile")
        if trigger == "opponent_discard" and sit.get("trigger_actor") not in TRIGGER_ACTORS:
            raise ValueError(f"{path}.situation.trigger_actor は {sorted(TRIGGER_ACTORS)} のどれかにしてください: "
                             f"{sit.get('trigger_actor')!r}")

    # --- self: 手牌・副露 ---
    me = require_dict(rec, "self", path)
    hand = me.get("hand_with_trigger_tile")
    if not isinstance(hand, list) or not 2 <= len(hand) <= 14:
        raise ValueError(f"{path}.self.hand_with_trigger_tile は2〜14枚の配列にしてください: {hand!r}")
    for j, code in enumerate(hand):
        check_tile(code, f"{path}.self.hand_with_trigger_tile[{j}]")
    if trigger is not None and sit["trigger_tile"] not in hand:
        raise ValueError(f"{path}.situation.trigger_tile = {sit['trigger_tile']!r} が "
                         f"self.hand_with_trigger_tile に含まれていません")
    melds = me.get("melds", [])
    if not isinstance(melds, list):
        raise ValueError(f"{path}.self.melds は配列にしてください: {melds!r}")
    for j, meld in enumerate(melds):
        validate_meld(meld, f"{path}.self.melds[{j}]")

    # --- decision: 行動と期待値差 ---
    dec = require_dict(rec, "decision", path)
    parse_choice(dec.get("player_choice"), f"{path}.decision.player_choice")
    parse_choice(dec.get("ai_choice"), f"{path}.decision.ai_choice")
    if "loss" not in dec:
        raise ValueError(f"{path}.decision に必須キー 'loss' がありません")
    loss = dec["loss"]
    if loss is not None and (not isinstance(loss, (int, float)) or isinstance(loss, bool)):
        raise ValueError(f"{path}.decision.loss は数値か null にしてください: {loss!r}")

    # --- commentary ---
    if rec.get("commentary") is not None and not isinstance(rec["commentary"], str):
        raise ValueError(f"{path}.commentary は文字列か null にしてください: {rec['commentary']!r}")


def normalize_backend_response(obj):
    """バックエンドの返り値 → 局面のリスト（検査つき）。単独のオブジェクトはリストにする"""
    records = [obj] if isinstance(obj, dict) else obj
    if not isinstance(records, list) or not records:
        raise ValueError("バックエンドの返り値が、局面のオブジェクト（またはそのリスト）ではありません")
    for i, rec in enumerate(records):
        validate_record(rec, i)
    return records


# -----------------------------------------------------------------------------
# バックエンドの返り値 → 画面に渡す report の作成（ここで、画面に必要な項目だけを抽出する）
# -----------------------------------------------------------------------------
def kyoku_title(meta):
    """meta → 局の表示名。『東1局』、本場があれば『東2局 1本場』"""
    honba = meta.get("honba") or 0
    return meta["kyoku"].strip() + (f" {honba}本場" if honba else "")


def kyoku_anchor(title, fallback):
    """『東2局 1本場』→ 'kyoku-1-1'（目次のアンカー kyoku-<局の番号>-<本場> 用）"""
    m = re.match(rf"^([{KYOKU_WINDS}])(\d)局", title)
    idx = KYOKU_WINDS.index(m.group(1)) * 4 + int(m.group(2)) - 1 if m else fallback
    honba = re.search(r"(\d+)本場", title)
    return f"kyoku-{idx}-{honba.group(1) if honba else 0}"


def meld_view(m):
    """副露 → 表示用の牌リスト。鳴いた牌だけ横向き(rotated)にする（位置は from で決まる。type は使わない）"""
    tiles = list(m.get("tiles", []))
    called, src = m.get("called"), m.get("from")
    pos = None
    if called in tiles and src:
        pos = {"上家": 0, "対面": 1, "下家": len(tiles) - 1}.get(src)     # チーは常に上家から → 先頭が鳴いた牌
    if pos is None:
        return {"from": src, "tiles": [{"code": t, "rotated": False} for t in tiles]}
    rest = list(tiles)
    rest.remove(called)
    ordered = rest[:pos] + [called] + rest[pos:]
    return {"from": src,
            "tiles": [{"code": t, "rotated": i == pos} for i, t in enumerate(ordered)]}


def entry_view(rec, threshold):
    """局面1件（新形式）→ 画面用の辞書。画面に必要な項目だけを、JSONから抽出する"""
    sit, me, dec = rec["situation"], rec["self"], rec["decision"]

    hand = list(me["hand_with_trigger_tile"])
    if sit["trigger"] is None:                                 # 鳴いた直後: ツモ牌なし
        trigger, trigger_tile = None, None
    else:                                                      # きっかけの牌を手牌から分けて、末尾に「自摸」「上家打」などで表示
        trigger_tile = sit["trigger_tile"]
        trigger = "自摸" if sit["trigger"] == "draw" else f'{sit["trigger_actor"]}打'
        hand.pop(len(hand) - 1 - hand[::-1].index(trigger_tile))

    player_choice = parse_choice(dec["player_choice"], "decision.player_choice")
    ai_choice = parse_choice(dec["ai_choice"], "decision.ai_choice")
    loss = dec["loss"]

    return {
        "turn": sit["turn"],
        "wall_remaining": None,                                # JSONにはあるが、画面では従来どおり表示しない
        "trigger": trigger,
        "trigger_label": f"{trigger} " if trigger else "",
        "trigger_tile": trigger_tile,
        "hand": hand,
        "melds": [meld_view(m) for m in me.get("melds", [])],
        "player_choice": player_choice,
        "ai_choice": ai_choice,
        "loss": loss,
        "is_match": player_choice == ai_choice,
        "is_warning": loss is not None and abs(loss) >= threshold,
        "commentary": rec.get("commentary"),
    }


def build_report(records):
    """画面(result_manyhands.html)に渡すJSON全体を作る"""
    kyokus = {}                                                # 局の表示名 → 局。挿入順＝出現順
    for rec in records:
        title = kyoku_title(rec["meta"])
        if title not in kyokus:
            kyokus[title] = {
                "anchor": kyoku_anchor(title, 100 + len(kyokus)),
                "name": title,
                "end_status": "",                              # 返り値にない（空なら非表示）
                "entries": [],
            }
        kyokus[title]["entries"].append(entry_view(rec, EV_WARNING_THRESHOLD))

    entries = [e for k in kyokus.values() for e in k["entries"]]
    total = len(entries)
    matched = sum(e["is_match"] for e in entries)
    warned = sum(e["is_warning"] for e in entries)

    return {
        "title": REPORT_TITLE,
        "engine": AI_LABEL,
        "warning_threshold": EV_WARNING_THRESHOLD,
        "meta_items": [
            ["局数", len(kyokus)],
            ["局面数", total],
            ["AI一致率", f"{matched}/{total} = {matched / total * 100:.3f}%"],
            ["注意局面", f"{warned}/{total}（期待値差 {EV_WARNING_THRESHOLD} 以上）"],
        ],
        "kyokus": list(kyokus.values()),
    }


# 1. ルート（アクセス時に入力画面を表示）
@app.route("/")
def index():
    return render_template("index.html")


# 2. 解析＆画面遷移の処理（フォームからPOST送信されたとき）
@app.route("/analyze", methods=["POST"])
def analyze():
    input_data = request.form.get("input_data", "").strip()
    uploaded_file = request.files.get("file")
    seat = request.form.get("seat", "0") # 自家指定（0:東, 1:南, 2:西, 3:北）

    source_type = None

    # --- source_type の判定ロジック ---
    if uploaded_file and uploaded_file.filename != "":
        # 1. ファイルアップロードがある場合
        source_type = "file"
        # ファイルからJSONとして読み込む処理（今回はダミーなのでファイルオブジェクトの存在確認のみ）
        uploaded_file.read()
        print("入力形式: file (ファイルアップロード)")

    elif input_data:
        # テキストエリアに入力がある場合、JSONかURLかを判定
        try:
            # JSON形式としてパースできるか試す
            json.loads(input_data)
            source_type = "json"
            print("入力形式: json (テキストデータ)")
        except json.JSONDecodeError:
            # パースできなければURL（または文字列）として扱う
            if input_data.startswith("http://") or input_data.startswith("https://"):
                source_type = "url"
                print(f"入力形式: url -> {input_data}")
            else:
                # どちらでもない場合は不正なリクエストとして400エラー
                abort(400)
    else:
        # いずれの入力もない場合は400エラー
        abort(400)

    print(f"選択された自家 (seat): {seat}")
    print(f"判定された source_type: {source_type}")

    # --- 500エラーのテスト用にあえて例外を発生させる ---
    # raise Exception("テスト用の強制エラーです")

    # バックエンドの返り値（局面のリスト）を受け取り、検査して、画面に必要な項目だけを抽出して report にする。
    # 形式の誤り・不正な牌コードは400エラー
    try:
        response, origin = call_backend(source_type, input_data, seat)
        records = normalize_backend_response(response)
        print(f"バックエンド返り値: {origin}（{len(records)}局面）")
        report = build_report(records)
    except ValueError as e:
        # 返り値の不備は理由だけ記録する（トレースバックは出さない）
        app.logger.warning("バックエンドの返り値を処理できません: %s", e)
        print(f"検査エラー: {e}")
        abort(400)

    # 画面に渡すJSONを data.json に保存（確認用）し、読み込み直して使う
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 結果用のHTMLテンプレート（result_manyhands.html）にデータを流し込んで表示する
    return render_template("result_manyhands.html", valid_tiles=VALID_TILES, **data)


# --- エラーハンドラーの設定 ---

@app.errorhandler(404)
def page_not_found(e):
    return render_template(
        "error.html",
        error_code="404",
        error_title="ページが見つかりません",
        error_message="お探しのページは移動または削除されたか、URLが間違っている可能性があります。"
    ), 404

@app.errorhandler(400)
def bad_request(e):
    return render_template(
        "error.html",
        error_code="400",
        error_title="不正なリクエストです",
        error_message="送信されたデータに誤りがあるか、処理できない形式のリクエストです。"
    ), 400

@app.errorhandler(500)
def internal_server_error(e):
    return render_template(
        "error.html",
        error_code="500",
        error_title="サーバーエラーが発生しました",
        error_message="バックエンド側で問題が発生しました。しばらく時間を置いてから再度お試しください。"
    ), 500


if __name__ == "__main__":
    app.run(debug=True, port=8080)
