# 渋谷スクランブル交差点周辺の3Dシーンを作る Blender スクリプト
# 実行: blender -b -P build_shibuya.py  → shibuya.blend
# 座標: 交差点中心を原点, X=東, Y=北, Z=上 (m)
import bpy, bmesh, json, math, os, random
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")
random.seed(42)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
FPS, NFRAMES = 24, 192
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 1, NFRAMES

C = Vector((-4.0, 2.0, 0))  # 交差点の中心 (航空写真から)


# ================= マテリアル =================
def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links


def simple(name, rgb, rough=0.6, metal=0.0, emit=0.0):
    m, n, _ = new_mat(name)
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*rgb, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


def facade_material():
    """UV(u=壁沿いの距離m, v=高さm)から窓のグリッドを作る外壁マテリアル"""
    m, n, l = new_mat("Facade")
    out = n["Material Output"]
    n.remove(n["Principled BSDF"])

    def node(t, **kw):
        x = n.new(t)
        for k, v in kw.items():
            setattr(x, k, v)
        return x

    def math_(op, a, b=None, val=None):
        x = node("ShaderNodeMath", operation=op)
        l.new(a, x.inputs[0]) if not isinstance(a, (int, float)) else setattr(x.inputs[0], "default_value", a)
        if b is not None:
            l.new(b, x.inputs[1]) if not isinstance(b, (int, float)) else setattr(x.inputs[1], "default_value", b)
        return x.outputs[0]

    uv = node("ShaderNodeTexCoord")
    sep = node("ShaderNodeSeparateXYZ")
    l.new(uv.outputs["UV"], sep.inputs[0])
    obj = node("ShaderNodeObjectInfo")
    rnd = obj.outputs["Random"]
    glassy = node("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="glassy").outputs["Fac"]

    # 建物ごとに窓の幅・階高を少し変える
    ww = math_("MULTIPLY_ADD", rnd, 1.6, val=None)
    n_ = ww.node
    n_.inputs[2].default_value = 1.8
    fh = math_("MULTIPLY_ADD", rnd, 0.6)
    fh.node.inputs[2].default_value = 3.3
    u = math_("DIVIDE", sep.outputs[0], ww)
    v = math_("DIVIDE", sep.outputs[1], fh)
    fu, fv = math_("FRACT", u), math_("FRACT", v)
    # 窓の開口率: 通常ビル / ガラス張り(glassy)で切り替え
    mx = math_("MULTIPLY_ADD", glassy, -0.1)
    mx.node.inputs[2].default_value = 0.15
    my = math_("MULTIPLY_ADD", glassy, -0.18)
    my.node.inputs[2].default_value = 0.25
    a1 = math_("GREATER_THAN", fu, mx)
    a2 = math_("LESS_THAN", fu, math_("SUBTRACT", 1.0, mx))
    a3 = math_("GREATER_THAN", fv, my)
    a4 = math_("LESS_THAN", fv, 0.88)
    ribbon = node("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="ribbon").outputs["Fac"]
    win = math_("MULTIPLY", math_("MAXIMUM", math_("MULTIPLY", a1, a2), ribbon), math_("MULTIPLY", a3, a4))
    # 1階は店舗のガラス
    ground = math_("LESS_THAN", sep.outputs[1], 4.2)
    gwin = math_("MULTIPLY", ground, math_("GREATER_THAN", sep.outputs[1], 0.3))

    # 壁の色 (建物ごとにランダム)
    ramp = node("ShaderNodeValToRGB")
    l.new(rnd, ramp.inputs[0])
    cols = [(0.0, (0.55, 0.53, 0.50)), (0.2, (0.72, 0.68, 0.60)), (0.4, (0.80, 0.80, 0.78)),
            (0.55, (0.35, 0.33, 0.32)), (0.7, (0.62, 0.55, 0.46)), (0.85, (0.50, 0.55, 0.58)),
            (1.0, (0.78, 0.74, 0.70))]
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = cols[0][0], (*cols[0][1], 1)
    els[1].position, els[1].color = cols[1][0], (*cols[1][1], 1)
    for p, c in cols[2:]:
        e = els.new(p)
        e.color = (*c, 1)
    # 汚れ・ムラ
    noise = node("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.4
    l.new(uv.outputs["UV"], noise.inputs["Vector"])
    dirt = node("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    dirt.inputs["Factor"].default_value = 0.25
    l.new(ramp.outputs[0], dirt.inputs[6])
    l.new(noise.outputs["Color"], dirt.inputs[7])

    wall = node("ShaderNodeBsdfPrincipled")
    l.new(dirt.outputs[2], wall.inputs["Base Color"])
    wall.inputs["Roughness"].default_value = 0.75

    glass = node("ShaderNodeBsdfPrincipled")
    gcol = node("ShaderNodeMix", data_type="RGBA")
    l.new(rnd, gcol.inputs["Factor"])
    gcol.inputs[6].default_value = (0.06, 0.09, 0.12, 1)
    gcol.inputs[7].default_value = (0.12, 0.16, 0.20, 1)
    l.new(gcol.outputs[2], glass.inputs["Base Color"])
    glass.inputs["Roughness"].default_value = 0.04
    glass.inputs["Metallic"].default_value = 0.6

    shop = node("ShaderNodeBsdfPrincipled")
    shop.inputs["Base Color"].default_value = (0.07, 0.07, 0.08, 1)
    shop.inputs["Roughness"].default_value = 0.1
    shop.inputs["Emission Color"].default_value = (1.0, 0.85, 0.65, 1)
    shop.inputs["Emission Strength"].default_value = 0.08

    mix1 = node("ShaderNodeMixShader")
    l.new(win, mix1.inputs[0])
    l.new(wall.outputs[0], mix1.inputs[1])
    l.new(glass.outputs[0], mix1.inputs[2])
    mix2 = node("ShaderNodeMixShader")
    l.new(gwin, mix2.inputs[0])
    l.new(mix1.outputs[0], mix2.inputs[1])
    l.new(shop.outputs[0], mix2.inputs[2])
    l.new(mix2.outputs[0], out.inputs[0])
    return m


def roof_material():
    m, n, l = new_mat("Roof")
    b = n["Principled BSDF"]
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.15
    tc = n.new("ShaderNodeTexCoord")
    l.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.35, 0.35, 0.34, 1)
    ramp.color_ramp.elements[1].color = (0.62, 0.62, 0.60, 1)
    l.new(noise.outputs["Fac"], ramp.inputs[0])
    l.new(ramp.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.85
    return m


def screen_material(name, seed):
    """大型ビジョン: 時間で流れるカラフルな映像"""
    m, n, l = new_mat(name)
    n.remove(n["Principled BSDF"])
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    l.new(tc.outputs["UV"], mp.inputs[0])
    mp.inputs["Scale"].default_value = (3, 2, 1)
    # Wタイムで動かす
    mp.inputs["Location"].default_value = (seed, 0, 0)
    mp.inputs["Location"].keyframe_insert("default_value", frame=1)
    mp.inputs["Location"].default_value = (seed + 2.5, 0.8, 0)
    mp.inputs["Location"].keyframe_insert("default_value", frame=NFRAMES)
    wave = n.new("ShaderNodeTexMagic")
    wave.turbulence_depth = 3
    wave.inputs["Scale"].default_value = 1.2
    l.new(mp.outputs[0], wave.inputs[0])
    hue = n.new("ShaderNodeHueSaturation")
    hue.inputs["Hue"].default_value = (seed * 0.37) % 1
    hue.inputs["Saturation"].default_value = 1.4
    l.new(wave.outputs["Color"], hue.inputs["Color"])
    em = n.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 6
    l.new(hue.outputs[0], em.inputs[0])
    l.new(em.outputs[0], n["Material Output"].inputs[0])
    for fc in m.node_tree.animation_data.action.fcurves:
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"
    return m


M_FACADE = facade_material()
M_ROOF = roof_material()
M_ROOFBOX = simple("RoofBox", (0.70, 0.70, 0.68), 0.7)


# ================= 地面 (航空写真) =================
G = json.load(open(os.path.join(D, "ground.json")))["half_size"]
bpy.ops.mesh.primitive_plane_add(size=2 * G, location=(0, 0, 0))
ground = bpy.context.object
ground.name = "Ground_Aerial"
m, n, l = new_mat("Aerial")
img = n.new("ShaderNodeTexImage")
img.image = bpy.data.images.load(os.path.join(D, "ground.jpg"))
img.interpolation = "Cubic"
b = n["Principled BSDF"]
bright = n.new("ShaderNodeBrightContrast")
bright.inputs["Bright"].default_value = -0.02
bright.inputs["Contrast"].default_value = 0.25
hs = n.new("ShaderNodeHueSaturation")
hs.inputs["Saturation"].default_value = 1.25
hs.inputs["Value"].default_value = 0.85
l.new(img.outputs[0], bright.inputs[0])
l.new(bright.outputs[0], hs.inputs["Color"])
l.new(hs.outputs[0], b.inputs["Base Color"])
b.inputs["Roughness"].default_value = 0.8
ground.data.materials.append(m)
# 外側の地面
bpy.ops.mesh.primitive_plane_add(size=4000, location=(0, 0, -0.05))
bpy.context.object.data.materials.append(simple("FarGround", (0.25, 0.25, 0.25), 0.9))

# ================= 建物 =================
blds = json.load(open(os.path.join(D, "buildings.json")))
coll = bpy.data.collections.new("Buildings")
scene.collection.children.link(coll)
screens = []


def signed_area(pts):
    return sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts))) / 2


for i, bd in enumerate(blds):
    pts = bd["outer"]
    if signed_area(pts) > 0:  # 時計回り→反時計回りへ (signed_area定義上の向きに合わせる)
        pts = pts[::-1]
    h = bd["h"]
    me = bpy.data.meshes.new(f"B{i}")
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    bot = [bm.verts.new((x, y, 0)) for x, y in pts]
    top = [bm.verts.new((x, y, h)) for x, y in pts]
    k = len(pts)
    ucum = 0.0
    for j in range(k):
        a, b2 = j, (j + 1) % k
        f = bm.faces.new((bot[a], bot[b2], top[b2], top[a]))
        f.material_index = 0
        L = (Vector(pts[b2]) - Vector(pts[a])).length
        for loop, (uu, vv) in zip(f.loops, [(ucum, 0), (ucum + L, 0), (ucum + L, h), (ucum, h)]):
            loop[uvl].uv = (uu, vv)
        ucum += L
    try:
        rf = bm.faces.new(top)
        rf.material_index = 1
    except ValueError:
        pass
    bm.normal_update()
    # 壁の法線が外向きになるよう揃える
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(bd["name"] or f"Bldg_{i}", me)
    me.materials.append(M_FACADE)
    me.materials.append(M_ROOF)
    ob["glassy"] = 1.0 if h > 90 else (0.6 if random.random() < 0.25 else 0.0)
    ob["ribbon"] = 1.0 if (h <= 90 and random.random() < 0.3) else 0.0
    # 屋上の設備 (室外機・塔屋・給水タンク)
    cx_ = sum(p[0] for p in pts) / len(pts)
    cy_ = sum(p[1] for p in pts) / len(pts)
    if math.hypot(cx_ - C.x, cy_ - C.y) < 180 and h < 120:
        poly_r = (sum((Vector(p) - Vector((cx_, cy_))).length for p in pts) / len(pts)) * 0.35
        for _ in range(random.randint(1, 4)):
            bw, bd_, bh = random.uniform(1.5, 5), random.uniform(1.5, 5), random.uniform(1.2, 3.5)
            ox, oy = random.uniform(-poly_r, poly_r), random.uniform(-poly_r, poly_r)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(cx_ + ox, cy_ + oy, h + bh / 2))
            rb = bpy.context.object
            rb.scale = (bw, bd_, bh)
            rb.data.materials.append(M_ROOFBOX)
    coll.objects.link(ob)

    # 交差点に面したビルには看板・大型ビジョンを付ける
    cen = Vector((sum(p[0] for p in pts) / k, sum(p[1] for p in pts) / k))
    dist = (cen - C.xy).length
    want_screen = bd["name"] in ("QFRONT", "MAGNET by SHIBUYA109", "SHIBUYA109", "西武渋谷店") or (
        dist < 110 and 12 < h < 80 and random.random() < 0.45)
    if want_screen:
        # 交差点に一番近い壁を探す
        best = None
        for j in range(k):
            p0, p1 = Vector(pts[j]), Vector(pts[(j + 1) % k])
            L = (p1 - p0).length
            if L < 6:
                continue
            mid = (p0 + p1) / 2
            dd = (mid - C.xy).length
            if best is None or dd < best[0]:
                best = (dd, p0, p1, L)
        if best:
            _, p0, p1, L = best
            sw = min(L * 0.75, 22 if bd["name"] == "QFRONT" else 14)
            sh = min(h * 0.5, sw * 0.7 if bd["name"] == "QFRONT" else sw * 0.6)
            z0 = max(6, h * 0.35) if bd["name"] != "QFRONT" else 12
            if z0 + sh > h - 1:
                sh = max(3, h - 1 - z0)
            screens.append((p0, p1, sw, sh, z0, len(screens)))

