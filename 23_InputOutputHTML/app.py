import json
import os
import re

from flask import Flask, render_template, request, abort

app = Flask(__name__)


# =============================================================================
# バックエンドから渡されるJSON（1局面 = 1オブジェクト。複数巡目は配列で渡す）
# -----------------------------------------------------------------------------
#   {
#       "kyoku": "東1局",                      局（同じ局の局面は、この文字列が同じであること）
#       "turn": 8,                             巡目
#       "tehai": ["4m", "6m", ..., "1s"],      手牌の牌コード（閉じた手牌のみ）。最後の1枚がツモ牌
#       "player_discard": "6m",                自分の選択（下記の「行動の表記」）
#       "ai_discard": "1s",                    AIの選択（同上）
#       "loss": 5.31,                          期待値差（AI − 自分）。null可
#       "commentary": "..."                    AIのコメント。省略・null可
#   }
#
# 行動の表記（player_discard / ai_discard）
#   打牌            牌コード                          例 "6m"
#   それ以外        "スルー" "立直" "ロン" "ツモ"
#   チー・ポン      鳴きに使う手牌2枚 + チー/ポン       例 "7s8sチー" "ssポン"
#
# 任意キー（無ければ省略。基本形式に無い局面を表すためのもの）
#   "trigger": "自摸" | "上家打" | "対面打" | "下家打" | null
#        省略＝"自摸"。他家の打牌への判断（スルー・鳴き・ロン）は "上家打" などで、tehai の最後がその牌。
#        null＝鳴いた直後でツモ牌なし（tehai の最後はツモ牌ではない）
#   "melds": [{"type": "chi"|"pon"|"daiminkan"|"kakan"|"ankan", "tiles": [...], "called": "6s", "from": "上家"|"対面"|"下家"}]
#        副露済みの面子（tehai には含めない）。called と from は暗槓・加槓では省略可
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
#     同じ kyoku の局面は1つの局にまとめ、目次・局見出しをつけて出力する（build_report() 参照）。
#  3. 手牌の絵文字変換（convert_tile_detail）は廃止。画面側が牌のSVG（#pai-<牌コード>）で描画する。
#     TILE_MAP は「有効な牌コードの一覧」として残し、字牌キーの修正メモも維持している。
#  4. バックエンドからの受け取りを validate_record() で検査する。
#     必須キーの欠け・型の誤り・不正な牌コード（天鳳の数字コード含む）は400エラー（理由はコンソールに出力）。
#  5. 期待値差（loss）が EV_WARNING_THRESHOLD 以上の局面だけ、⚠️・展開・AIアドバイス欄を表示。
#     これまでブラウザ側JSがやっていた判定を、app.py側で行うように変更した。
#  6. バックエンド呼び出しは call_backend() に分離。今はダミーを返す（旧版の固定 result の代わり）。
#     本物のバックエンドをつなぐときは、この関数の中身だけ差し替える。
#  7. 【今回】ダミーを「半荘全部（9局・109局面）」に変更。データは dummy_backend_response.json に分離した。
#     これに伴い、打牌以外の判断（スルー・立直・ロン・ツモ・チー・ポン）、副露済みの手牌、
#     他家の打牌への判断、鳴いた直後（ツモ牌なし）を表せるように、上記の「行動の表記」と
#     任意キー trigger / melds を追加した（基本の7キーは変更なし）。
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
DUMMY_PATH = os.path.join(app.root_path, "dummy_backend_response.json")      # ダミーのバックエンド返り値
KYOKU_WINDS = "東南西北"

# 行動の表記
ACTION_WORDS = {"スルー": "skip", "立直": "riichi", "ロン": "ron", "ツモ": "tsumo"}
CALL_PATTERN = re.compile(r"^((?:[1-9][mps]r?|[ewnspfc]){2})(チー|ポン)$")      # 例: 7s8sチー / ssポン
TILE_TOKEN = re.compile(r"[1-9][mps]r?|[ewnspfc]")
# 任意キーの値
TRIGGERS = {"自摸", "上家打", "対面打", "下家打"}
MELD_TYPES = {"chi", "pon", "daiminkan", "kakan", "ankan"}
MELD_FROM = {"上家", "対面", "下家"}


