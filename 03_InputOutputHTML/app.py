import json
import os
from flask import Flask, jsonify, render_template, render_template_string, request

app = Flask(__name__)


# 牌の変換テーブル（赤ドラはベースの牌文字に設定）
TILE_MAP = {
    '1m': '🀇', '2m': '🀈', '3m': '🀉', '4m': '🀊', '5m': '🀋', '6m': '🀌', '7m': '🀍', '8m': '🀎', '9m': '🀏',
    '5mr': '🀋', # 赤5萬
    '1p': '🀙', '2p': '🀚', '3p': '🀛', '4p': '🀜', '5p': '🀝', '6p': '🀞', '7p': '🀟', '8p': '🀠', '9p': '🀡',
    '5pr': '🀝', # 赤5筒
    '1s': '🀐', '2s': '🀑', '3s': '🀒', '4s': '🀓', '5s': '🀔', '6s': '🀕', '7s': '🀖', '8s': '🀗', '9s': '🀘',
    '5sr': '🀔', # 赤5索
    'e': '🀀', 's_n': '🀁', 'w': '🀂', 'n': '🀃',
    'h': '🀆', 'f': '🀅', 'c': '🀄\uFE0E'
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
    url = request.form.get("url")
    print(f"受け取ったURL: {url}")

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
        "commentary": "ここにAIからのコメントが入ります。"
    }

    # 一時的に data.json に保存
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    # data.json を読み込む
    with open("data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # 赤ドラ対応の変換処理（手牌は各要素を辞書型リストに、打牌は絵文字と赤フラグを分離して渡す）
    data["tehai_data"] = [convert_tile_detail(t) for t in data["tehai"]]
    
    player_res = convert_tile_detail(data["player_discard"])
    data["player_discard"] = player_res["emoji"]
    data["player_is_red"] = player_res["is_red"]

    ai_res = convert_tile_detail(data["ai_discard"])
    data["ai_discard"] = ai_res["emoji"]
    data["ai_is_red"] = ai_res["is_red"]

    # 不要になった元キーを削除（混同防止）
    del data["tehai"]

    # 結果用のHTMLテンプレート（template.html）にデータを流し込んで表示する
    return render_template("template.html", **data)


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
    app.run(debug=True, port=5000)