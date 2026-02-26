import bpy
import math
import sys
import os
import os.path
import bmesh
import datetime
from mathutils import Vector, Matrix
from random import random, seed, uniform, randint, randrange
from enum import IntEnum
from colorsys import hls_to_rgb
'''
ARMATURE_NAME = "V.006"
NUM_BONES     = 25
SCALE          = 8.743
R_LARGE  = 1.8
R_SMALL  = 1.2
CT = Vector((  0.0,   3.0, 0.0 ))
CB = Vector(( -3.0,   0.0, 0.0 ))
CF = Vector((  3.0,   0.0, 0.0 ))
FRAME_START  = 1
FRAME_END    = 360
FPS          = 60
DIRECTION    = -1
WHEEL_DEPTH      = 0.7
WHEEL_VERTS  = 6
WHEEL_VERTSBIG = 13
WHEEL_COLOR      = (0.20, 0.20, 0.20, 1.0)
magic_cubique_bezier = 0.5522847498
RADIUS         = 2
circumference  = 2 * math.pi * RADIUS
'''
ARMATURE_NAME  = "V.005" # 30 degrés big
NUM_BONES      = 25
SCALE          = 8.743
R_LARGE        = 0.1751 * SCALE
R_SMALL        = 0.1273 * SCALE
CT             = Vector(( 0.0,     2.6229, 0.0))
CB             = Vector((-2.6229,  0.0,    0.0))
CF             = Vector(( 5.2458,  0.0,    0.0))
FRAME_START    = 1
FRAME_END      = 450
FPS            = 120
DIRECTION      = -1
WHEEL_DEPTH    = 0.6
WHEEL_VERTS    = 6
WHEEL_VERTSBIG = 13
WHEEL_COLOR    = (0.12, 0.12, 0.12, 1.0)
magic_cubique_bezier = 0.5522847498
RADIUS         = 2
circumference  = 2 * math.pi * RADIUS

def radianPositif(centre, point):
    return math.atan2(point.y - centre.y, point.x - centre.x)
 
def pt_on_circle(c, radius, angle, z):
    return Vector((c.x + radius * math.cos(angle), c.y + radius * math.sin(angle), z))

def ccw(a0, a1):
    distance = (a1 - a0) % (2 * math.pi)
    return distance if distance > 1e-9 else 2 * math.pi

def seg_len(s):
    if s['type'] == 'L': return (s['p1'] - s['p0']).length
    return ccw(s['a0'], s['a1']) * s['r']

def pt_on_seg(s, t):
    if s['type'] == 'L': return s['p0'].lerp(s['p1'], t)
    return pt_on_circle(s['c'], s['r'], s['a0'] + t * ccw(s['a0'], s['a1']), 0)

def tang_on_seg(s, t):
    if s['type'] == 'L':
        return math.atan2(s['p1'].y - s['p0'].y, s['p1'].x - s['p0'].x)
    return s['a0'] + t * ccw(s['a0'], s['a1']) + math.pi / 2

def all_ext_tangents(c1, r1, c2, r2):
    dx, dy = c2.x - c1.x, c2.y - c1.y
    d      = math.hypot(dx, dy)
    theta  = math.atan2(dy, dx)
    alpha  = math.acos(max(-1.0, min(1.0, (r1 - r2) / d)))
    return [(theta + s * alpha,
             pt_on_circle(c1, r1, theta + s * alpha, 0),
             pt_on_circle(c2, r2, theta + s * alpha, 0)) for s in (+1, -1)]

# Droite du bas
tgts = all_ext_tangents(CB, R_SMALL, CF, R_SMALL)
tgts.sort(key=lambda x: x[1].y)
_, P_bot_B, P_bot_F = tgts[0]

# Diagonale CF → CT
a_CF_in = radianPositif(CF, P_bot_F)
_, P_F_out, P_CT_in = min(
    all_ext_tangents(CF, R_SMALL, CT, R_LARGE),
    key=lambda x: ccw(a_CF_in, radianPositif(CF, x[1]))
)