# 大型ビジョン/看板の生成
for p0, p1, sw, sh, z0, sid in screens:
    d = (p1 - p0).normalized()
    nrm = Vector((d.y, -d.x))
    mid = (p0 + p1) / 2
    if (mid + nrm - C.xy).length > (mid - C.xy).length:  # 交差点側を向かせる
        nrm = -nrm
    c = mid + nrm * 0.35
    bpy.ops.mesh.primitive_plane_add(size=1)
    sc = bpy.context.object
    sc.name = f"Screen_{sid}"
    sc.scale = (sw, sh, 1)
    sc.rotation_euler = (math.pi / 2, 0, math.atan2(nrm.y, nrm.x) + math.pi / 2)
    sc.location = (c.x, c.y, z0 + sh / 2)
    sc.data.materials.append(screen_material(f"ScreenMat_{sid}", sid * 1.7 + 0.3))
    # 黒い枠
    bpy.ops.mesh.primitive_cube_add(size=1)
    fr = bpy.context.object
    fr.scale = (sw + 0.6, 0.3, sh + 0.6)
    fr.rotation_euler = (0, 0, math.atan2(nrm.y, nrm.x) + math.pi / 2)
    fr.location = (c.x - nrm.x * 0.2, c.y - nrm.y * 0.2, z0 + sh / 2)
    fr.data.materials.append(simple("ScreenFrame", (0.03, 0.03, 0.03), 0.4))

