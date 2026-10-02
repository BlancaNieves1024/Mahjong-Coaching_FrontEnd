import json
import os
from flask import Flask, jsonify, render_template, render_template_string, request, abort

app = Flask(__name__)


# 牌の変換テーブル（赤ドラはベースの牌文字に設定）
#
# --- 修正メモ（字牌が表示されないエラーの対応） -----------------------------
# 字牌（東西南北・白發中）のうち「南」と「白」のキーが誤っていたため、
# バックエンドから渡される牌コードと一致せず、該当牌だけ
# convert_tile_detail() のフォールバック（f"[{tile_code}]"）に落ちて
# 素の文字列表示になっていました。
#
#   修正前: 's_n': '🀁'  →  修正後: 's': '🀁'   （南 / South wind）
#   修正前: 'h':   '🀆'  →  修正後: 'p': '🀆'   （白 / Haku, White Dragon）
#
# mjai記法では風牌は e/s/w/n（東南西北）、三元牌は p/f/c（白/發/中）の
# 1文字コードなので、南は 's'、白は 'p' が正しいキーです。
# 東(e)・西(w)・北(n)・發(f)・中(c) は元々正しいキーだったため変更していません。
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

# 牌コードを辞書型（絵文字と赤フラグ）に変換する関数
def convert_tile_detail(tile_code):
    emoji = TILE_MAP.get(tile_code, f"[{tile_code}]")
    is_red = tile_code.endswith('r')
    return {
        'emoji': emoji,
        'is_red': is_red
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

    # ダミーの result データ（赤ドラを含む）
    result = {
        "kyoku": "東1局",
        "turn": 8,
        "tehai": ["4m", "6m", "9p", "9p", "3s", "3s", "4s", "4s", "5sr", "7s", "8s", "8s", "c", "1s"],
        "player_discard": "6m",
        "ai_discard": "1s",
        "loss": 5.31,
        "commentary": f"【入力ソース: {source_type} / 自家: {seat}番】ここにAIからのコメントが入ります。"
    }

    # 一時的に data.json に保存
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    # data.json を読み込む
    with open("data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # 赤ドラ対応の変換処理
    data["tehai_data"] = [convert_tile_detail(t) for t in data["tehai"]]

    player_res = convert_tile_detail(data["player_discard"])
    data["player_discard"] = player_res["emoji"]
    data["player_is_red"] = player_res["is_red"]

    ai_res = convert_tile_detail(data["ai_discard"])
    data["ai_discard"] = ai_res["emoji"]
    data["ai_is_red"] = ai_res["is_red"]

    # 不要になった元キーを削除（混同防止）
    del data["tehai"]

    # 結果用のHTMLテンプレート（result.html）にデータを流し込んで表示する
    return render_template("result.html", **data)


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