# Diagonale CT → CB
a_CT_in = radianPositif(CT, P_CT_in)
_, P_CT_out, P_CB_in = min(
    all_ext_tangents(CT, R_LARGE, CB, R_SMALL),
    key=lambda x: ccw(a_CT_in, radianPositif(CT, x[1]))
)

SEGS = [
    {'type': 'L', 'p0': P_bot_B,  'p1': P_bot_F},
    {'type': 'A', 'c': CF, 'r': R_SMALL, 'a0': radianPositif(CF, P_bot_F),  'a1': radianPositif(CF, P_F_out)},
    {'type': 'L', 'p0': P_F_out,  'p1': P_CT_in},
    {'type': 'A', 'c': CT, 'r': R_LARGE, 'a0': radianPositif(CT, P_CT_in),  'a1': radianPositif(CT, P_CT_out)},
    {'type': 'L', 'p0': P_CT_out, 'p1': P_CB_in},
    {'type': 'A', 'c': CB, 'r': R_SMALL, 'a0': radianPositif(CB, P_CB_in),  'a1': radianPositif(CB, P_bot_B)},
]

ok = True
for i in range(len(SEGS)):
    gap = (pt_on_seg(SEGS[i], 1.0) - pt_on_seg(SEGS[(i+1) % len(SEGS)], 0.0)).length
    ok  = ok and gap < 0.01

LENGTHS   = [seg_len(s) for s in SEGS]
TOTAL_LEN = sum(LENGTHS)

if not ok:
    raise RuntimeError("Chemin non fermé")

def eval_path(d):
    d = d % TOTAL_LEN
    walked = 0.0
    for s, l in zip(SEGS, LENGTHS):
        if walked + l >= d - 1e-9:
            t = max(0.0, min(1.0, (d - walked) / l))
            return pt_on_seg(s, t), tang_on_seg(s, t)
        walked += l
    return pt_on_seg(SEGS[0], 0.0), tang_on_seg(SEGS[0], 0.0)

if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

step_arc = TOTAL_LEN / NUM_BONES

def wheel_verts(radius):
    circumference = 2 * math.pi * radius
    n = round(circumference / step_arc)
    return max(n, WHEEL_VERTS)

VERTS_SMALL = wheel_verts(R_SMALL)
VERTS_LARGE = wheel_verts(R_LARGE)

ratio = R_LARGE / R_SMALL

arm = bpy.data.objects.get(ARMATURE_NAME)
if arm is None:
    raise RuntimeError(f"'{ARMATURE_NAME}' introuvable")

bpy.ops.object.select_all(action='DESELECT')
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='POSE')

pose_bones = arm.pose.bones
step_arc   = TOTAL_LEN / NUM_BONES

mat_inv = arm.matrix_world.inverted()

bpy.context.scene.frame_start     = FRAME_START
bpy.context.scene.frame_end       = FRAME_END
bpy.context.scene.render.fps      = FPS
bpy.context.scene.render.fps_base = 1.0

total_frames = FRAME_END - FRAME_START

for frame in range(FRAME_START, FRAME_END + 1):
    bpy.context.scene.frame_set(frame)
    phase = (frame - FRAME_START) / total_frames

    for i, pb in enumerate(pose_bones):
        pos_world, tang = eval_path((i * step_arc + phase * TOTAL_LEN) % TOTAL_LEN)

        pos_local  = mat_inv @ Vector((pos_world.x, pos_world.y, 0))
        rest_local = pb.bone.head_local
        pb.location = pos_local - rest_local

        pb.rotation_mode  = 'XYZ'
        pb.rotation_euler = (0, 0, tang - math.pi / 2)

        pb.keyframe_insert(data_path="location",       frame=frame)
        pb.keyframe_insert(data_path="rotation_euler", frame=frame)

bpy.ops.object.mode_set(mode='OBJECT')

action = arm.animation_data.action

def set_linear(fcurves):
    for fc in fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

if hasattr(action, 'layers') and len(action.layers) > 0:
    slot = arm.animation_data.action_slot
    for layer in action.layers:
        for strip in layer.strips:
            cb = strip.channelbag(slot)
            if cb:
                set_linear(cb.fcurves)
