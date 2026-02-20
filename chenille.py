import bpy
import math
import bmesh

scale_factor = 25 #nbBones, scale armature, nbSquare, -Y +Y frame, 
BONE_LENGTH = 0.1
SCALE_FACTOR = 0.8743 # 25 0.8743 so 50 * 2
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 500
bpy.context.scene.render.fps = 120
bpy.context.scene.render.fps_base = 1.0
bpy.context.scene.frame_current = 1

if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
#bpy.ops.object.select_all(action='SELECT')
#bpy.ops.object.delete(use_global=False)
radius = 3
magic_cubique_bezier = 0.5522847498
circumference = 2 * math.pi * radius

bpy.ops.object.armature_add(enter_editmode=False, location=(0, -scale_factor, 0))
armature = bpy.context.active_object
armature.name = "petite_chenille_deviendra_grande"
armature.rotation_euler[0] = math.radians(-90)
bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
armature.scale = (scale_factor, scale_factor, scale_factor)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.armature.select_all(action='SELECT')
bpy.ops.armature.subdivide(number_cuts=scale_factor - 1)
edit_bones = armature.data.edit_bones
bones_by_position = sorted(edit_bones, key=lambda b: b.head.y, reverse=True)
num_bones = len(bones_by_position)
for i, bone in enumerate(bones_by_position):
    bone.name = f"Bone_{i:03d}"
bpy.ops.object.mode_set(mode='OBJECT')
bones = armature.data.bones
num_bones = len(bones)
first_bone = bones[0]
bone_length_local = first_bone.length
bone_length = bone_length_local * scale_factor
bone_head_world = armature.matrix_world @ first_bone.head_local

bpy.ops.mesh.primitive_plane_add(size=bone_length, location=(0, 0, 0))
plane = bpy.context.active_object
plane.name = "do_not_export"
plane.rotation_euler[1] = math.radians(90)
plane.location = bone_head_world.copy()
plane.location.y -= bone_length / 2 - scale_factor
plane.scale.x = 0.25
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(plane.data)
bm.faces.ensure_lookup_table()
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
for f in bm.faces:
    f.select = False
for e in bm.edges:
    e.select = False
for v in bm.verts:
    v.select = False
horizontal_edges_per_iteration = []
for edge in bm.edges:
    v1, v2 = edge.verts
    if v1.co.y > 0 and v2.co.y > 0:
        edge_vert_indices = [v.index for v in edge.verts]
        horizontal_edges_per_iteration.append(edge_vert_indices)
        break
for edge in bm.edges:
    v1, v2 = edge.verts
    if v1.co.y < 0 and v2.co.y < 0:
        edge.select = True
        break
bmesh.update_edit_mesh(plane.data)
for i in range(num_bones - 1):
    selected_edges = [e for e in bm.edges if e.select]
    if not selected_edges:
        break
    edge_vert_indices = []
    for e in selected_edges:
        edge_vert_indices.extend([v.index for v in e.verts])
    horizontal_edges_per_iteration.append(list(set(edge_vert_indices)))
    extruded = bmesh.ops.extrude_edge_only(bm, edges=selected_edges)
    new_verts = [v for v in extruded['geom'] if isinstance(v, bmesh.types.BMVert)]
    if new_verts:
        bmesh.ops.translate(bm, vec=(0, -bone_length, 0), verts=new_verts)
    for e in bm.edges:
        e.select = False
    new_edges = [g for g in extruded['geom'] if isinstance(g, bmesh.types.BMEdge)]
    for e in new_edges:
        v1, v2 = e.verts
        if abs(v1.co.x - v2.co.x) > 0.1:
            e.select = True
    bmesh.update_edit_mesh(plane.data)
selected_edges = [e for e in bm.edges if e.select]
if selected_edges:
    edge_vert_indices = []
    for e in selected_edges:
        edge_vert_indices.extend([v.index for v in e.verts])
    horizontal_edges_per_iteration.append(list(set(edge_vert_indices)))
