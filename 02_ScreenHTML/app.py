from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

# 同じフォルダにある index.html をそのまま表示するルート
@app.route("/")
def index():
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return render_template_string(html_content)

# フロントエンドからのPOSTを受け取るAPIエンドポイント
@app.route("/api/analyze", methods=["POST"])
def analyze_haifu():
    data = request.get_json()
    received_url = data.get("url")
    
    print(f"受け取ったURL: {received_url}")

    # 本番のバックエンドが返す想定のダミーJSONをレスポンスとして返す
    dummy_response = {
        "kyoku": "東1局",
        "turn": 3,
        "tehai": ["4m", "6m", "9p", "9p", "3s", "3s", "4s", "4s", "5sr", "7s", "8s", "8s", "e", "1s"],
        "player_discard": "6m",
        "player_ev": 2.85,
        "ai_discard": "1s",
        "ai_ev": 8.16,
        "loss": 5.31,
        "commentary": "ここではオタ風を残すよりも役牌を重視しましょう。"
    }
    
    return jsonify(dummy_response)

if __name__ == "__main__":
    # ローカルサーバーを起動 ( http://127.0.0.1:5000 )
    app.run(debug=True, port=5000)