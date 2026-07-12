import json
import re
from bs4 import BeautifulSoup

def get_turn_info(entry):
    """summaryから「Turn X」という情報を抽出する"""
    summary = entry.find("summary").get_text(strip=True)
    # 例: "Turn 2 (×65)" -> 2 を取得
    match = re.search(r"Turn\s+(\d+)", summary, re.IGNORECASE)
    return int(match.group(1)) if match else None

def get_kyoku_name(entry):
    """現在のセクションのh1から局名を取得する"""
    section = entry.find_parent("section")
    if section:
        heading = section.find("h1", class_="kyoku-heading")
        return heading.get_text(strip=True) if heading else "Unknown"
    return "Unknown"


def get_ev_from_row(row):
    """行から期待値(pt EV)を取得してfloatに変換"""
    tds = row.find_all("td")
    if len(tds) < 2: return 0.0
    
    ev_td = tds[1]
    int_part = ev_td.find("span", class_="int")
    frac_part = ev_td.find("span", class_="frac")
    
    int_str = int_part.text.strip() if int_part else "0"
    frac_str = frac_part.text.strip() if frac_part else "0"
    
    # 結合して数値化（"-0."のケースなどに注意）
    val_str = int_str + frac_str
    try:
        return float(val_str)
    except:
        return 0.0

def get_tile_id(tag):
    """useタグから牌IDを取得"""
    if not tag: return None
    href = tag.get("href", "")
    return href.replace("#pai-", "")

def extract_tehai(entry):
    """
    エントリー内のすべての牌を探索してリスト化する
    (手牌+ツモ牌を区別せず、全ての手持ち牌として取得)
    """
    tehai = []
    # 局面内の tehai-state クラスを持つ ul を探す
    tehai_ul = entry.find("ul", class_="tehai-state")
    if not tehai_ul:
        return []
    
    # すべての use タグを取得
    for use_tag in tehai_ul.find_all("use"):
        href = use_tag.get("href", "")
        if "#pai-" in href:
            tile_id = href.replace("#pai-", "")
            tehai.append(tile_id)
            
    return tehai


def extract_max_loss_turn(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    max_loss = -1.0
    max_loss_data = None

    # 各局のセクションを探索
    for section in soup.find_all("section"):
        kyoku_name = section.find("h1", class_="kyoku-heading").get_text(strip=True)
        
        # 局面ごとのエントリーを探索
        for entry in section.find_all("details", class_="collapse entry"):
            # 巡目を取得
            summary = entry.find("summary").get_text(strip=True)
            turn_match = re.search(r"(\d+)巡目", summary)
            turn_num = int(turn_match.group(1)) if turn_match else 0

            table = entry.find("table", class_="data")
            if not table: continue
            rows = table.find("tbody").find_all("tr")
            
            # AIの推奨（期待値最大）
            ai_best_row = rows[0]
            ai_ev = get_ev_from_row(ai_best_row)
            ai_discard = get_tile_id(ai_best_row.find("use"))

            # プレイヤーの打牌を探索
            player_discard = None
            player_span = entry.find("span", style=lambda s: s and "background" in s)
            if player_span:
                player_discard = get_tile_id(player_span.find("use"))
            
            # プレイヤーの期待値を計算
            player_ev = ai_ev # スルー等の場合AI推奨と一致とみなす
            for row in rows:
                if get_tile_id(row.find("use")) == player_discard:
                    player_ev = get_ev_from_row(row)
                    break
            
            loss = ai_ev - player_ev
    # 損失(loss)の計算・比較処理の中
            if loss > max_loss:
                max_loss = loss
                
                # ここで手牌リストを取得
                current_tehai = extract_tehai(entry)
                
                max_loss_data = {
                    "kyoku": kyoku_name,
                    "turn": turn_num,
                    "tehai": current_tehai,  # 手牌を追加
                    "player_discard": player_discard,
                    "player_ev": round(player_ev, 5),
                    "ai_discard": ai_discard,
                    "ai_ev": round(ai_ev, 5),
                    "loss": round(loss, 5),
                }
    return max_loss_data



# --- 補助関数: 行から切った牌の種類を特定 ---
def get_discard_tile(row):
    """
    その行にある牌情報を正確に取得する関数。
    """
    # 行の中に<use>タグが複数ある場合、最初のものだけでなく
    # 状況に応じて取得する対象を特定する必要がある
    use_tags = row.find_all("use")
    if not use_tags:
        return None
    
    # 基本は最初のタグを返すが、もし「Player」の表記と近接している場合は
    # 構造を確認する必要がある。
    # 今回のケースでは、最初の<use>がその行の打牌を表しているはず。
    return use_tags[0].get("href", "").replace("#pai-", "")

def get_player_discard(entry):
    """
    Playerの打牌を特定する専用関数
    """
    # <span style="background:#ffd5d5"> の中の <use> を探すのが確実
    player_span = entry.find("span", style=lambda s: s and "background" in s)
    if player_span:
        use_tag = player_span.find("use")
        if use_tag:
            return use_tag.get("href", "").replace("#pai-", "")
    
    # それが見つからない場合は、"Player:" という文字を含むタグを探す
    for span in entry.find_all("span"):
        if "Player:" in span.text:
            use_tag = span.find("use")
            if use_tag:
                return use_tag.get("href", "").replace("#pai-", "")
    return None

# === 実行テスト ===
if __name__ == "__main__":
    # あなたの 'report.html' を解析
    result = extract_max_loss_turn("report.html")

    # 結果をJSON形式で綺麗に画面に表示
    print(json.dumps(result, indent=4, ensure_ascii=False))