# ================= 袖看板・壁面看板 =================
SIGN_COLS = [(1.0, 1.0, 0.95), (1.0, 0.85, 0.1), (0.95, 0.12, 0.08), (0.1, 0.35, 0.95),
             (0.1, 0.75, 0.3), (1.0, 0.45, 0.05), (0.9, 0.2, 0.6)]
M_SIGN = []
for i, c in enumerate(SIGN_COLS):
    m, n, l = new_mat(f"Sign{i}")
    b = n["Principled BSDF"]
    # 文字っぽい模様: 横縞ノイズで明暗をつける
    tex = n.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 6
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1, 1, 6)
    l.new(tc.outputs["Object"], mp.inputs[0])
    l.new(mp.outputs[0], tex.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[0].color = (*c, 1)
    ramp.color_ramp.elements[1].position = 0.55
    ramp.color_ramp.elements[1].color = (0.03, 0.03, 0.03, 1) if i == 0 else (1, 1, 1, 1)
    l.new(tex.outputs["Fac"], ramp.inputs[0])
    l.new(ramp.outputs[0], b.inputs["Base Color"])
    l.new(ramp.outputs[0], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 1.5
    M_SIGN.append(m)

nsign = 0
for ob in list(coll.objects):
    me = ob.data
    h = max(v.co.z for v in me.vertices)
    vs = [v.co for v in me.vertices if v.co.z < 0.01]
    if h < 8 or len(vs) < 3:
        continue
    cen = sum(vs, Vector()) / len(vs)
    if (cen.xy - C.xy).length > 95:
        continue
    k = len(vs)
    # 交差点や道路に向いた壁 (中心から外向き & 交差点側) に看板
    for j in range(k):
        p0, p1 = vs[j].xy, vs[(j + 1) % k].xy
        L = (p1 - p0).length
        if L < 5:
            continue
        d = (p1 - p0).normalized()
        nrm = Vector((d.y, -d.x))
        mid = (p0 + p1) / 2
        if (mid - cen.xy).dot(nrm) < 0:
            nrm = -nrm
        if nrm.dot((C.xy - mid).normalized()) < 0.2:
            continue
        top = min(h - 1, 30)
        # 縦の袖看板 (壁から突き出す)
        for _ in range(random.randint(0, 2)):
            t = random.uniform(0.1, 0.9)
            sh = random.uniform(4, min(12, top - 4)) if top > 9 else 0
            if sh <= 0:
                break
            z0 = random.uniform(4.5, top - sh)
            pos = p0 + d * (L * t) + nrm * 0.6
            bpy.ops.mesh.primitive_cube_add(size=1, location=(pos.x, pos.y, z0 + sh / 2))
            sg = bpy.context.object
            sg.scale = (1.0, 0.25, sh)
            sg.rotation_euler = (0, 0, math.atan2(nrm.y, nrm.x))
            sg.data.materials.append(random.choice(M_SIGN))
            nsign += 1
        # 2階あたりの横長看板
        if random.random() < 0.7:
            pos = mid + nrm * 0.15
            bw = L * random.uniform(0.5, 0.9)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(pos.x, pos.y, random.uniform(4.6, 6.0)))
            sg = bpy.context.object
            sg.scale = (bw, 0.2, random.uniform(0.9, 1.6))
            sg.rotation_euler = (0, 0, math.atan2(d.y, d.x))
            sg.data.materials.append(random.choice(M_SIGN))
            nsign += 1
print("signs", nsign)

# ================= 木 (ハチ公前広場など) =================
M_LEAF = simple("Leaf", (0.10, 0.20, 0.07), 0.8)
M_TRUNK = simple("Trunk", (0.18, 0.12, 0.08), 0.9)
TREES = [(-34, -16), (-30, -24), (-36, -31), (-28, -38), (-33, -45), (-25, -30), (24, -17), (-24, -44)]
for tx, ty in TREES:
    hgt = random.uniform(6, 9)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.18, depth=hgt * 0.5, location=(tx, ty, hgt * 0.25))
    bpy.context.object.data.materials.append(M_TRUNK)
    for _ in range(4):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=random.uniform(1.5, 2.4),
            location=(tx + random.uniform(-1, 1), ty + random.uniform(-1, 1), hgt * random.uniform(0.6, 0.85)))
        o = bpy.context.object
        o.data.materials.append(M_LEAF)
        bpy.ops.object.shade_smooth()

