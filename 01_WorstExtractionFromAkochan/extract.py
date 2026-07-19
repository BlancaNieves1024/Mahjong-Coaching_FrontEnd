import json
import re
from bs4 import BeautifulSoup
import sys  # 追加

# --- 牌ID抽出 ---
def get_tile_id(tag):
    if not tag: return None
    return tag.get("href", "").replace("#pai-", "")

# --- 手牌と副露を分離せずすべて取得する関数 ---
def extract_tiles(entry):
    """
    手牌・副露を分けず、tehai-state内のすべての牌を抽出する
    """
    tehai = []
    
    # 手牌エリア（Mortal/AkochanのWeb版共通構造）
    tehai_ul = entry.find("ul", class_="tehai-state")
    if not tehai_ul: return tehai, []

    # すべての牌タグを取得してtehaiリストに入れる
    for use_tag in tehai_ul.find_all("use"):
        tile_id = get_tile_id(use_tag)
        if tile_id:
            tehai.append(tile_id)
            
    return tehai, [] # fuuroは空のまま返して構造を維持

# --- 局と巡目の取得 ---
def get_kyoku_and_turn(entry):
    section = entry.find_parent("section")
    kyoku = "Unknown"
    if section:
        h1 = section.find("h1", class_="kyoku-heading")
        if h1:
            kyoku = h1.find("div").get_text(strip=True) if h1.find("div") else h1.get_text(strip=True)

    summary = entry.find("summary").get_text(strip=True)
    turn_match = re.search(r"Turn\s+(\d+)", summary, re.IGNORECASE)
    turn = int(turn_match.group(1)) if turn_match else 0
    return kyoku, turn

def get_ev_from_row(row):
    tds = row.find_all("td")
    if len(tds) < 2: return 0.0
    ev_td = tds[1]
    int_part = ev_td.find("span", class_="int")
    frac_part = ev_td.find("span", class_="frac")
    val_str = (int_part.text.strip() if int_part else "0") + (frac_part.text.strip() if frac_part else "0")
    try: return float(val_str)
    except: return 0.0

def extract_max_loss_turn(html_path):
    # 複数のエンコーディングを順に試す
    for enc in ['utf-8', 'utf-16', 'cp932', 'utf-8-sig']:
        try:
            with open(html_path, "r", encoding=enc) as f:
                content = f.read()
            soup = BeautifulSoup(content, "html.parser")
            break # 成功したらループを抜ける
        except UnicodeDecodeError:
            continue
    else:
        raise Exception("どのエンコーディングでもファイルを読み込めませんでした。")

    max_loss = -1.0
    max_loss_data = None

    for section in soup.find_all("section"):
        for entry in section.find_all("details", class_="entry"):
            kyoku, turn = get_kyoku_and_turn(entry)
            
            table = entry.find("table", class_="data")
            if not table: continue
            
            rows = table.find("tbody").find_all("tr")
            ai_best_row = rows[0]
            ai_ev = get_ev_from_row(ai_best_row)
            
            player_span = entry.find("span", style=lambda s: s and "background" in s)
            player_discard = get_tile_id(player_span.find("use")) if player_span and player_span.find("use") else None
            
            player_ev = ai_ev
            for row in rows:
                if get_tile_id(row.find("use")) == player_discard:
                    player_ev = get_ev_from_row(row)
                    break
            
            loss = ai_ev - player_ev
            if loss > max_loss:
                max_loss = loss
                tehai, _ = extract_tiles(entry) # 分割せず全牌を取得
                
                max_loss_data = {
                    "kyoku": kyoku,
                    "turn": turn,
                    "tehai": tehai,
                    "player_discard": player_discard,
                    "player_ev": round(player_ev, 5),
                    "ai_discard": get_tile_id(ai_best_row.find("use")),
                    "ai_ev": round(ai_ev, 5),
                    "loss": round(loss, 5),
                    "commentary": "ここにAIからのコメントが入ります。"
                }
    return max_loss_data

if __name__ == "__main__":
    # 引数が指定されているかチェック
    if len(sys.argv) < 2:
        print("使い方: python script.py <path_to_html>")
        sys.exit(1)
    
    # コマンドライン引数からファイル名を取得
    html_file_path = sys.argv[1]
    
    # 処理を実行
    result = extract_max_loss_turn(html_file_path)
    print(json.dumps(result, indent=4, ensure_ascii=False))

    # JSONファイルとして保存
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(result,f, indent=4, ensure_ascii=False)

    print("data.json を出力しました。")