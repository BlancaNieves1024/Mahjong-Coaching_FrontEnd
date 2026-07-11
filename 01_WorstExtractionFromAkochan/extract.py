import json
import re
from bs4 import BeautifulSoup


def extract_max_loss_turn(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    max_loss = -1.0
    max_loss_data = None

    # 1. ページ内のすべての section を取得
    sections = soup.find_all("section")
    
    # 2. それぞれの section ごとにループを回す
    for section in sections:
        kyoku_id = section.find("h1", class_="kyoku-heading")
        kyoku_name = (
            kyoku_id.find("a").text.strip()
            if kyoku_id and kyoku_id.find("a")
            else "Unknown"
        )

        # 3. section の中にある r-box を探す
        entries = section.find_all("div", class_="r-box")
        for entry in entries:
            summary = entry.find("summary")
            if not summary: continue
            
            turn_match = re.search(r"Turn\s+(\d+)", summary.text)
            if not turn_match: continue
            turn_num = int(turn_match.group(1))

            table = entry.find("table", class_="data")
            if not table: continue

            # 行の取得
            rows = table.find("tbody").find_all("tr")
            if not rows: continue
            
            ai_ev = get_ev_from_row(rows[0])
            ai_discard = get_discard_tile(rows[0])
            
            player_discard = get_player_discard(entry)
            player_ev = ai_ev 
            for row in rows:
                if get_discard_tile(row) == player_discard:
                    player_ev = get_ev_from_row(row)
                    break
            
            loss = ai_ev - player_ev

            if loss > max_loss:
                max_loss = loss
                
                # 手牌の取得
                tehai = []
                tsumo = None
                tehai_ul = entry.find("ul", class_="tehai-state")
                if tehai_ul:
                    for li in tehai_ul.find_all("li"):
                        use_tag = li.find("use")
                        if not use_tag: continue
                        tile_id = use_tag.get("href", "").replace("#pai-", "")
                        if "tsumo" in li.get("class", []) or li.get("before") == "Draw ":
                            tsumo = tile_id
                        else:
                            tehai.append(tile_id)

                max_loss_data = {
                    "kyoku": kyoku_name,
                    "turn": turn_num,
                    "tehai": tehai,
                    "tsumo": tsumo,
                    "player_discard": player_discard,
                    "player_ev": round(player_ev, 5),
                    "ai_discard": ai_discard,
                    "ai_ev": round(ai_ev, 5),
                    "loss": round(loss, 5),
                }

    return max_loss_data


# --- 補助関数: 行から期待値(pt EV)を計算 ---
def get_ev_from_row(row):
    tds = row.find_all("td")
    if len(tds) < 2:
        return 0.0
    ev_td = tds[1]  # 2番目の列が pt EV
    int_part = ev_td.find("span", class_="int")
    frac_part = ev_td.find("span", class_="frac")

    int_str = int_part.text.strip() if int_part else "0"
    frac_str = frac_part.text.strip() if frac_part else "0"

    # 整数部が "-" だけの場合は "-0" に補正
    if int_str == "-":
        int_str = "-0"

    return float(f"{int_str}{frac_str}")


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
    result = extract_max_loss_turn("66f2c0014f2c8ea4.html")

    # 結果をJSON形式で綺麗に画面に表示
    print(json.dumps(result, indent=4, ensure_ascii=False))