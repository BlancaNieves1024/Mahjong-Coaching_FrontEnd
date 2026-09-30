"""
extract_backend_output.py

mjai-reviewer が生成する牌譜検討レポート (template.html) から、
各局・各巡目について「バックエンドが返すべきJSON」相当のデータを抽出するスクリプト。

出力される各レコードのスキーマ（ユーザー提示の dummy_response と同一）:
    {
        "kyoku": str,           # 例: "東1局", "東2局 1本場"
        "turn": int,            # 巡目
        "tehai": list[str],     # 手牌（自摸牌を含む）。牌コードは mjai 記法（例: "5sr" = 赤5索）
        "player_discard": str,  # プレイヤーの選択（打牌の場合は牌コード、それ以外は "立直"/"ツモ"/"ロン"/"スルー"/"XXポン"等）
        "player_ev": float,     # プレイヤーの選択の期待値 (Q値)
        "ai_discard": str,      # Mortal(AI)の選択
        "ai_ev": float,         # Mortal(AI)の選択の期待値 (Q値)
        "loss": float,          # ai_ev - player_ev（AIの選択に対する損失。正の値ほど損）
        "commentary": str|None  # AIからのアドバイス文（現状のテンプレートにはプレースホルダーしか無いため None）
    }

使い方:
    python3 extract_backend_output.py report.html > backend_output.json
"""

import sys
import re
import json
from bs4 import BeautifulSoup


def sig_of_nodes(nodes):
    """牌(svg)とテキストの並びを 'T:5s|打' のような比較用の文字列に変換する"""
    parts = []
    for n in nodes:
        if getattr(n, "name", None) == "svg":
            use = n.find("use")
            href = use.get("href") if use else ""
            parts.append("T:" + (href or "").replace("#pai-", ""))
        elif getattr(n, "name", None) is None:
            t = re.sub(r"\s+", " ", str(n)).strip()
            if t:
                parts.append(t)
        else:
            t = re.sub(r"\s+", " ", n.get_text()).strip()
            if t:
                parts.append(t)
    return "|".join(parts)


def sig_to_display(sig):
    """比較用シグネチャを人間可読な表記（牌コード or 行動名）に変換する"""
    parts = sig.split("|")
    tiles = [p[2:] for p in parts if p.startswith("T:")]
    labels = [p for p in parts if not p.startswith("T:")]
    if len(tiles) == 1 and labels == ["打"]:
        return tiles[0]
    return "".join(tiles) + "".join(labels)


def parse_q(td):
    if td is None:
        return None
    t = re.sub(r"\s+", "", td.get_text())
    try:
        return float(t)
    except ValueError:
        return None


def tile_list(ul):
    tiles = []
    for li in ul.find_all("li", recursive=False):
        svg = li.find("svg")
        if svg:
            use = svg.find("use")
            href = use.get("href") if use else ""
            tiles.append((href or "").replace("#pai-", ""))
    return tiles


def extract(html: str):
    soup = BeautifulSoup(html, "lxml")
    results = []
    current_kyoku = None

    for el in soup.find_all(["h1", "details"]):
        if el.name == "h1" and "kyoku-heading" in (el.get("class") or []):
            a = el.find("a", class_="chapter")
            current_kyoku = a.get_text(strip=True) if a else None
            continue

        if el.name == "details" and "entry" in (el.get("class") or []):
            entry = el
            summary = entry.find("summary", recursive=False)
            summary_text = summary.get_text() if summary else ""
            m = re.search(r"(\d+)巡目", summary_text)
            turn = int(m.group(1)) if m else None

            children = list(entry.children)
            player_nodes = None
            mortal_role_idx = None
            table_details = None
            table_details_idx = None
            for i, node in enumerate(children):
                if getattr(node, "name", None) == "span":
                    role_child = node.find("span", class_="role", recursive=False)
                    if role_child and "プレイヤー" in role_child.get_text():
                        player_nodes = [c for c in node.children if c is not role_child]
                    elif node.get("class") and "role" in node.get("class") and "Mortal" in node.get_text():
                        mortal_role_idx = i
                if getattr(node, "name", None) == "details":
                    table_details = node
                    table_details_idx = i

            if player_nodes is None or mortal_role_idx is None or table_details is None:
                continue

            mortal_nodes = children[mortal_role_idx + 1:table_details_idx]
            table = table_details.find("table", class_="data")
            tbody = table.find("tbody") if table else None
            rows = tbody.find_all("tr", recursive=False) if tbody else []

            player_sig = sig_of_nodes(player_nodes)
            mortal_sig = sig_of_nodes(mortal_nodes)
            player_q = None
            mortal_q = None
            for row in rows:
                tds = row.find_all("td", recursive=False)
                if len(tds) < 2:
                    continue
                sig = sig_of_nodes(list(tds[0].children))
                if sig == player_sig and player_q is None:
                    player_q = parse_q(tds[1])
                if sig == mortal_sig and mortal_q is None:
                    mortal_q = parse_q(tds[1])

            ul = entry.find("ul", class_="tehai-state", recursive=False)
            tehai = tile_list(ul) if ul else []

            results.append({
                "kyoku": current_kyoku,
                "turn": turn,
                "tehai": tehai,
                "player_discard": sig_to_display(player_sig),
                "player_ev": round(player_q, 2) if player_q is not None else None,
                "ai_discard": sig_to_display(mortal_sig),
                "ai_ev": round(mortal_q, 2) if mortal_q is not None else None,
                "loss": round(mortal_q - player_q, 2) if (player_q is not None and mortal_q is not None) else None,
                "commentary": None,
            })

    return results


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "template.html"
    with open(path, encoding="utf-8") as f:
        html = f.read()
    data = extract(html)
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