bpy.ops.object.mode_set(mode='OBJECT')
max_group_index = len(horizontal_edges_per_iteration) - 1
for i, vert_indices in enumerate(horizontal_edges_per_iteration):
    vg_name = f"Group_{i:03d}"
    vg = plane.vertex_groups.new(name=vg_name)
    vg.add(vert_indices, 1.0, 'REPLACE')
bpy.ops.object.select_all(action='DESELECT')
plane.select_set(True)
armature.select_set(True)
bpy.context.view_layer.objects.active = armature

bpy.ops.object.mode_set(mode='POSE')
pose_bones = armature.pose.bones
last_bone = pose_bones[scale_factor - 1]
first_bone = pose_bones[0]
copy_loc = first_bone.constraints.new('COPY_LOCATION')
copy_loc.target = plane
copy_loc.subtarget = f"Group_{max_group_index:03d}"
copy_rot = first_bone.constraints.new('COPY_ROTATION')
copy_rot.target = plane
copy_rot.subtarget = f"Group_{max_group_index:03d}"
stretch = first_bone.constraints.new('STRETCH_TO')
stretch.target = plane
stretch.subtarget = f"Group_{max_group_index - 1:03d}"
stretch.rest_length = 0
stretch.bulge = 0
for i in range(1, scale_factor):
    bone = pose_bones[i]
    rotation_group_index = i + 1
    if rotation_group_index <= max_group_index:
        copy_rot = bone.constraints.new('COPY_ROTATION')
        copy_rot.target = plane
        copy_rot.subtarget = f"Group_{max_group_index - i:03d}"
for i in range(1, num_bones):
    bone = pose_bones[i]
    stretch_group_index = i + 1
    if stretch_group_index <= max_group_index:
        stretch = bone.constraints.new('STRETCH_TO')
        stretch.target = plane
        stretch.subtarget = f"Group_{max_group_index - i - 1:03d}"
        stretch.rest_length = 0
        stretch.bulge = 0
bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()
bpy.context.evaluated_depsgraph_get()

bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT')
armature.select_set(True)
bpy.context.view_layer.objects.active = armature
bpy.ops.object.mode_set(mode='EDIT')
edit_bones = armature.data.edit_bones
bpy.ops.armature.select_all(action='DESELECT')
edit_bones[0].select = True
edit_bones[0].select_head = True
edit_bones[0].select_tail = True
bpy.ops.armature.duplicate()
new_bone = bpy.context.selected_editable_bones[0]
new_bone.name = "Bone_Control"
new_bone.head.x = 3
new_bone.head.y -= 6
new_bone.head.z += 3
new_bone.tail.x = 3
new_bone.tail.y -= 5.6
new_bone.tail.z += 3
center = (new_bone.head + new_bone.tail) / 2
new_bone.head = center + (new_bone.head - center) * 2.5
new_bone.tail = center + (new_bone.tail - center) * 2.5
bpy.ops.armature.select_all(action='DESELECT')
edit_bones[0].select = True
edit_bones[0].select_head = True
edit_bones[0].select_tail = True
edit_bones["Bone_Control"].select = True
edit_bones["Bone_Control"].select_head = True
edit_bones["Bone_Control"].select_tail = True
armature.data.edit_bones.active = edit_bones["Bone_Control"]
bpy.ops.armature.parent_set(type='OFFSET')
bpy.ops.object.mode_set(mode='POSE')
bone_control_pose = armature.pose.bones["Bone_Control"]
while len(bone_control_pose.constraints) > 0:
    bone_control_pose.constraints.remove(bone_control_pose.constraints[0])
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
plane.select_set(True)
armature.select_set(True)
bpy.context.view_layer.objects.active = armature
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='DESELECT')
armature.data.bones.active = armature.data.bones["Bone_Control"]
#bone_control_pose.bone.select = True
bpy.ops.object.parent_set(type='BONE')
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
armature.select_set(True)
bpy.context.view_layer.objects.active = armature
armature.location.y = scale_factor
armature.keyframe_insert(data_path="location", frame=1, index=1)
armature.location.y = -scale_factor
armature.keyframe_insert(data_path="location", frame=450, index=1)