# -----------------------------------------------------------------------------
# バックエンド呼び出し（今はダミー）
# -----------------------------------------------------------------------------
def dummy_backend_response(source_type, seat):
    """ダミーのバックエンド返り値。半荘全部（9局・109局面）を返す（旧版の固定 result の代わり）。

    注意局面（loss が閾値以上）にだけ、ダミーのコメントを付ける。
    """
    with open(DUMMY_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)
    note = f"【入力ソース: {source_type} / 自家: {seat}番】ここにAIからのコメントが入ります。"
    for rec in records:
        if rec["loss"] is not None and abs(rec["loss"]) >= EV_WARNING_THRESHOLD:
            rec["commentary"] = note
    return records


def looks_like_backend_response(obj):
    """貼り付けられたJSONが、バックエンドの返り値の形（局面のオブジェクト or そのリスト）か"""
    first = obj[0] if isinstance(obj, list) and obj else obj
    return isinstance(first, dict) and any(k in first for k in ("tehai", "player_discard", "ai_discard"))


def call_backend(source_type, input_data, seat):
    """バックエンドを呼び出して、局面のリストを返す。

    今はダミー。本物のバックエンドをつなぐときは、この関数の中身だけ差し替える。
    （テスト用: JSONの貼り付けが上記の形なら、それをバックエンドの返り値として使う）
    """
    if source_type == "json":
        parsed = json.loads(input_data)
        if looks_like_backend_response(parsed):
            return parsed, "貼り付けられたJSONをバックエンドの返り値として使用"
    return dummy_backend_response(source_type, seat), "ダミーのバックエンド返り値を使用"


# -----------------------------------------------------------------------------
# バックエンドの返り値の検査
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


def parse_action(value, path):
    """バックエンドの行動表記 → 画面用の辞書。不正なら ValueError

    "6m"      → {"type": "discard", "tile": "6m"}
    "スルー"  → {"type": "skip"}（立直 riichi / ロン ron / ツモ tsumo も同様）
    "7s8sチー"→ {"type": "chi", "with_tiles": ["7s", "8s"]}（ポンは "pon"）
    """
    if isinstance(value, str):
        if value in VALID_TILES:
            return {"type": "discard", "tile": value}
        if value in ACTION_WORDS:
            return {"type": ACTION_WORDS[value]}
        m = CALL_PATTERN.match(value)
        if m:
            return {"type": "pon" if m.group(2) == "ポン" else "chi",
                    "with_tiles": TILE_TOKEN.findall(m.group(1))}
    if is_tenhou_code(value):
        check_tile(value, path)                                # 天鳳形式の数字コードだと分かる説明で ValueError
    raise ValueError(
        f"{path} = {value!r} は行動の表記として不正です。打牌は牌コード、それ以外は "
        f"スルー / 立直 / ロン / ツモ / 「手牌2枚+チー・ポン」（例 7s8sチー）で渡してください"
    )


def validate_meld(meld, path):
    if not isinstance(meld, dict):
        raise ValueError(f"{path} がオブジェクトではありません")
    if meld.get("type") not in MELD_TYPES:
        raise ValueError(f"{path}.type は {sorted(MELD_TYPES)} のどれかにしてください: {meld.get('type')!r}")
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
    """局面1件の必須キー・型・牌コード・行動の表記を検査する。不正なら ValueError"""
    path = f"[{i}]"
    if not isinstance(rec, dict):
        raise ValueError(f"{path} がオブジェクトではありません")
    for key in ("kyoku", "turn", "tehai", "player_discard", "ai_discard", "loss"):
        if key not in rec:
            raise ValueError(f"{path} に必須キー '{key}' がありません")
    if not isinstance(rec["kyoku"], str) or not rec["kyoku"].strip():
        raise ValueError(f"{path}.kyoku は空でない文字列にしてください: {rec['kyoku']!r}")
    if not isinstance(rec["turn"], int) or isinstance(rec["turn"], bool):
        raise ValueError(f"{path}.turn は整数にしてください: {rec['turn']!r}")
    if not isinstance(rec["tehai"], list) or not 2 <= len(rec["tehai"]) <= 14:
        raise ValueError(f"{path}.tehai は2〜14枚の配列にしてください: {rec['tehai']!r}")
    for j, code in enumerate(rec["tehai"]):
        check_tile(code, f"{path}.tehai[{j}]")
    parse_action(rec["player_discard"], f"{path}.player_discard")
    parse_action(rec["ai_discard"], f"{path}.ai_discard")
    loss = rec["loss"]
    if loss is not None and (not isinstance(loss, (int, float)) or isinstance(loss, bool)):
        raise ValueError(f"{path}.loss は数値か null にしてください: {loss!r}")
    if rec.get("commentary") is not None and not isinstance(rec["commentary"], str):
        raise ValueError(f"{path}.commentary は文字列か null にしてください: {rec['commentary']!r}")
    # --- 任意キー ---
    if "trigger" in rec and rec["trigger"] is not None and rec["trigger"] not in TRIGGERS:
        raise ValueError(f"{path}.trigger は {sorted(TRIGGERS)} か null にしてください: {rec['trigger']!r}")
    if "melds" in rec:
        if not isinstance(rec["melds"], list):
            raise ValueError(f"{path}.melds は配列にしてください: {rec['melds']!r}")
        for j, meld in enumerate(rec["melds"]):
            validate_meld(meld, f"{path}.melds[{j}]")


