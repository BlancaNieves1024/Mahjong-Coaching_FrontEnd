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


if __name__ == "__main__":
    app.run(debug=True, port=5000)