import json
import os
from flask import Flask, jsonify, render_template, render_template_string, request

app = Flask(__name__)


# 牌の変換テーブル（前回作成したもの）
TILE_MAP = {
    '1m': '🀇', '2m': '🀈', '3m': '🀉', '4m': '🀊', '5m': '🀋', '6m': '🀌', '7m': '🀍', '8m': '🀎', '9m': '🀏',
    '1p': '🀙', '2p': '🀚', '3p': '🀛', '4p': '🀜', '5p': '🀝', '6p': '🀞', '7p': '🀟', '8p': '🀠', '9p': '🀡',
    '1s': '🀐', '2s': '🀑', '3s': '🀒', '4s': '🀓', '5s': '🀔', '6s': '🀕', '7s': '🀖', '8s': '🀗', '9s': '🀘',
    '5mr': '🀋(赤)','5pr': '🀝(赤)', '5sr': '🀔(赤)',# 赤ドラ
    'e': '🀀', 's_n': '🀁', 'w': '🀂', 'n': '🀃',
    'h': '🀆', 'f': '🀅', 'c': '🀄\uFE0E'
}
def convert_tiles(tile_code):
    return TILE_MAP.get(tile_code, f"[{tile_code}]")


# 1. ルート（アクセス時に入力画面を表示）
@app.route("/")
def index():
    # templates/index.html を自動でレンダリングする
    return render_template("index.html")


# 2. 解析＆画面遷移の処理（フォームからPOST送信されたとき）
@app.route("/analyze", methods=["POST"])
def analyze():
    url = request.form.get("url")
    print(f"受け取ったURL: {url}")

# --- 500エラーのテスト用にあえて例外を発生させる ---
    #raise Exception("テスト用の強制エラーです")

    # --- 【あなたのお手元のコードをここに組み込むイメージ】 ---
    # 本来はここでURLからデータを抽出して data.json を作る処理が入ります
    # 今回のデモでは、ダミーの result データを用意します
    result = {
        "kyoku": "東1局",
        "turn": 8,
        "tehai": ["4m", "6m", "9p", "9p", "3s", "3s", "4s", "4s", "5s", "7s", "8s", "8s", "c", "1s"],
        "player_discard": "6m",
        "ai_discard": "1s",
        "loss": 5.31,
        "commentary": "ここにAIからのコメントが入ります。"
    }


    # 一時的に data.json に保存する処理（お手元のコードの再現）
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    # -----------------------------------------------------------

    # data.json を読み込んで牌を変換する（お手元の main.py の処理）
    with open("data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # 牌コードの変換
    data["tehai"] = [convert_tiles(t) for t in data["tehai"]]
    data["player_discard"] = convert_tiles(data["player_discard"])
    data["ai_discard"] = convert_tiles(data["ai_discard"])

    # 結果用のHTMLテンプレート（template.html）にデータを流し込んで表示する
    return render_template("template.html", **data)


# --- エラーハンドラーの設定 ---

# 404エラー（ページが見つからない場合）
@app.errorhandler(404)
def page_not_found(e):
    return render_template(
        "error.html",
        error_code="404",
        error_title="ページが見つかりません",
        error_message="お探しのページは移動または削除されたか、URLが間違っている可能性があります。"
    ), 404

# 400エラー（不正なリクエスト等の場合）
@app.errorhandler(400)
def bad_request(e):
    return render_template(
        "error.html",
        error_code="400",
        error_title="不正なリクエストです",
        error_message="送信されたデータに誤りがあるか、処理できない形式のリクエストです。"
    ), 400

# 500エラー（サーバー内部で予期せぬエラーが発生した場合）
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
# 500エラー（サーバー内部で予期せぬエラーが発生した場合）を発生させるテスト時にコメントアウトする
    #app.run(debug=False, port=5000)