import re
from bs4 import BeautifulSoup

# 1. あなたがアップロードした元のHTMLファイルを読み込みます
try:
    with open("report.html", "r", encoding="utf-8") as f:
        html_content = f.read()
except FileNotFoundError:
    print("エラー: 'report.html' が見つかりません。このプログラムと同じフォルダに配置してください。")
    exit()

print("HTMLファイルを整形中...（数万行の牌画像データもすべてノーカットで処理します）")

# 2. BeautifulSoupを使って、タグのネスト構造に合わせて綺麗にインデントと改行を入れます
soup = BeautifulSoup(html_content, "html.parser")
formatted_html = soup.prettify()

# 3. 整形した完全なデータを、新しいファイルとして書き出します
with open("formatted_report.html", "w", encoding="utf-8") as f:
    f.write(formatted_html)

print("成功しました！同じフォルダに 'formatted_report.html' が作成されました。")