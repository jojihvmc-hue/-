# 国土地理院のベクトルタイル(建物)と航空写真を、交差点中心のローカル座標(m)に変換する
# 実行: python3 prep_data.py   → data/buildings.json, data/ground.jpg, data/check.png
import math, json, glob, os, random
import mapbox_vector_tile as mvt
from shapely.geometry import Polygon, MultiPolygon, box as sbox
from shapely.ops import unary_union
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")
LAT0, LON0 = 35.65950, 139.70055          # スクランブル交差点の中心
KX = 111320 * math.cos(math.radians(LAT0))  # 経度1度あたりのm
KY = 110574                                  # 緯度1度あたりのm
R = 320                                      # モデル化する半径 (m)


def to_local(lon, lat):
    return ((lon - LON0) * KX, (lat - LAT0) * KY)


def tile_to_lonlat(tx, ty, z, fx, fy):
    n = 2 ** z
    lon = (tx + fx) / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty + fy) / n))))
    return lon, lat


# ---------- 建物 ----------
pieces, edge_pieces = [], []
for p in glob.glob(os.path.join(D, "bv_16_*.pbf")):
    _, _, tx, ty = os.path.basename(p)[:-4].split("_")
    tx, ty = int(tx), int(ty)
    layer = mvt.decode(open(p, "rb").read(), default_options={"y_coord_down": True})["building"]
    ext = layer["extent"]
    corners = [to_local(*tile_to_lonlat(tx, ty, 16, a, b)) for a, b in [(0, 0), (1, 1)]]
    tbox = sbox(min(corners[0][0], corners[1][0]), min(corners[0][1], corners[1][1]),
                max(corners[0][0], corners[1][0]), max(corners[0][1], corners[1][1]))
    for f in layer["features"]:
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else (
            g["coordinates"] if g["type"] == "MultiPolygon" else [])
        for rings in polys:
            conv = [[to_local(*tile_to_lonlat(tx, ty, 16, x / ext, y / ext)) for x, y in r] for r in rings]
            try:
                poly = Polygon(conv[0], conv[1:]).buffer(0)
            except Exception:
                continue
            if poly.is_empty or poly.area < 4:
                continue
            item = (poly, f["properties"].get("ftCode", 3101))
            # タイル境界で切れた建物は後で隣とつなぐ
            if poly.distance(tbox.exterior) < 0.3:
                edge_pieces.append(item)
            else:
                pieces.append(item)

# 境界に接する断片を結合
merged = unary_union([p for p, _ in edge_pieces]).buffer(0.05).buffer(-0.05)
geoms = list(merged.geoms) if isinstance(merged, MultiPolygon) else [merged]
for g in geoms:
    codes = [c for p, c in edge_pieces if p.intersects(g)]
    pieces.append((g, max(codes) if codes else 3101))

# 有名な建物の高さ (公開されている概略値, m)。中心付近にある最大の建物に当てはめる
# 有名な建物の高さ (公開されている概略値, m)。位置はローカル座標(m)で、航空写真と照合済み
# (name, x, y, 高さ, 探索半径)。足元に建物ポリゴンが無ければ箱で補う
LANDMARKS = [
    ("渋谷スクランブルスクエア", 160, -125, 230, 30),
    ("渋谷ヒカリエ",             284, -55, 183, 30),
    ("渋谷ストリーム",           194, -243, 180, 25),
    ("渋谷サクラステージ",       -14, -300, 179, 25),
    ("渋谷フクラス",             -86, -199, 103, 25),
    ("QFRONT",                   -15, 40, 37, 10),
    ("MAGNET by SHIBUYA109",     -73, 36, 45, 10),
    ("SHIBUYA109",               -132, 6, 50, 12),
    ("西武渋谷店",               -32, 150, 40, 15),
]

random.seed(7)
out = []
lm_used = {}
cands = []
for poly, code in pieces:
    c = poly.centroid
    if math.hypot(c.x, c.y) > R:
        continue
    cands.append((poly, code))

