import bpy
import bmesh
import math
from mathutils import Vector

NUM_BONES = 25
EPS = 1e-3
MESH_Y_MIN = -25.0
MESH_Y_MAX = 0.0
NEG_X_WEIGHTS = (0.067233, 0.851498, 0.067233)
POS_X_WEIGHTS = (0.128648, 0.686939, 0.128648)
TOTAL_LEN     = MESH_Y_MAX - MESH_Y_MIN

bpy.ops.object.select_all(action='DESELECT')

mesh_obj = bpy.data.objects.get("Cube.002")
bpy.context.view_layer.objects.active = mesh_obj
mesh_obj.select_set(True)
arm_obj = bpy.data.objects.get("petite_chenille.007")
mesh_obj.vertex_groups.clear()

vgroups = []
for i in range(NUM_BONES):
    vg = mesh_obj.vertex_groups.new(name=f"Bone_{i:03d}")
    vgroups.append(vg)

mesh_data = mesh_obj.data
bpy.ops.object.mode_set(mode='OBJECT')

for v in mesh_data.vertices:
    y = v.co.y
    x = v.co.x
    z = v.co.z
    if y <= MESH_Y_MIN + EPS:
        #vgroups[0].add([v.index], 1.0, 'REPLACE')
        continue
    if y >= MESH_Y_MAX - EPS:
        vgroups[0].add([v.index], w0, 'REPLACE')
        vgroups[1].add([v.index], w1, 'REPLACE')
        vgroups[2].add([v.index], w2, 'REPLACE')
        continue

    t        = (y - MESH_Y_MIN) / TOTAL_LEN * NUM_BONES  # 0.0 … 25.0
    main_idx = int(math.floor(t))
    main_idx = max(0, min(NUM_BONES - 1, main_idx))

    i_prev = max(0,           main_idx - 1)
    i_curr = main_idx
    i_next = min(NUM_BONES - 1, main_idx + 1)
    
    i0 = main_idx % NUM_BONES
    i1 = (main_idx + 1) % NUM_BONES
    i2 = (main_idx + 2) % NUM_BONES

    if z < 0:
        w0, w1, w2 = NEG_X_WEIGHTS
    else:
        w0, w1, w2 = POS_X_WEIGHTS

    vgroups[i0].add([v.index], w0, 'REPLACE')
    vgroups[i1].add([v.index], w1, 'REPLACE')
    vgroups[i2].add([v.index], w2, 'REPLACE')

#bpy.ops.outliner.orphans_purge(do_recursive=True)
'''
bpy.ops.object.select_all(action='DESELECT')
obj = bpy.data.objects.get("Cube.002")
bpy.context.view_layer.objects.active = obj
obj.vertex_groups.clear()
bpy.ops.object.select_all(action='DESELECT')
bones = bpy.data.objects.get("petite_chenille.007")
bpy.context.view_layer.objects.active = bones
bpy.ops.object.mode_set(mode='EDIT')
edit_bones = bones.data.edit_bones
bpy.ops.bones.select_all(action='DESELECT')
edit_bones[0].select = True
edit_bones[0].select_head = True
edit_bones[0].select_tail = True
vg = [
    obj.vertex_groups.new(name=f"Bone.{i + 1:03d}")
    for i in range(NUM_BONES)
]
for v in obj.data.vertices:
    vy = v.co.y   # Y local du cube (= Y world ici, rotation Y conserve l'axe Y)

    if vy < -1.0 + EPS:
        # Fond du cube
        vg[0].add([v.index], 1.0, 'REPLACE')

    elif abs(vy - (-1.0)) < EPS:
        # Boucle inférieure du cube → bone 0 à 100 %
        vg[0].add([v.index], 1.0, 'REPLACE')

    elif abs(vy - 1.0) < EPS:
        # Jonction cube / extrude 1 → 50/50 bone 0 & bone 1
        vg[0].add([v.index], 0.5, 'REPLACE')
        vg[1].add([v.index], 0.5, 'REPLACE')

    elif 1.0 + EPS < vy < 25.0 - EPS:
        # Boucles intermédiaires (Y = 2, 3, …, 24)
        # Y=k  →  bone (k-1) et bone (k)  à 50/50
        k  = int(round(vy))          # position entière de la boucle
        bi = k - 1                   # index du bone "inférieur"
        bi = max(0, min(NUM_BONES - 2, bi))
        vg[bi    ].add([v.index], 0.128648, 'REPLACE')
        vg[bi + 1].add([v.index], 0.686939, 'REPLACE')
        vg[bi + 2].add([v.index], 0.128648, 'REPLACE')

    else:
        # Sommet de la chaîne (Y ≈ 25) → bone 24 à 100 %
        vg[NUM_BONES - 1].add([v.index], 1.0, 'REPLACE')
'''
