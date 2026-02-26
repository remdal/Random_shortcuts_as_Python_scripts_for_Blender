import bpy
from mathutils import Vector

NUM_BONES    = 25
MESH_Y_START = 0.0
MESH_Y_END   = 25.0

BONE_SPACING = (MESH_Y_END - MESH_Y_START) / NUM_BONES
BONE_LEN     = BONE_SPACING * 0.9

if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

bpy.ops.object.armature_add(enter_editmode=True, location=(0, -NUM_BONES, 0))
arm_obj      = bpy.context.active_object
arm_obj.name = "V"
edit_bones   = arm_obj.data.edit_bones

for b in list(edit_bones):
    edit_bones.remove(b)

for i in range(NUM_BONES):
    b      = edit_bones.new(f"Bone_{i:03d}")
    y      = MESH_Y_START + i * BONE_SPACING
    b.head = Vector((0, y,            0))
    b.tail = Vector((0, y + BONE_LEN, 0))

bpy.ops.object.mode_set(mode='OBJECT')