curve_data = bpy.data.curves.new('TrackPath_Data', type='CURVE')
curve_data.dimensions = '3D'
curve_data.resolution_u = 1024
curve_data.use_radius = False
curve_obj = bpy.data.objects.new('CurvePath', curve_data)
bpy.context.collection.objects.link(curve_obj)
spline = curve_data.splines.new('BEZIER')
spline.resolution_u = 64
points_coords = [
    (-0.3000, -0.1273, 0),
    ( 0.6000, -0.1273, 0),
    ( 0.6486,  0.1176, 0),
    ( 0.0669,  0.4618, 0),
    (-0.1091,  0.4369, 0),
    (-0.3793,  0.0996, 0)
]
spline.bezier_points.add(len(points_coords) - 1)
for i, coord in enumerate(points_coords):
    bp = spline.bezier_points[i]
    bp.co = coord
    bp.handle_left_type = 'FREE'
    bp.handle_right_type = 'FREE'
def set_handle(bp, point, center, radius, scale_k, is_exit):
    angle = math.atan2(point[1] - center[1], point[0] - center[0])
    tangent_x = -math.sin(angle)
    tangent_y = math.cos(angle)
    handle_len = scale_k * radius
    if is_exit:
        bp.handle_left = (
            point[0] - handle_len * tangent_x,
            point[1] - handle_len * tangent_y,
            0 )
    else:
        bp.handle_right = (
            point[0] + handle_len * tangent_x,
            point[1] + handle_len * tangent_y,
            0 )
bp0 = spline.bezier_points[0]
set_handle(bp0, points_coords[0], (-0.3, 0), 0.1273, 0.949, True)
bp0.handle_right = (-0.25, -0.1273, 0)
bp1 = spline.bezier_points[1]
bp1.handle_left = (0.55, -0.1273, 0)
set_handle(bp1, points_coords[1], (0.6, 0), 0.1273, 1.095, False)
bp2 = spline.bezier_points[2]
set_handle(bp2, points_coords[2], (0.6, 0), 0.1273, 1.095, True)
dx = points_coords[3][0] - points_coords[2][0]
dy = points_coords[3][1] - points_coords[2][1]
line_len = math.sqrt(dx*dx + dy*dy)
bp2.handle_right = (
    points_coords[2][0] + 0.1 * dx / line_len,
    points_coords[2][1] + 0.1 * dy / line_len,
    0 )
bp3 = spline.bezier_points[3]
bp3.handle_left = (
    points_coords[3][0] - 0.1 * dx / line_len,
    points_coords[3][1] - 0.1 * dy / line_len,
    0 )
set_handle(bp3, points_coords[3], (0, 0.3), 0.1751, 0.364, False)
bp4 = spline.bezier_points[4]
set_handle(bp4, points_coords[4], (0, 0.3), 0.1751, 0.364, True)
dx = points_coords[5][0] - points_coords[4][0]
dy = points_coords[5][1] - points_coords[4][1]
line_len = math.sqrt(dx*dx + dy*dy)
bp4.handle_right = (
    points_coords[4][0] + 0.1 * dx / line_len,
    points_coords[4][1] + 0.1 * dy / line_len,
    0 )
bp5 = spline.bezier_points[5]
bp5.handle_left = (
    points_coords[5][0] - 0.1 * dx / line_len,
    points_coords[5][1] - 0.1 * dy / line_len,
    0 )

set_handle(bp5, points_coords[5], (-0.3, 0), 0.1273, 0.949, False)
spline.use_cyclic_u = True
bpy.ops.object.select_all(action='DESELECT')
curve_obj.select_set(True)
bpy.context.view_layer.objects.active = curve_obj
bpy.ops.transform.resize(value=(SCALE_FACTOR * 10, SCALE_FACTOR * 10, SCALE_FACTOR * 10))
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
#plane.select_set(True)
obj = bpy.data.objects.get("do_not_export")
bpy.context.view_layer.objects.active = obj
curve_modifier = plane.modifiers.new(name="Curve", type='CURVE')
curve_modifier.object = curve_obj
curve_modifier.deform_axis = 'POS_Y'
bpy.context.view_layer.update()