# ================= 歩行者 =================
CLOTH = [(0.03, 0.03, 0.035), (0.05, 0.06, 0.10), (0.25, 0.25, 0.26), (0.55, 0.47, 0.36),
         (0.85, 0.84, 0.80), (0.45, 0.08, 0.06), (0.10, 0.22, 0.35), (0.40, 0.38, 0.30)]
M_CLOTH = [simple(f"Cloth{i}", c, 0.8) for i, c in enumerate(CLOTH)]
M_SKIN = simple("Skin", (0.62, 0.45, 0.35), 0.6)
M_HAIR = simple("Hair", (0.02, 0.015, 0.012), 0.5)
M_PANTS = simple("Pants", (0.04, 0.04, 0.05), 0.8)


def make_person_mesh(idx):
    """簡易な人型 (胴体・脚・頭) を1つのメッシュにまとめる"""
    parts = []
    hscale = random.uniform(0.92, 1.08)
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.19, depth=0.62, location=(0, 0, 1.17))
    parts.append((bpy.context.object, idx % len(M_CLOTH)))
    for sx in (-0.09, 0.09):
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.075, depth=0.86, location=(sx, 0, 0.43))
        parts.append((bpy.context.object, -1))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=0.11, location=(0, 0, 1.6))
    parts.append((bpy.context.object, -2))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=0.115, location=(0, -0.015, 1.63))
    parts.append((bpy.context.object, -3))
    mats = []
    for o, mi in parts:
        mat = M_PANTS if mi == -1 else M_SKIN if mi == -2 else M_HAIR if mi == -3 else M_CLOTH[mi]
        o.data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    for o, _ in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0][0]
    bpy.ops.object.join()
    p = bpy.context.object
    p.scale = (1, 1, hscale)
    bpy.ops.object.transform_apply(scale=True)
    me = p.data
    bpy.data.objects.remove(p)
    return me


