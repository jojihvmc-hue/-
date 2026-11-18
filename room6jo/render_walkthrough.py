# 入口から部屋に入り、中央でぐるっと見回すウォークスルー動画のフレームを書き出す
# 実行: blender -b room6jo.blend -P render_walkthrough.py  （環境変数 FRAMES=開始-終了 で範囲指定可）
import bpy, math, os

OUT = os.path.dirname(os.path.abspath(bpy.data.filepath))
scene = bpy.context.scene
for o in bpy.data.objects:          # 寸法ラベル・天井の表示状態を通常に戻す
    if o.type == "FONT" or o.name.startswith("DimLine"):
        o.hide_render = True
    if o.name == "Ceiling":
        o.hide_render = False
for o in bpy.data.objects:
    if o.type == "LIGHT":
        o.hide_render = False
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6

bpy.ops.object.camera_add()
cam = bpy.context.object
cam.name = "Cam_Walk"
cam.data.lens = 14
scene.camera = cam

FPS, WALK, TURN = 24, 72, 120      # 歩く3秒 + 見回す5秒
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 1, WALK + TURN

EYE = 1.55
P0, P1 = (0.55, 3.40), (1.20, 1.90)  # ドア付近 → 部屋中央寄り


def ease(t):
    return t * t * (3 - 2 * t)


def yaw_to(px, py, tx, ty):
    return math.atan2(ty - py, tx - px) - math.pi / 2


yaw_walk = yaw_to(*P0, 1.4, 0.0)      # 窓のほうを向いて歩く
for f in range(scene.frame_start, scene.frame_end + 1):
    if f <= WALK:
        t = ease((f - 1) / (WALK - 1))
        x, y = P0[0] + (P1[0] - P0[0]) * t, P0[1] + (P1[1] - P0[1]) * t
        yaw, pitch = yaw_walk, math.radians(78)
    else:
        t = ease((f - WALK) / TURN)
        x, y = P1
        yaw, pitch = yaw_walk + 2 * math.pi * t, math.radians(80)
    cam.location = (x, y, EYE)
    cam.rotation_euler = (pitch, 0, yaw)
    cam.keyframe_insert("location", frame=f)
    cam.keyframe_insert("rotation_euler", frame=f)

r = scene.render
r.resolution_x, r.resolution_y = 854, 480
scene.cycles.samples = int(os.environ.get("SAMPLES", 20))
scene.cycles.max_bounces = 4
scene.cycles.seed = 0
scene.cycles.use_animated_seed = False   # ノイズ模様を固定してちらつきを抑える
r.image_settings.file_format = "PNG"
r.filepath = os.path.join(OUT, "frames", "f_")

rng = os.environ.get("FRAMES")
if rng:
    a, b = map(int, rng.split("-"))
    scene.frame_start, scene.frame_end = a, b
bpy.ops.render.render(animation=True)
print("DONE")
