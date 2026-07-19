import json
from jinja2 import Template
# 牌の変換テーブル
# TILE_MAP = {
#     '1m': '[一萬]', '2m': '[二萬]', '3m': '[三萬]', '4m': '[四萬]', '5m': '[五萬]', '6m': '[六萬]', '7m': '[七萬]', '8m': '[八萬]', '9m': '[九萬]',
#     '1p': '[一筒]', '2p': '[二筒]', '3p': '[三筒]', '4p': '[四筒]', '5p': '[五筒]', '6p': '[六筒]', '7p': '[七筒]', '8p': '[八筒]', '9p': '[九筒]',
#     '1s': '[一索]', '2s': '[二索]', '3s': '[三索]', '4s': '[四索]', '5s': '[五索]', '6s': '[六索]', '7s': '[七索]', '8s': '[八索]', '9s': '[九索]',
#     '5mr': '[五萬(赤)]','5pr': '[五筒(赤)]', '5sr': '[五索(赤)]',# 赤ドラ
#     'e': '[東]', 's_n': '[南]', 'w': '[西]', 'n': '[北]',
#     'h': '[白]', 'f': '[發]', 'c': '[中]'
# }

TILE_MAP = {
    '1m': '🀇', '2m': '🀈', '3m': '🀉', '4m': '🀊', '5m': '🀋', '6m': '🀌', '7m': '🀍', '8m': '🀎', '9m': '🀏',
    '1p': '🀙', '2p': '🀚', '3p': '🀛', '4p': '🀜', '5p': '🀝', '6p': '🀞', '7p': '🀟', '8p': '🀠', '9p': '🀡',
    '1s': '🀐', '2s': '🀑', '3s': '🀒', '4s': '🀓', '5s': '🀔', '6s': '🀕', '7s': '🀖', '8s': '🀗', '9s': '🀘',
    '5mr': '🀋(赤)','5pr': '🀝(赤)', '5sr': '🀔(赤)',# 赤ドラ
    'e': '🀀', 's_n': '🀁', 'w': '🀂', 'n': '🀃',
    'h': '🀆', 'f': '🀅', 'c': '🀄'
}

def convert_tiles(tile_code):
    """牌コードを日本語の文字列に変換する"""
    return TILE_MAP.get(tile_code, f"[{tile_code}]") # 定義外ならそのまま返す

# 1. 保存されたJSONを読み込む
with open('data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# --- 変換処理を追加 ---
# 手牌リストを変換
data['tehai'] = [convert_tiles(t) for t in data['tehai']]
# 打牌を変換
data['player_discard'] = convert_tiles(data['player_discard'])
data['ai_discard'] = convert_tiles(data['ai_discard'])
# --------------------

# 2. HTMLテンプレートの読み込み
with open('template.html', 'r', encoding='utf-8') as f:
    template = Template(f.read())

# 3. 結合して保存
rendered_html = template.render(data)
with open('analysis_result.html', 'w', encoding='utf-8') as f:
    f.write(rendered_html)

print("analysis_result.html を生成しました。")