PERSON_MESHES = [make_person_mesh(i) for i in range(16)]
pcoll = bpy.data.collections.new("People")
scene.collection.children.link(pcoll)

# 交差点の四隅 (航空写真から読み取った概略位置)
CORNERS = {"NW": Vector((-27, 21)), "NE": Vector((17, 25)), "SE": Vector((19, -18)), "SW": Vector((-23, -19))}
ROUTES = [("NW", "NE"), ("NE", "SE"), ("SE", "SW"), ("SW", "NW"), ("NW", "SE"), ("NE", "SW")]


def add_person(loc0, loc1):
    me = random.choice(PERSON_MESHES)
    ob = bpy.data.objects.new("Person", me)
    pcoll.objects.link(ob)
    d = (loc1 - loc0)
    ob.rotation_euler = (0, 0, math.atan2(d.y, d.x) - math.pi / 2)
    ob.location = (loc0.x, loc0.y, 0)
    ob.keyframe_insert("location", frame=1)
    ob.location = (loc1.x, loc1.y, 0)
    ob.keyframe_insert("location", frame=NFRAMES)
    for fc in ob.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    return ob


T = NFRAMES / FPS
# 横断中の人 (動画の間ずっと歩いている)
for _ in range(900):
    a, b_ = random.choice(ROUTES)
    if random.random() < 0.5:
        a, b_ = b_, a
    A, B = CORNERS[a], CORNERS[b_]
    dirv = (B - A).normalized()
    side = Vector((-dirv.y, dirv.x))
    width = random.gauss(0, 2.2)
    speed = random.uniform(1.1, 1.6)
    total = (B - A).length
    s0 = random.uniform(-3, total - speed * T + 3)
    p0 = A + dirv * s0 + side * width
    p1 = p0 + dirv * speed * T + side * random.uniform(-0.5, 0.5)
    add_person(p0, p1)
