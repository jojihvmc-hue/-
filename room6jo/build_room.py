# 6畳洋室の3Dモデルを作り、2枚レンダリングする Blender スクリプト
# 実行: blender -b -P build_room.py
# 座標: X=東, Y=北, Z=上 (単位 m)。室内寸法 2.7m(東西) x 3.6m(南北)
import bpy, math, os

OUT = os.path.dirname(os.path.abspath(__file__))

# ---- 寸法定義 (m) ----
W, D, H = 2.70, 3.60, 2.40          # 室内 幅(東西)・奥行(南北)・天井高
T = 0.12                            # 壁厚
WIN_X0, WIN_X1 = 0.55, 2.15         # 南窓 (幅1.60)
WIN_Z0, WIN_Z1 = 0.90, 2.00         # 窓 腰高0.90・高さ1.10
DOOR_X0, DOOR_X1 = 0.15, 0.93       # 北ドア (幅0.78)
DOOR_H = 2.00

BED = dict(w=0.97, l=1.95, h=0.45)  # シングルベッド
DESK = dict(w=1.00, d=0.60, h=0.72)
SHELF = dict(w=0.80, d=0.30, h=1.80)
CHAIR = dict(w=0.45, d=0.50, seat=0.45, back=0.85)

# ---- 初期化 ----
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def mat(name, rgb, rough=0.6, emit=None, alpha=1.0, transmission=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    if transmission:
        b.inputs["Transmission Weight"].default_value = transmission
        b.inputs["IOR"].default_value = 1.0
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = 1.0
    return m


M = {
    "wall": mat("Wall", (0.85, 0.84, 0.80), 0.9),
    "floor": mat("Floor", (0.45, 0.30, 0.18), 0.4),
    "ceil": mat("Ceiling", (0.92, 0.92, 0.92), 0.9),
    "wood": mat("Wood", (0.60, 0.43, 0.27), 0.5),
    "white": mat("White", (0.90, 0.90, 0.88), 0.5),
    "dark": mat("Dark", (0.12, 0.12, 0.13), 0.5),
    "mattress": mat("Mattress", (0.88, 0.88, 0.92), 0.8),
    "duvet": mat("Duvet", (0.35, 0.50, 0.68), 0.9),
    "door": mat("Door", (0.72, 0.60, 0.46), 0.5),
    "glass": mat("Glass", (0.85, 0.92, 1.0), 0.0, transmission=1.0),
    "frame": mat("Frame", (0.75, 0.75, 0.76), 0.4),
    "book": [mat(f"Book{i}", c, 0.7) for i, c in enumerate(
        [(0.6, 0.15, 0.12), (0.15, 0.3, 0.55), (0.2, 0.45, 0.25),
         (0.8, 0.65, 0.2), (0.3, 0.3, 0.32)])],
    "label": mat("Label", (0, 0, 0), emit=(0.85, 0.05, 0.05)),
}


def box(name, x0, x1, y0, y1, z0, z1, m, coll=None):
    bpy.ops.mesh.primitive_cube_add(size=1,
        location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    o = bpy.context.object
    o.name = name
    o.scale = (x1 - x0, y1 - y0, z1 - z0)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(m)
    return o


# ---- 床・天井 ----
box("Floor", -T, W + T, -T, D + T, -0.05, 0, M["floor"])
ceiling = box("Ceiling", -T, W + T, -T, D + T, H, H + 0.05, M["ceil"])

# ---- 壁 ----
# 西・東
box("Wall_W", -T, 0, -T, D + T, 0, H, M["wall"])
box("Wall_E", W, W + T, -T, D + T, 0, H, M["wall"])
# 南 (窓の開口を残して4分割)
box("Wall_S_L", 0, WIN_X0, -T, 0, 0, H, M["wall"])
box("Wall_S_R", WIN_X1, W, -T, 0, 0, H, M["wall"])
box("Wall_S_Bot", WIN_X0, WIN_X1, -T, 0, 0, WIN_Z0, M["wall"])
box("Wall_S_Top", WIN_X0, WIN_X1, -T, 0, WIN_Z1, H, M["wall"])
# 北 (ドアの開口)
box("Wall_N_L", 0, DOOR_X0, D, D + T, 0, H, M["wall"])
box("Wall_N_R", DOOR_X1, W, D, D + T, 0, H, M["wall"])
box("Wall_N_Top", DOOR_X0, DOOR_X1, D, D + T, DOOR_H, H, M["wall"])

# 巾木
for n, a in [("W", (0, 0.01, 0, D)), ("E", (W - 0.01, W, 0, D)),
             ("S", (0, W, 0, 0.01)), ("N", (0, W, D - 0.01, D))]:
    box("Baseboard_" + n, *a, 0, 0.06, M["white"])

# ---- 窓 (枠 + ガラス) ----
f = 0.04
box("Win_Frame_B", WIN_X0, WIN_X1, -0.08, -0.02, WIN_Z0, WIN_Z0 + f, M["frame"])
box("Win_Frame_T", WIN_X0, WIN_X1, -0.08, -0.02, WIN_Z1 - f, WIN_Z1, M["frame"])
box("Win_Frame_L", WIN_X0, WIN_X0 + f, -0.08, -0.02, WIN_Z0, WIN_Z1, M["frame"])
box("Win_Frame_R", WIN_X1 - f, WIN_X1, -0.08, -0.02, WIN_Z0, WIN_Z1, M["frame"])
mid = (WIN_X0 + WIN_X1) / 2
box("Win_Frame_M", mid - f / 2, mid + f / 2, -0.08, -0.02, WIN_Z0, WIN_Z1, M["frame"])
box("Win_Glass", WIN_X0, WIN_X1, -0.055, -0.045, WIN_Z0, WIN_Z1, M["glass"])
box("Win_Sill", WIN_X0 - 0.03, WIN_X1 + 0.03, -0.02, 0.03, WIN_Z0 - 0.02, WIN_Z0, M["white"])

# ---- ドア (90°開いた状態: 西側に吊元、室内側へ開く) ----
box("Door_Leaf", DOOR_X0, DOOR_X0 + 0.035, D - (DOOR_X1 - DOOR_X0), D,
    0, DOOR_H - 0.01, M["door"])
box("Door_Handle", DOOR_X0 + 0.035, DOOR_X0 + 0.07, D - 0.70, D - 0.62, 0.95, 0.98, M["frame"])

# ---- ベッド (東壁沿い、頭は北) ----
bx0, bx1 = W - BED["w"], W
by0, by1 = D - BED["l"], D
box("Bed_Frame", bx0, bx1, by0, by1, 0.05, 0.25, M["wood"])
for i, (lx, ly) in enumerate([(bx0, by0), (bx1 - 0.06, by0), (bx0, by1 - 0.06), (bx1 - 0.06, by1 - 0.06)]):
    box(f"Bed_Leg{i}", lx, lx + 0.06, ly, ly + 0.06, 0, 0.05, M["wood"])
box("Bed_Mattress", bx0 + 0.01, bx1 - 0.01, by0 + 0.01, by1 - 0.04, 0.25, BED["h"], M["mattress"])
box("Bed_Duvet", bx0, bx1, by0, by1 - 0.55, BED["h"], BED["h"] + 0.06, M["duvet"])
box("Bed_Pillow", bx0 + 0.15, bx1 - 0.15, by1 - 0.45, by1 - 0.12, BED["h"], BED["h"] + 0.10, M["white"])
box("Bed_Headboard", bx0, bx1, by1 - 0.04, by1, 0, 0.80, M["wood"])

# ---- 机 (西壁沿い、窓側) ----
dx0, dx1 = 0, DESK["d"]
dy0, dy1 = 0.25, 0.25 + DESK["w"]
box("Desk_Top", dx0, dx1, dy0, dy1, DESK["h"] - 0.03, DESK["h"], M["wood"])
for i, (lx, ly) in enumerate([(dx0 + 0.02, dy0 + 0.02), (dx1 - 0.06, dy0 + 0.02),
                              (dx0 + 0.02, dy1 - 0.06), (dx1 - 0.06, dy1 - 0.06)]):
    box(f"Desk_Leg{i}", lx, lx + 0.04, ly, ly + 0.04, 0, DESK["h"] - 0.03, M["dark"])
box("Desk_Monitor", 0.08, 0.10, dy0 + 0.25, dy0 + 0.80, DESK["h"] + 0.10, DESK["h"] + 0.42, M["dark"])
box("Desk_MonitorStand", 0.06, 0.18, dy0 + 0.48, dy0 + 0.57, DESK["h"], DESK["h"] + 0.10, M["dark"])

# 椅子
cx0, cy0 = DESK["d"] + 0.05, dy0 + 0.27
cx1, cy1 = cx0 + CHAIR["d"], cy0 + CHAIR["w"]
box("Chair_Seat", cx0, cx1, cy0, cy1, CHAIR["seat"] - 0.05, CHAIR["seat"], M["dark"])
box("Chair_Back", cx1 - 0.05, cx1, cy0, cy1, CHAIR["seat"], CHAIR["back"], M["dark"])
box("Chair_Post", (cx0 + cx1) / 2 - 0.025, (cx0 + cx1) / 2 + 0.025,
    (cy0 + cy1) / 2 - 0.025, (cy0 + cy1) / 2 + 0.025, 0.05, CHAIR["seat"] - 0.05, M["frame"])
box("Chair_Base", cx0 + 0.05, cx1 - 0.05, cy0 + 0.05, cy1 - 0.05, 0, 0.05, M["frame"])

# ---- 本棚 (西壁沿い、机の北側) ----
sx0, sx1 = 0, SHELF["d"]
sy0, sy1 = 1.55, 1.55 + SHELF["w"]
t = 0.02
box("Shelf_SideS", sx0, sx1, sy0, sy0 + t, 0, SHELF["h"], M["white"])
box("Shelf_SideN", sx0, sx1, sy1 - t, sy1, 0, SHELF["h"], M["white"])
box("Shelf_Back", sx0, sx0 + 0.01, sy0, sy1, 0, SHELF["h"], M["white"])
levels = [0.0, 0.05, 0.40, 0.75, 1.10, 1.45, SHELF["h"] - t]
for i, z in enumerate(levels):
    box(f"Shelf_Board{i}", sx0, sx1, sy0 + t, sy1 - t, z, z + t, M["white"])
import random
random.seed(3)
for i in range(1, len(levels) - 1):
    z0 = levels[i] + t
    y = sy0 + t + 0.01
    while y < sy1 - t - 0.05:
        bw = random.uniform(0.02, 0.05)
        bh = min(random.uniform(0.18, 0.30), levels[i + 1] - z0 - 0.02)
        box("Book", sx0 + 0.04, sx0 + random.uniform(0.18, 0.24), y, y + bw,
            z0, z0 + bh, random.choice(M["book"]))
        y += bw + 0.003

# ---- 照明 ----
bpy.ops.object.light_add(type="AREA", location=(W / 2, D / 2, H - 0.02))
ceil_light = bpy.context.object
ceil_light.data.size = 0.5
ceil_light.data.energy = 120
ceil_light.data.color = (1.0, 0.95, 0.88)

bpy.ops.object.light_add(type="SUN", location=(W / 2, -3, 4))
sun = bpy.context.object
sun.data.energy = 3.5
sun.rotation_euler = (math.radians(55), 0, math.radians(180))  # 南から差し込む

# 窓から入る天空光
bpy.ops.object.light_add(type="AREA", location=(mid, -0.15, (WIN_Z0 + WIN_Z1) / 2))
sky = bpy.context.object
sky.data.shape = "RECTANGLE"
sky.data.size, sky.data.size_y = WIN_X1 - WIN_X0, WIN_Z1 - WIN_Z0
sky.data.energy = 150
sky.data.color = (0.85, 0.92, 1.0)
sky.rotation_euler = (math.radians(-90), 0, 0)  # 北(室内)向き

world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.6, 0.75, 0.95, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6

# ---- 真上ビュー用の寸法ラベル ----
labels = []


def label(text, x, y, size=0.16, rot=0):
    bpy.ops.object.text_add(location=(x, y, H + 0.3))
    o = bpy.context.object
    o.data.body = text
    o.data.size = size
    o.data.align_x = "CENTER"
    o.data.align_y = "CENTER"
    o.rotation_euler = (0, 0, math.radians(rot))
    o.data.materials.append(M["label"])
    labels.append(o)


label("2700", W / 2, -0.38)
label("3600", -0.40, D / 2, rot=90)
label("N  (Door 780)", (DOOR_X0 + DOOR_X1) / 2 + 0.35, D + 0.30, 0.12)
label("S  (Window 1600)", mid, -0.70, 0.12)
label("Bed 970x1950", (bx0 + bx1) / 2, (by0 + by1) / 2 - 0.3, 0.11, 90)
label("Desk 1000x600", (dx0 + dx1) / 2, (dy0 + dy1) / 2, 0.10, 90)
label("Shelf 800x300", (sx0 + sx1) / 2, (sy0 + sy1) / 2, 0.08, 90)
# 寸法線
box("DimLine_W", 0, W, -0.24, -0.23, H + 0.3, H + 0.31, M["label"])
box("DimLine_D", -0.24, -0.23, 0, D, H + 0.3, H + 0.31, M["label"])
for o in bpy.data.objects:
    if o.name.startswith("DimLine"):
        labels.append(o)

# ---- カメラ ----
# 1) 入口から見渡す (ドア付近、目線高さ 1.55m)
bpy.ops.object.camera_add(location=(0.55, D - 0.15, 1.55))
cam_door = bpy.context.object
cam_door.name = "Cam_Entrance"
cam_door.data.lens = 16
cam_door.data.sensor_width = 36
dx, dy, dz = 1.55 - 0.55, 0.3 - (D - 0.15), 0.9 - 1.55
cam_door.rotation_euler = (
    math.atan2(math.hypot(dx, dy), -dz), 0, math.atan2(dy, dx) - math.pi / 2)

# 2) 真上から (平行投影)
bpy.ops.object.camera_add(location=(W / 2 - 0.15, D / 2 - 0.1, 8))
cam_top = bpy.context.object
cam_top.name = "Cam_Top"
cam_top.data.type = "ORTHO"
cam_top.data.ortho_scale = 4.9
cam_top.data.clip_end = 20

# ---- レンダ設定 ----
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = int(os.environ.get("SAMPLES", 256))
scene.cycles.use_denoising = False
scene.cycles.max_bounces = 6
scene.render.film_transparent = False
scene.view_settings.view_transform = "Filmic" if "Filmic" in [
    i.identifier for i in scene.view_settings.bl_rna.properties["view_transform"].enum_items] else "AgX"
scene.view_settings.exposure = -0.6


def render(cam, path, res, show_ceiling, show_labels):
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = res
    ceiling.hide_render = not show_ceiling
    ceil_light.hide_render = not show_ceiling
    sun.hide_render = sky.hide_render = not show_ceiling
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6 if show_ceiling else 2.5
    for o in labels:
        o.hide_render = not show_labels
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "room6jo.blend"))
render(cam_door, os.path.join(OUT, "render_entrance.png"), (1280, 960), True, False)
render(cam_top, os.path.join(OUT, "render_top.png"), (1000, 1100), False, True)
print("DONE")