else:
    set_linear(action.fcurves)

linear_speed_per_frame = DIRECTION * TOTAL_LEN / total_frames

WHEEL_DEFS = [
    {"name": "Wheel_CB", "center": CB, "radius": R_SMALL, "verts": VERTS_SMALL},
    {"name": "Wheel_CF", "center": CF, "radius": R_SMALL, "verts": VERTS_SMALL},
    {"name": "Wheel_CT", "center": CT, "radius": R_LARGE, "verts": VERTS_LARGE},
]

def set_linear_action(action, anim_data):
    if not action or not anim_data:
        return
    slot = anim_data.action_slot
    for layer in action.layers:
        for strip in layer.strips:
            cb = strip.channelbag(slot)
            if cb:
                for fc in cb.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'

def remove_if_exists(name):
    obj = bpy.data.objects.get(name)
    if obj:
        bpy.data.objects.remove(obj, do_unlink=True)

if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

bpy.ops.object.select_all(action='DESELECT')

wheel_objects = []

for wd in WHEEL_DEFS:
    remove_if_exists(wd["name"])
    remove_if_exists(wd["name"] + "_marker")

    bpy.ops.mesh.primitive_cylinder_add(
        vertices = wd["verts"],
        radius   = wd["radius"],
        depth    = WHEEL_DEPTH,
        location = (wd["center"].x, wd["center"].y, 0.0),
        rotation = (math.pi / 2, 0.0, 0.0),
    )
    wheel = bpy.context.active_object
    wheel.name = wd["name"]

    mat = bpy.data.materials.new(wd["name"] + "_Mat")
    mat.diffuse_color = WHEEL_COLOR
    wheel.data.materials.append(mat)

    wheel_objects.append((wheel, wd["center"], wd["radius"]))

for wheel_obj, center, radius in wheel_objects:
    omega = linear_speed_per_frame / radius

    for frame in (FRAME_START, FRAME_END):
        elapsed = frame - FRAME_START
        angle   = omega * elapsed
        bpy.context.scene.frame_set(frame)
        wheel_obj.rotation_mode  = 'XYZ'
        wheel_obj.rotation_euler = (0.0, 0.0, angle)
        wheel_obj.keyframe_insert(data_path="rotation_euler", frame=frame)

    if wheel_obj.animation_data and wheel_obj.animation_data.action:
        set_linear_action(
            wheel_obj.animation_data.action,
            wheel_obj.animation_data )

if DIRECTION == -1:
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')

    for frame in range(FRAME_START, FRAME_END + 1):
        bpy.context.scene.frame_set(frame)
        phase = 1.0 - (frame - FRAME_START) / total_frames

        for i, pb in enumerate(arm.pose.bones):
            pos_world, tang = eval_path(
                (i * step_arc + phase * TOTAL_LEN) % TOTAL_LEN
            )
            pos_local  = mat_inv @ Vector((pos_world.x, pos_world.y, 0))
            rest_local = pb.bone.head_local
            pb.location       = pos_local - rest_local
            pb.rotation_mode  = 'XYZ'
            pb.rotation_euler = (0, 0, tang - math.pi / 2)

            pb.keyframe_insert(data_path="location",       frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

    bpy.ops.object.mode_set(mode='OBJECT')

    set_linear_action(arm.animation_data.action, arm.animation_data)

bpy.context.scene.frame_set(FRAME_START)

'''
    # Petit marqueur radial pour bien voir la rotation
    bpy.ops.mesh.primitive_cylinder_add(
        vertices = 8,
        radius   = wd["radius"] * 0.08,
        depth    = WHEEL_DEPTH * 1.05,
        location = (wd["center"].x + wd["radius"] * 0.75,
                    wd["center"].y,
                    0.0),
        rotation = (math.pi / 2, 0.0, 0.0),
    )
    marker = bpy.context.active_object
    marker.name = wd["name"] + "_marker"
    
    # Parent marker → wheel
    marker.parent = wheel
'''