def normalize_backend_response(obj):
    """バックエンドの返り値 → 局面のリスト（検査つき）。単独のオブジェクトはリストにする"""
    records = [obj] if isinstance(obj, dict) else obj
    if not isinstance(records, list) or not records:
        raise ValueError("バックエンドの返り値が、局面のオブジェクト（またはそのリスト）ではありません")
    for i, rec in enumerate(records):
        validate_record(rec, i)
    return records


# -----------------------------------------------------------------------------
# バックエンドの返り値 → 画面に渡す report の作成
# -----------------------------------------------------------------------------
def kyoku_anchor(name, fallback):
    """『東2局 1本場』→ 'kyoku-1-1'（目次のアンカー kyoku-<局の番号>-<本場> 用）"""
    m = re.match(rf"^([{KYOKU_WINDS}])(\d)局", name)
    idx = KYOKU_WINDS.index(m.group(1)) * 4 + int(m.group(2)) - 1 if m else fallback
    honba = re.search(r"(\d+)本場", name)
    return f"kyoku-{idx}-{honba.group(1) if honba else 0}"


def meld_view(m):
    """副露 → 表示用の牌リスト。鳴いた牌だけ横向き(rotated)にする"""
    tiles = list(m.get("tiles", []))
    called, src = m.get("called"), m.get("from")
    pos = None
    if called in tiles and src:
        if m.get("type") == "chi":
            pos = 0                                           # チーは常に上家から（先頭が鳴いた牌）
        else:
            pos = {"上家": 0, "対面": 1, "下家": len(tiles) - 1}.get(src)
    if pos is None:
        return {"type": m.get("type"), "from": src, "tiles": [{"code": t, "rotated": False} for t in tiles]}
    rest = list(tiles)
    rest.remove(called)
    ordered = rest[:pos] + [called] + rest[pos:]
    return {"type": m.get("type"), "from": src,
            "tiles": [{"code": t, "rotated": i == pos} for i, t in enumerate(ordered)]}


def entry_view(rec, threshold):
    """局面1件 → 画面用の辞書"""
    tehai = list(rec["tehai"])
    trigger = rec.get("trigger", "自摸")                        # 省略＝自摸
    if trigger is None:                                        # 鳴いた直後: ツモ牌なし
        hand, trigger_tile = tehai, None
    else:                                                      # 最後の1枚（ツモ牌／他家の打牌）を手牌の末尾に分けて表示
        hand, trigger_tile = tehai[:-1], tehai[-1]

    loss = rec["loss"]
    is_match = rec["player_discard"] == rec["ai_discard"]
    is_warning = loss is not None and abs(loss) >= threshold

    return {
        "turn": rec["turn"],
        "wall_remaining": None,                                # バックエンドから渡されないため非表示
        "trigger": trigger,
        "trigger_label": f"{trigger} " if trigger else "",
        "trigger_tile": trigger_tile,
        "hand": hand,
        "melds": [meld_view(m) for m in rec.get("melds", [])],
        "player_choice": parse_action(rec["player_discard"], "player_discard"),
        "ai_choice": parse_action(rec["ai_discard"], "ai_discard"),
        "loss": loss,
        "is_match": is_match,
        "is_warning": is_warning,
        "commentary": rec.get("commentary"),
    }


def build_report(records):
    """画面(result_manyhands.html)に渡すJSON全体を作る"""
    kyokus = {}                                                # 局名 → 局。挿入順＝出現順
    for rec in records:
        name = rec["kyoku"].strip()
        if name not in kyokus:
            kyokus[name] = {
                "anchor": kyoku_anchor(name, 100 + len(kyokus)),
                "name": name,
                "end_status": "",                              # バックエンドから渡されない（空なら非表示）
                "entries": [],
            }
        kyokus[name]["entries"].append(entry_view(rec, EV_WARNING_THRESHOLD))

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

    # バックエンドの返り値（局面のリスト）を受け取り、検査して、画面用の report にする。
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