# 歩道で待っている/歩いている人
for name, cpt in CORNERS.items():
    out_dir = (cpt - C.xy).normalized()
    for _ in range(70):
        p = cpt + out_dir * random.uniform(1.5, 9) + Vector((random.uniform(-5, 5), random.uniform(-5, 5)))
        if random.random() < 0.6:
            add_person(p, p + Vector((random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3))))
        else:
            v = Vector((random.uniform(-1, 1), random.uniform(-1, 1))).normalized() * random.uniform(4, 10)
            add_person(p, p + v)

# ================= 車 (信号待ちで停車中) =================
CAR_COLS = [(0.02, 0.02, 0.02), (0.85, 0.85, 0.85), (0.3, 0.3, 0.32), (0.05, 0.07, 0.12),
            (0.6, 0.6, 0.62), (0.5, 0.05, 0.04)]
M_CAR = [simple(f"Car{i}", c, 0.25, 0.5) for i, c in enumerate(CAR_COLS)]
M_TAXI = simple("Taxi", (0.04, 0.05, 0.09), 0.25, 0.5)
M_GLASS = simple("CarGlass", (0.02, 0.025, 0.03), 0.05, 0.8)
M_TIRE = simple("Tire", (0.02, 0.02, 0.02), 0.9)
M_BUS = simple("Bus", (0.85, 0.85, 0.82), 0.4, 0.3)


def add_vehicle(x, y, yaw, bus=False):
    L, W, H = (11, 2.5, 3.0) if bus else (4.6, 1.75, 1.45)
    mat = M_BUS if bus else (M_TAXI if random.random() < 0.3 else random.choice(M_CAR))
    objs = []
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.35 + (H * 0.45 if not bus else H / 2) / 2))
    o = bpy.context.object
    o.scale = (L, W, H * 0.45 if not bus else H - 0.35)
    o.data.materials.append(mat)
    objs.append(o)
    if not bus:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.2, 0, 0.35 + H * 0.45 + H * 0.2))
        o = bpy.context.object
        o.scale = (L * 0.55, W * 0.92, H * 0.4)
        o.data.materials.append(M_GLASS)
        objs.append(o)
    else:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1.9))
        o = bpy.context.object
        o.scale = (L * 0.96, W + 0.02, 1.0)
        o.data.materials.append(M_GLASS)
        objs.append(o)
    for wx in (-L * 0.32, L * 0.32):
        for wy in (-W / 2, W / 2):
            bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.33 if not bus else 0.5, depth=0.25,
                location=(wx, wy, 0.33 if not bus else 0.5), rotation=(math.pi / 2, 0, 0))
            bpy.context.object.data.materials.append(M_TIRE)
            objs.append(bpy.context.object)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    car = bpy.context.object
    car.location = (x, y, 0)
    car.rotation_euler = (0, 0, yaw)
    return car


