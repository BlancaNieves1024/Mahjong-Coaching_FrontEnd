"""
extract_dummy_backend_response.py

日本語版のレポートHTML（template_manyhands_v2.html 形式・Mortal出力）から、半荘全部の局・巡目について
「バックエンドの返り値」(ダミー用)を抽出する。

返り値の形は、入力JSON仕様（ai-input-format.md）と同じ入れ子の形式。
バックエンドの返り値は「入力JSONの commentary にアドバイスを入れたもの」なので、同じ形になる。

使い方（リポジトリのルートで実行）:
    python apps/v2/tools/extract_dummy_backend_response.py prototypes/02_ScreenHTML/template_manyhands_v2.html apps/v2/data/dummy_backend_response.json

  出力先のファイルを指定すると、UTF-8（改行LF）で書き出す。出力先を省略すると標準出力に出す。
  （Windows PowerShell の「>」は、UTF-16で書き出してしまうため、出力先の指定を推奨）

出力する項目（元のレポートHTMLにあるものだけ。無い項目は出力しない）:
    meta        engine / kyoku / honba
    situation   turn / wall_remaining / trigger / trigger_actor / trigger_tile
    self        hand_with_trigger_tile / melds
    decision    player_choice / ai_choice / loss
    commentary  null

出さない項目: others / hidden_info / self.river / self.score / self.wind、decision の candidates や期待値。
  → 元のレポートに無い。結果画面も使わない（app.py は使う項目だけを読む）。

仕様書に例のない値（Mortal出力のダミーに現れるもの）:
    trigger が null（trigger_tile も null）    鳴いた直後の打牌判断（ツモ牌なし）
    player_choice / ai_choice の type          riichi（立直）/ tsumo（ツモ）
    type が chi / pon で then_discard が無い    鳴きだけの判断（鳴いたあとの打牌は別の局面）
"""
import json
import re
import sys

from bs4 import BeautifulSoup

PLAIN_ACTIONS = {"スルー": "skip", "立直": "riichi", "ロン": "ron", "ツモ": "tsumo"}
FROM_BY_POS = {0: "上家", 1: "対面", 2: "下家"}        # 3枚の副露で、横向きの牌の位置 → 出し元
LABEL_RE = re.compile(r"^(.*?局)(?:\s+(\d+)本場)?$")   # 『東2局 1本場』→ 局 / 本場


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


def choice_of(sig):
    """行動のシグネチャ → 構造化した行動 {"type": ...}"""
    parts = sig.split("|")
    tiles = [p[2:] for p in parts if p.startswith("T:")]
    labels = [p for p in parts if not p.startswith("T:")]
    if labels == ["打"] and len(tiles) == 1:
        return {"type": "discard", "tile": tiles[0]}
    if not tiles and len(labels) == 1 and labels[0] in PLAIN_ACTIONS:
        return {"type": PLAIN_ACTIONS[labels[0]]}
    if len(tiles) == 2 and labels in (["チー"], ["ポン"]):
        return {"type": "chi" if labels[0] == "チー" else "pon", "with_tiles": tiles}
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
    records, kyoku_label = [], None
    for el in soup.find_all(["h1", "details"]):
        classes = el.get("class") or []
        if el.name == "h1" and "kyoku-heading" in classes:
            kyoku_label = el.find("a", class_="chapter").get_text(strip=True)
            continue
        if not (el.name == "details" and "entry" in classes):
            continue

        summary = el.find("summary").get_text()
        turn = int(re.search(r"(\d+)巡目", summary).group(1))
        wall = int(re.search(r"残り(\d+)", summary).group(1))
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

        # --- きっかけ（ツモ牌／他家の打牌） ---
        if not trigger_lis:                                    # 鳴いた直後: ツモ牌なし
            trigger, actor, trigger_tile = None, None, None
        else:
            assert trigger_lis[0] is closed_lis[-1], "ツモ牌が手牌の末尾にありません"
            label = trigger_lis[0].get("before").strip()       # 自摸 / 上家打 / 対面打 / 下家打
            trigger_tile = tehai[-1]
            if label == "自摸":
                trigger, actor = "draw", "自分"
            else:
                trigger, actor = "opponent_discard", label.removesuffix("打")

        m = LABEL_RE.match(kyoku_label)
        situation = {"turn": turn, "wall_remaining": wall, "trigger": trigger}
        if actor:
            situation["trigger_actor"] = actor
        situation["trigger_tile"] = trigger_tile

        records.append({
            "meta": {"engine": "Mortal", "kyoku": m.group(1), "honba": int(m.group(2) or 0)},
            "situation": situation,
            "self": {"hand_with_trigger_tile": tehai, "melds": melds},
            "decision": {"player_choice": choice_of(player_sig), "ai_choice": choice_of(ai_sig), "loss": loss},
            "commentary": None,
        })
    return records


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("使い方: python extract_dummy_backend_response.py <レポートHTML> [<出力先.json>]")
    with open(sys.argv[1], encoding="utf-8") as f:
        data = extract(f.read())
    # 1局面 = 1行で出力（確認しやすく、差分も見やすい）
    text = "[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in data) + "\n]\n"
    if len(sys.argv) >= 3:
        with open(sys.argv[2], "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"{len(data)}局面を {sys.argv[2]} に書き出しました", file=sys.stderr)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(text)
