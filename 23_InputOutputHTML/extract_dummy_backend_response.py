"""
extract_dummy_backend_response.py

日本語版のレポートHTML（template_manyhands_v2.html 形式）から、半荘全部の局・巡目について
「バックエンドが返すJSON」(ダミー用)を抽出する。

使い方:
    python3 extract_dummy_backend_response.py template_manyhands_v2.html > dummy_backend_response.json

出力する各レコード（先頭7キーは、バックエンドの基本形式と同じ）:
    kyoku           "東1局" / "東2局 1本場" など
    turn            巡目
    tehai           手牌の牌コード（mjai表記）。閉じた手牌のみで、副露の牌は含めない。
                    ツモ牌／他家の打牌がある局面では、それが最後の1枚
    player_discard  自分の選択。打牌は牌コード。それ以外は 'スルー' '立直' 'ロン' 'ツモ'、
                    チー/ポンは鳴きに使う手牌2枚＋名前（例 '7s8sチー', 'ssポン'）
    ai_discard      AIの選択（表記は player_discard と同じ）
    loss            AIの選択のQ値 − 自分の選択のQ値（5桁）
    commentary      null（ダミーのコメントは app.py が注意局面にだけ付ける）

    --- 基本形式に無い局面を表すための任意キー（必要なときだけ付く）---
    trigger         ツモ牌の種類。省略＝'自摸'。'上家打' '対面打' '下家打'＝他家の打牌への判断
                    （tehai の最後がその牌）。null＝鳴いた直後でツモ牌なし
    melds           副露 [{"type": "chi"|"pon"|"daiminkan", "tiles": [...], "called": 牌, "from": "上家"|"対面"|"下家"}]
"""
import json
import re
import sys

from bs4 import BeautifulSoup

PLAIN_ACTIONS = ("スルー", "立直", "ロン", "ツモ")
FROM_BY_POS = {0: "上家", 1: "対面", 2: "下家"}        # 3枚の副露で、横向きの牌の位置 → 出し元


def tile_of(svg):
    return svg.find("use")["href"].replace("#pai-", "")


def signature(nodes):
    """牌(svg)とテキストの並びを 'T:7s|T:8s|チー' のような文字列にする"""
    parts = []
    for n in nodes:
        if getattr(n, "name", None) == "svg":
            parts.append("T:" + tile_of(n))
        else:
            t = re.sub(r"\s+", " ", n.get_text() if hasattr(n, "get_text") else str(n)).strip()
            if t:
                parts.append(t)
    return "|".join(parts)


def action_name(sig):
    """行動のシグネチャ → 'バックエンドの表記'。打牌は牌コード"""
    parts = sig.split("|")
    tiles = [p[2:] for p in parts if p.startswith("T:")]
    labels = [p for p in parts if not p.startswith("T:")]
    if labels == ["打"] and len(tiles) == 1:
        return tiles[0]
    if not tiles and labels and labels[0] in PLAIN_ACTIONS:
        return labels[0]
    if len(tiles) == 2 and labels in (["チー"], ["ポン"]):
        return "".join(tiles) + labels[0]
    raise ValueError(f"未対応の行動表記: {sig!r}")


def parse_meld(li):
    """副露の<li class=fuuro> → {"type","tiles","called","from"}"""
    items = [(tile_of(x.find("svg")), "rotated" in (x.get("class") or [])) for x in li.find_all("li")]
    if len(items) not in (3, 4) or sum(r for _, r in items) != 1:
        raise ValueError(f"未対応の副露の形: {items}")      # 加槓・暗槓などは未対応
    pos = [r for _, r in items].index(True)
    called = items[pos][0]
    others = [t for i, (t, _) in enumerate(items) if i != pos]
    if len(items) == 4:
        kind, src = "daiminkan", {0: "上家", 1: "対面"}.get(pos, "下家")
    elif len({t for t, _ in items}) == 1:
        kind, src = "pon", FROM_BY_POS[pos]
    else:
        kind, src = "chi", "上家"                              # チーは常に上家から。先頭が鳴いた牌
    tiles = [called] + others if kind == "chi" else [t for t, _ in items]
    return {"type": kind, "tiles": tiles, "called": called, "from": src}


def extract(html):
    soup = BeautifulSoup(html, "lxml")
    records, kyoku = [], None
    for el in soup.find_all(["h1", "details"]):
        classes = el.get("class") or []
        if el.name == "h1" and "kyoku-heading" in classes:
            kyoku = el.find("a", class_="chapter").get_text(strip=True)
            continue
        if not (el.name == "details" and "entry" in classes):
            continue

        turn = int(re.search(r"(\d+)巡目", el.find("summary").get_text()).group(1))
        lis = el.find("ul", class_="tehai-state", recursive=False).find_all("li", recursive=False)
        closed_lis = [li for li in lis if "fuuro" not in (li.get("class") or [])]
        tehai = [tile_of(li.find("svg")) for li in closed_lis]
        trigger_lis = [li for li in closed_lis if "tsumo" in (li.get("class") or [])]
        melds = [parse_meld(li) for li in lis if "fuuro" in (li.get("class") or [])]

        kids = list(el.children)
        player_sig = None
        for c in kids:
            if getattr(c, "name", None) == "span" and c.find("span", class_="role", recursive=False):
                role = c.find("span", class_="role", recursive=False)
                player_sig = signature([x for x in c.children if x is not role])
        ai_at = next(i for i, c in enumerate(kids) if getattr(c, "name", None) == "span"
                     and "role" in (c.get("class") or []) and "Mortal" in c.get_text())
        table_at = next(i for i, c in enumerate(kids) if getattr(c, "name", None) == "details")
        ai_sig = signature(kids[ai_at + 1:table_at])

        q = {}
        for tr in el.select("tbody > tr"):
            tds = tr.find_all("td", recursive=False)
            q.setdefault(signature(list(tds[0].children)), float(re.sub(r"\s+", "", tds[1].get_text())))
        loss = round(q[ai_sig] - q[player_sig], 5)

        rec = {
            "kyoku": kyoku, "turn": turn, "tehai": tehai,
            "player_discard": action_name(player_sig), "ai_discard": action_name(ai_sig),
            "loss": loss, "commentary": None,
        }
        # --- 任意キー ---
        if not trigger_lis:
            rec["trigger"] = None                              # 鳴いた直後: ツモ牌なし
        else:
            assert trigger_lis[0] is closed_lis[-1], "ツモ牌が手牌の末尾にありません"
            label = trigger_lis[0].get("before").strip()
            if label != "自摸":
                rec["trigger"] = label                         # 上家打 / 対面打 / 下家打
        if melds:
            rec["melds"] = melds
        records.append(rec)
    return records


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        data = extract(f.read())
    json.dump(data, sys.stdout, ensure_ascii=False, indent=1)