from shapely.geometry import Point
extra = []
for name, x, y, h, rad in LANDMARKS:
    pt = Point(x, y)
    inside = [i for i, (p, _) in enumerate(cands) if p.contains(pt) and i not in lm_used]
    near = inside or [i for i, (p, _) in enumerate(cands) if p.distance(pt) < rad and i not in lm_used]
    if near:
        i = max(near, key=lambda i: cands[i][0].area)
        lm_used[i] = (name, h)
    else:
        extra.append((name, Polygon([(x-25, y-20), (x+25, y-20), (x+25, y+20), (x-25, y+20)]), h))
    # 低層部(マークシティ等)は別扱い

for i, (poly, code) in enumerate(cands):
    a = poly.area
    if i in lm_used:
        name, h = lm_used[i]
    else:
        name = None
        if code == 3103:
            h = random.uniform(40, 65)
        elif code == 3102:
            # 面積が大きいほど高いビルになりやすい
            h = random.uniform(11, 20) + min(a / 90, 22) * random.uniform(0.3, 1.0)
        else:
            h = random.uniform(6, 11)
    simp = poly.simplify(0.25)
    ext = list(simp.exterior.coords)[:-1]
    if len(ext) < 3:
        continue
    out.append({"name": name, "code": code, "h": round(h, 1),
                "outer": [[round(x, 2), round(y, 2)] for x, y in ext],
                "holes": [[[round(x, 2), round(y, 2)] for x, y in list(r.coords)[:-1]] for r in simp.interiors]})

for name, poly, h in extra:
    out.append({"name": name, "code": 3103, "h": h, "outer": [list(c) for c in list(poly.exterior.coords)[:-1]], "holes": []})
# マークシティ: 低層の長い建物 + 東西2本のタワー
for b in out:
    c = Polygon(b["outer"]).centroid
    if -320 < c.x < -60 and -200 < c.y < -40 and Polygon(b["outer"]).area > 3000:
        b["name"], b["h"] = "渋谷マークシティ(低層部)", 28
for name, x, y in [("マークシティ イースト", -110, -80), ("マークシティ ウエスト", -230, -150)]:
    out.append({"name": name, "code": 3103, "h": 98, "outer": [[x-18, y-14], [x+18, y-14], [x+18, y+14], [x-18, y+14]], "holes": []})
json.dump(out, open(os.path.join(D, "buildings.json"), "w"), ensure_ascii=False)
print("buildings:", len(out), "landmarks:", [v[0] for v in lm_used.values()])

# ---------- 航空写真 (z18) をモザイクして切り抜き ----------
z = 18
tiles = glob.glob(os.path.join(D, "photo", "18_*.jpg"))
txs = sorted({int(os.path.basename(t).split("_")[1]) for t in tiles})
tys = sorted({int(os.path.basename(t).split("_")[2][:-4]) for t in tiles})
mos = Image.new("RGB", (256 * len(txs), 256 * len(tys)))
for t in tiles:
    _, a, b = os.path.basename(t)[:-4].split("_")
    mos.paste(Image.open(t), ((int(a) - txs[0]) * 256, (int(b) - tys[0]) * 256))
# モザイク左上・右下のローカル座標
x0, y1 = to_local(*tile_to_lonlat(txs[0], tys[0], z, 0, 0))
x1, y0 = to_local(*tile_to_lonlat(txs[-1], tys[-1], z, 1, 1))
G = 330  # 地面は ±330m
W, H = mos.size
crop = (int((-G - x0) / (x1 - x0) * W), int((y1 - G) / (y1 - y0) * H),
        int((G - x0) / (x1 - x0) * W), int((y1 + G) / (y1 - y0) * H))
ground = mos.crop(crop)
ground.save(os.path.join(D, "ground.jpg"), quality=92)
json.dump({"half_size": G}, open(os.path.join(D, "ground.json"), "w"))
print("ground px:", ground.size)

# ---------- 確認用の図 ----------
from PIL import ImageDraw
chk = ground.copy().convert("RGB")
dr = ImageDraw.Draw(chk, "RGBA")
s = chk.size[0] / (2 * G)
for b in out:
    pts = [((x + G) * s, (G - y) * s) for x, y in b["outer"]]
    col = (255, 0, 0, 90) if b["name"] else (0, 200, 255, 50)
    dr.polygon(pts, fill=col, outline=(255, 255, 0, 255))
chk.save(os.path.join(D, "check.png"))