# 各方向の停止線手前に車列 (位置は航空写真の道路から)
LANES = [
    # (先頭x, 先頭y, 進行方向の角度(rad), 台数)
    (17, 33, -math.pi / 2, 5), (21, 33, -math.pi / 2, 4),      # 北から来る車 (南向き)
    (26, 34, math.pi / 2, 0),
    (-36, -2, 0.08, 5), (-36, 2.5, 0.08, 4),                  # 西(道玄坂方面)から
    (-12, -30, math.pi / 2, 4), (-16, -30, math.pi / 2, 3),    # 南から
    (34, 4, math.pi, 3),                                       # 東(駅前)から
]
for x, y, yaw, cnt in LANES:
    back = Vector((-math.cos(yaw), -math.sin(yaw)))
    for j in range(cnt):
        bus = (j == 2 and random.random() < 0.5)
        off = j * 6.2 + (3 if bus else 0)
        add_vehicle(x + back.x * off, y + back.y * off, yaw, bus)

# ================= 空と太陽 =================
world = bpy.data.worlds.new("Sky")
scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
sky = wn.new("ShaderNodeTexSky")
sky.sky_type = "NISHITA"
sky.sun_elevation = math.radians(38)
sky.sun_rotation = math.radians(150)   # 航空写真の影の向きに合わせて南南東から
sky.altitude = 40
sky.air_density = 1.2
sky.dust_density = 2.0
world.node_tree.links.new(sky.outputs[0], wn["Background"].inputs[0])
wn["Background"].inputs["Strength"].default_value = 0.25

bpy.ops.object.light_add(type="SUN")
sun = bpy.context.object
sun.data.energy = 4.0
sun.data.angle = math.radians(0.6)
sun.data.color = (1.0, 0.96, 0.9)
# 南南東からの日差し (影が北北西に伸びる。航空写真の影と同じ向き)
sky.sun_disc = False
sun.rotation_euler = (math.pi / 2 - sky.sun_elevation, 0, math.radians(30))

# ================= カメラ (ドローン風にゆっくり旋回・下降) =================
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 20
cam_data.clip_end = 3000
cam = bpy.data.objects.new("Cam_Drone", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
target = bpy.data.objects.new("CamTarget", None)
scene.collection.objects.link(target)
tc_ = cam.constraints.new("TRACK_TO")
tc_.target = target
tc_.track_axis = "TRACK_NEGATIVE_Z"
tc_.up_axis = "UP_Y"

for f in range(1, NFRAMES + 1, 4):
    t = (f - 1) / (NFRAMES - 1)
    e = t * t * (3 - 2 * t)
    # 交差点の周りを半径35mで旋回。高さ58m→50m (半径60m以内のビルは最大45m)
    pa = math.radians(-60 - 100 * e)          # 南東 → 南 → 南西
    cam.location = (C.x + 35 * math.cos(pa), C.y + 35 * math.sin(pa), 58 - 8 * e)
    look = Vector((-math.cos(pa), -math.sin(pa), 0))
    target.location = C + look * 45 + Vector((0, 0, 0))
    cam.keyframe_insert("location", frame=f)
    target.keyframe_insert("location", frame=f)

# ================= レンダ設定 =================
r = scene.render
r.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 24
scene.cycles.use_denoising = False
scene.cycles.max_bounces = 4
scene.cycles.diffuse_bounces = 2
scene.cycles.glossy_bounces = 2
scene.cycles.transmission_bounces = 2
scene.cycles.use_animated_seed = False
r.resolution_x, r.resolution_y = 960, 540
scene.view_settings.view_transform = "AgX" if "AgX" in [
    i.identifier for i in scene.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
scene.view_settings.look = "AgX - Medium High Contrast" if scene.view_settings.view_transform == "AgX" else "Medium High Contrast"
scene.view_settings.exposure = -0.2
r.use_motion_blur = False
r.motion_blur_shutter = 0.5

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "shibuya.blend"))
print("BUILT", len(blds), "buildings,", len(screens), "screens,", len(pcoll.objects), "people")
