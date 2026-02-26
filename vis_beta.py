import bpy
import bmesh
import math
from mathutils import Vector, Matrix

# ══════════════════════════════════════════════════════════════════════
#  GÉNÉRATEUR DE VIS PARAMÉTRIQUE — Blender 5.0.1
#  Génère corps fileté + tête (hex / cylindrique / fraisée / bombée)
#  + empreinte (cruciforme / plate / torx / allen)
# ══════════════════════════════════════════════════════════════════════

# ── PARAMÈTRES PRINCIPAUX ─────────────────────────────────────────────

# Norme / diamètre
DIAMETER        = 0.006      # M6 → 6 mm  (M3=0.003, M4=0.004, M5=0.005, M8=0.008)

# Filetage
PITCH           = 0.001      # pas du filet en m  (M6 standard = 1 mm)
THREAD_DEPTH    = 0.35       # profondeur du filet en fraction du diamètre
THREAD_SEGMENTS = 32         # segments par tour (qualité hélix)
THREAD_PROFILE  = 'ISO'      # 'ISO' (60°) | 'WHITWORTH' (55°) | 'SQUARE' | 'BUTTRESS'

# Corps
SHAFT_LENGTH    = 0.030      # longueur du corps fileté (30 mm)
SHANK_LENGTH    = 0.000      # longueur lisse sous la tête (0 = entièrement fileté)
SHAFT_SEGMENTS  = 24         # segments radiaux du corps

# Tête
HEAD_TYPE       = 'HEX'      # 'HEX' | 'CYLINDER' | 'COUNTERSUNK' | 'DOMED' | 'NONE'
HEAD_DIAMETER   = 0.010      # diamètre de la tête (M6 hex ≈ 10 mm)
HEAD_HEIGHT     = 0.004      # hauteur de la tête  (M6 hex ≈ 4 mm)
HEX_CHAMFER     = 0.15       # chanfrein haut de tête hex (fraction de HEAD_HEIGHT)

# Empreinte
DRIVE_TYPE      = 'ALLEN'    # 'ALLEN' | 'PHILIPS' | 'SLOT' | 'TORX' | 'NONE'
DRIVE_DEPTH     = 0.003      # profondeur de l'empreinte
DRIVE_SIZE      = 0.70       # fraction du diamètre de tête

# Pointe
TIP_TYPE        = 'CHAMFER'  # 'CHAMFER' | 'FLAT' | 'CONE'
TIP_LENGTH      = 0.002      # longueur de la pointe

# Rendu
SMOOTH_SHADE    = False
MATERIAL_COLOR  = (0.7, 0.7, 0.75, 1.0)   # acier inox
ROUGHNESS       = 0.25
METALLIC        = 1.0

# Position dans la scène
LOCATION        = (0.0, 0.0, 0.0)
NAME            = "Vis_Generee"

'''
# Vis M4 cruciforme fraisée
DIAMETER=0.004  HEAD_TYPE='COUNTERSUNK'  DRIVE_TYPE='PHILIPS'

# Boulon M8 hex allen
DIAMETER=0.008  HEAD_TYPE='HEX'  DRIVE_TYPE='ALLEN'

# Vis M3 Torx tête bombée
DIAMETER=0.003  HEAD_TYPE='DOMED'  DRIVE_TYPE='TORX'

# Vis autotaraudeuse M5 à filet carré
DIAMETER=0.005  THREAD_PROFILE='SQUARE'  TIP_TYPE='CONE'
'''

# ══════════════════════════════════════════════════════════════════════
#  UTILITAIRES
# ══════════════════════════════════════════════════════════════════════

def remove_if_exists(name):
    for n in [name, name + "_head", name + "_thread", name + "_shank"]:
        obj = bpy.data.objects.get(n)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)

def make_material(name):
    mat = bpy.data.materials.get(name)
    if mat:
        bpy.data.materials.remove(mat)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value  = MATERIAL_COLOR
        bsdf.inputs["Roughness"].default_value   = ROUGHNESS
        bsdf.inputs["Metallic"].default_value    = METALLIC
    return mat

def apply_smooth(obj):
    if SMOOTH_SHADE:
        for poly in obj.data.polygons:
            poly.use_smooth = True
        obj.data.update()

def set_origin_to_base(obj):
    """Déplace l'origine à la base de la vis (Z=0 = dessous de la tête)."""
    obj.location.z += 0
    bpy.context.view_layer.update()

# ══════════════════════════════════════════════════════════════════════
#  1. FILETAGE (hélice + profil extrudé)
# ══════════════════════════════════════════════════════════════════════

def thread_profile_verts(r_major, r_minor, profile_type):
    """Retourne les vertices du profil de filet dans le plan XZ (2D)."""
    if profile_type == 'ISO':
        # Triangle 60° tronqué
        return [
            Vector((r_major,  0.5)),
            Vector((r_minor,  0.0)),
            Vector((r_major, -0.5)),
        ]
    elif profile_type == 'WHITWORTH':
        # Triangle 55° arrondi — approx par 4 pts
        angle = math.radians(55) / 2
        return [
            Vector((r_major,  0.5)),
            Vector((r_minor + (r_major - r_minor) * 0.1,  0.1)),
            Vector((r_minor + (r_major - r_minor) * 0.1, -0.1)),
            Vector((r_major, -0.5)),
        ]
    elif profile_type == 'SQUARE':
        return [
            Vector((r_major,  0.5)),
            Vector((r_minor,  0.5)),
            Vector((r_minor, -0.5)),
            Vector((r_major, -0.5)),
        ]
    elif profile_type == 'BUTTRESS':
        return [
            Vector((r_major,  0.5)),
            Vector((r_minor,  0.0)),
            Vector((r_major, -0.5)),
            Vector((r_major, -0.5)),
        ]
    return [Vector((r_major, 0.5)), Vector((r_minor, 0.0)), Vector((r_major, -0.5))]


def build_thread(r_outer, pitch, depth_frac, length, segments, profile_type):
    """Construit le mesh du filetage par révolution hélicoïdale."""
    r_major = r_outer / 2
    r_minor = r_major * (1.0 - depth_frac)
    profile = thread_profile_verts(r_major, r_minor, profile_type)

    turns       = length / pitch
    total_steps = int(turns * segments)
    dz          = pitch / segments
    dangle      = 2 * math.pi / segments
    np          = len(profile)  # points par profil

    verts = []
    faces = []

    for step in range(total_steps + 1):
        angle = step * dangle
        z     = step * dz
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        for p in profile:
            r = p.x
            verts.append(Vector((r * cos_a, r * sin_a, z)))

    # Faces entre deux anneaux consécutifs
    for step in range(total_steps):
        base  = step * np
        base2 = (step + 1) * np
        for j in range(np - 1):
            faces.append((base + j, base + j + 1, base2 + j + 1, base2 + j))

    mesh = bpy.data.meshes.new("thread_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


# ══════════════════════════════════════════════════════════════════════
#  2. CORPS LISSE (shank)
# ══════════════════════════════════════════════════════════════════════

def build_cylinder(radius, length, segments, name):
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends   = True,
        cap_tris   = False,
        segments   = segments,
        radius1    = radius,
        radius2    = radius,
        depth      = length,
    )
    # Déplace pour que la base soit en Z=0
    for v in bm.verts:
        v.co.z += length / 2
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


# ══════════════════════════════════════════════════════════════════════
#  3. TÊTE
# ══════════════════════════════════════════════════════════════════════

def build_head_hex(diameter, height, chamfer_frac, segments=6):
    """Tête hexagonale avec chanfrein supérieur."""
    bm = bmesh.new()
    r  = diameter / 2
    # Hexagone = cercle inscrit, on utilise la distance entre-plats
    # diameter = entre-plats → r_vertex = diameter / (2 * cos(30°))
    r_v = r / math.cos(math.radians(30))
    chamfer_h = height * chamfer_frac
    body_h    = height - chamfer_h

    # Anneau bas
    verts_bot = []
    for i in range(6):
        a = math.radians(30 + 60 * i)
        verts_bot.append(bm.verts.new(Vector((r_v * math.cos(a), r_v * math.sin(a), 0))))

    # Anneau haut corps
    verts_mid = []
    for i in range(6):
        a = math.radians(30 + 60 * i)
        verts_mid.append(bm.verts.new(Vector((r_v * math.cos(a), r_v * math.sin(a), body_h))))

    # Anneau chanfrein (rayon réduit)
    r_champ = r_v * 0.85
    verts_top = []
    for i in range(6):
        a = math.radians(30 + 60 * i)
        verts_top.append(bm.verts.new(Vector((r_champ * math.cos(a), r_champ * math.sin(a), height))))

    # Centre haut
    v_top_center = bm.verts.new(Vector((0, 0, height)))

    # Faces latérales
    for i in range(6):
        j = (i + 1) % 6
        bm.faces.new([verts_bot[i], verts_bot[j], verts_mid[j], verts_mid[i]])
        bm.faces.new([verts_mid[i], verts_mid[j], verts_top[j], verts_top[i]])

    # Face bas
    bm.faces.new(verts_bot[::-1])

    # Dessus avec chanfrein
    for i in range(6):
        j = (i + 1) % 6
        bm.faces.new([verts_top[i], verts_top[j], v_top_center])

    bm.verts.index_update()
    bm.normal_update()
    mesh = bpy.data.meshes.new("head_hex")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def build_head_cylinder(diameter, height, segments=32):
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False,
        segments=segments,
        radius1=diameter / 2,
        radius2=diameter / 2,
        depth=height,
    )
    for v in bm.verts:
        v.co.z += height / 2
    mesh = bpy.data.meshes.new("head_cyl")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def build_head_countersunk(diameter, height, shaft_d, segments=32):
    """Tête fraisée (conique)."""
    bm = bmesh.new()
    r_top = diameter / 2
    r_bot = shaft_d / 2
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False,
        segments=segments,
        radius1=r_bot,
        radius2=r_top,
        depth=height,
    )
    for v in bm.verts:
        v.co.z += height / 2
    mesh = bpy.data.meshes.new("head_countersunk")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def build_head_domed(diameter, height, segments=32):
    """Tête bombée (hémisphère + cylindre court)."""
    bm = bmesh.new()
    r = diameter / 2
    cyl_h = height * 0.3
    dome_h = height - cyl_h
    # Base cylindrique
    ring = []
    for i in range(segments):
        a = 2 * math.pi * i / segments
        ring.append(bm.verts.new(Vector((r * math.cos(a), r * math.sin(a), 0))))
    ring_top = []
    for i in range(segments):
        a = 2 * math.pi * i / segments
        ring_top.append(bm.verts.new(Vector((r * math.cos(a), r * math.sin(a), cyl_h))))
    bm.faces.new(ring[::-1])
    for i in range(segments):
        j = (i + 1) % segments
        bm.faces.new([ring[i], ring[j], ring_top[j], ring_top[i]])
    # Dôme sphérique
    dome_segs = 12
    prev_ring = ring_top
    for s in range(1, dome_segs + 1):
        phi = math.pi / 2 * s / dome_segs
        rr  = r * math.cos(phi)
        zz  = cyl_h + dome_h * math.sin(phi)
        if s < dome_segs:
            cur_ring = []
            for i in range(segments):
                a = 2 * math.pi * i / segments
                cur_ring.append(bm.verts.new(Vector((rr * math.cos(a), rr * math.sin(a), zz))))
            for i in range(segments):
                j = (i + 1) % segments
                bm.faces.new([prev_ring[i], prev_ring[j], cur_ring[j], cur_ring[i]])
            prev_ring = cur_ring
        else:
            tip = bm.verts.new(Vector((0, 0, cyl_h + dome_h)))
            for i in range(segments):
                j = (i + 1) % segments
                bm.faces.new([prev_ring[i], prev_ring[j], tip])
    bm.verts.index_update()
    bm.normal_update()
    mesh = bpy.data.meshes.new("head_domed")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


# ══════════════════════════════════════════════════════════════════════
#  4. EMPREINTE (boolean soustrait de la tête)
# ══════════════════════════════════════════════════════════════════════

def build_drive_allen(head_d, depth, size_frac, head_z_top):
    """Hexagone creux (clé Allen)."""
    r = (head_d * size_frac) / 2 / math.cos(math.radians(30))
    bm = bmesh.new()
    verts_bot, verts_top = [], []
    for i in range(6):
        a = math.radians(30 + 60 * i)
        x, y = r * math.cos(a), r * math.sin(a)
        verts_bot.append(bm.verts.new(Vector((x, y, head_z_top - depth))))
        verts_top.append(bm.verts.new(Vector((x, y, head_z_top + 0.0001))))
    bm.faces.new(verts_bot)
    bm.faces.new(verts_top[::-1])
    for i in range(6):
        j = (i + 1) % 6
        bm.faces.new([verts_bot[i], verts_bot[j], verts_top[j], verts_top[i]])
    bm.verts.index_update()
    bm.normal_update()
    mesh = bpy.data.meshes.new("drive_allen")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def build_drive_slot(head_d, depth, size_frac, head_z_top):
    """Fente plate."""
    w = head_d * size_frac * 0.15
    l = head_d * size_frac / 2
    bm = bmesh.new()
    coords_bot = [(-l, -w, head_z_top - depth), (l, -w, head_z_top - depth),
                  (l,  w, head_z_top - depth), (-l,  w, head_z_top - depth)]
    coords_top = [(-l, -w, head_z_top + 0.0001), (l, -w, head_z_top + 0.0001),
                  (l,  w, head_z_top + 0.0001), (-l,  w, head_z_top + 0.0001)]
    vb = [bm.verts.new(Vector(c)) for c in coords_bot]
    vt = [bm.verts.new(Vector(c)) for c in coords_top]
    bm.faces.new(vb)
    bm.faces.new(vt[::-1])
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new([vb[i], vb[j], vt[j], vt[i]])
    bm.verts.index_update()
    bm.normal_update()
    mesh = bpy.data.meshes.new("drive_slot")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def build_drive_philips(head_d, depth, size_frac, head_z_top):
    """Croix cruciforme (Philips) — deux fentes croisées."""
    w = head_d * size_frac * 0.13
    l = head_d * size_frac / 2
    bm = bmesh.new()
    all_vb, all_vt = [], []
    for angle_deg in (0, 90):
        a = math.radians(angle_deg)
        ca, sa = math.cos(a), math.sin(a)
        coords = [
            (-l*ca + w*sa, -l*sa - w*ca, head_z_top - depth),
            ( l*ca + w*sa,  l*sa - w*ca, head_z_top - depth),
            ( l*ca - w*sa,  l*sa + w*ca, head_z_top - depth),
            (-l*ca - w*sa, -l*sa + w*ca, head_z_top - depth),
        ]
        vb = [bm.verts.new(Vector(c)) for c in coords]
        vt = [bm.verts.new(Vector((c[0], c[1], head_z_top + 0.0001))) for c in coords]
        bm.faces.new(vb)
        bm.faces.new(vt[::-1])
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new([vb[i], vb[j], vt[j], vt[i]])
    bm.verts.index_update()
    bm.normal_update()
    mesh = bpy.data.meshes.new("drive_philips")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def build_drive_torx(head_d, depth, size_frac, head_z_top):
    """Étoile Torx à 6 lobes."""
    r_out = head_d * size_frac * 0.38
    r_in  = r_out * 0.55
    pts   = 6
    bm = bmesh.new()
    vb, vt = [], []
    for i in range(pts * 2):
        a = math.pi * i / pts
        r = r_out if i % 2 == 0 else r_in
        x, y = r * math.cos(a), r * math.sin(a)
        vb.append(bm.verts.new(Vector((x, y, head_z_top - depth))))
        vt.append(bm.verts.new(Vector((x, y, head_z_top + 0.0001))))
    bm.faces.new(vb)
    bm.faces.new(vt[::-1])
    n = len(vb)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([vb[i], vb[j], vt[j], vt[i]])
    bm.verts.index_update()
    bm.normal_update()
    mesh = bpy.data.meshes.new("drive_torx")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


# ══════════════════════════════════════════════════════════════════════
#  5. POINTE
# ══════════════════════════════════════════════════════════════════════

def build_tip(shaft_r, tip_type, tip_length, segments):
    bm = bmesh.new()
    if tip_type == 'CONE':
        bmesh.ops.create_cone(
            bm, cap_ends=True, cap_tris=False,
            segments=segments, radius1=0.0001, radius2=shaft_r, depth=tip_length,
        )
        for v in bm.verts:
            v.co.z += tip_length / 2
    elif tip_type == 'CHAMFER':
        bmesh.ops.create_cone(
            bm, cap_ends=True, cap_tris=False,
            segments=segments,
            radius1=shaft_r * 0.3,
            radius2=shaft_r,
            depth=tip_length,
        )
        for v in bm.verts:
            v.co.z += tip_length / 2
    else:  # FLAT
        bmesh.ops.create_circle(bm, cap_tris=False, segments=segments, radius=shaft_r)
    mesh = bpy.data.meshes.new("tip_mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


# ══════════════════════════════════════════════════════════════════════
#  6. ASSEMBLAGE
# ══════════════════════════════════════════════════════════════════════

def assemble_screw():
    remove_if_exists(NAME)
    mat = make_material(NAME + "_Mat")
    col = bpy.context.collection
    objects_to_join = []

    shaft_r = DIAMETER / 2
    # Z=0 : base de la tête | Z positif : vers le bas

    z_head_bot = 0.0
    z_head_top = HEAD_HEIGHT
    z_shank_bot = -SHANK_LENGTH if SHANK_LENGTH > 0 else 0
    z_thread_top = z_head_bot - SHANK_LENGTH
    z_thread_bot = z_thread_top - SHAFT_LENGTH
    z_tip_bot    = z_thread_bot - TIP_LENGTH

    # ── Tête ─────────────────────────────────────────────────────────
    if HEAD_TYPE != 'NONE':
        if HEAD_TYPE == 'HEX':
            head_mesh = build_head_hex(HEAD_DIAMETER, HEAD_HEIGHT, HEX_CHAMFER)
        elif HEAD_TYPE == 'CYLINDER':
            head_mesh = build_head_cylinder(HEAD_DIAMETER, HEAD_HEIGHT)
        elif HEAD_TYPE == 'COUNTERSUNK':
            head_mesh = build_head_countersunk(HEAD_DIAMETER, HEAD_HEIGHT, DIAMETER)
        elif HEAD_TYPE == 'DOMED':
            head_mesh = build_head_domed(HEAD_DIAMETER, HEAD_HEIGHT)
        else:
            head_mesh = build_head_cylinder(HEAD_DIAMETER, HEAD_HEIGHT)

        head_obj = bpy.data.objects.new(NAME + "_head", head_mesh)
        head_obj.location = (0, 0, 0)
        col.objects.link(head_obj)
        head_obj.data.materials.append(mat)
        apply_smooth(head_obj)
        objects_to_join.append(head_obj)

        # ── Empreinte (boolean) ───────────────────────────────────────
        if DRIVE_TYPE != 'NONE':
            if DRIVE_TYPE == 'ALLEN':
                drive_mesh = build_drive_allen(HEAD_DIAMETER, DRIVE_DEPTH, DRIVE_SIZE, HEAD_HEIGHT)
            elif DRIVE_TYPE == 'SLOT':
                drive_mesh = build_drive_slot(HEAD_DIAMETER, DRIVE_DEPTH, DRIVE_SIZE, HEAD_HEIGHT)
            elif DRIVE_TYPE == 'PHILIPS':
                drive_mesh = build_drive_philips(HEAD_DIAMETER, DRIVE_DEPTH, DRIVE_SIZE, HEAD_HEIGHT)
            elif DRIVE_TYPE == 'TORX':
                drive_mesh = build_drive_torx(HEAD_DIAMETER, DRIVE_DEPTH, DRIVE_SIZE, HEAD_HEIGHT)
            else:
                drive_mesh = None

            if drive_mesh:
                drive_obj = bpy.data.objects.new(NAME + "_drive", drive_mesh)
                drive_obj.location = (0, 0, 0)
                col.objects.link(drive_obj)

                bpy.context.view_layer.objects.active = head_obj
                mod = head_obj.modifiers.new("Drive", type='BOOLEAN')
                mod.operation = 'DIFFERENCE'
                mod.object    = drive_obj
                mod.solver    = 'MANIFOLD'#'FAST'
                bpy.ops.object.select_all(action='DESELECT')
                head_obj.select_set(True)
                bpy.context.view_layer.objects.active = head_obj
                bpy.ops.object.modifier_apply(modifier="Drive")
                bpy.data.objects.remove(drive_obj, do_unlink=True)

    # ── Corps lisse (shank) ───────────────────────────────────────────
    if SHANK_LENGTH > 0.0001:
        shank_mesh = build_cylinder(shaft_r, SHANK_LENGTH, SHAFT_SEGMENTS, NAME + "_shank")
        shank_obj  = bpy.data.objects.new(NAME + "_shank", shank_mesh)
        shank_obj.location = (0, 0, -SHANK_LENGTH)
        col.objects.link(shank_obj)
        shank_obj.data.materials.append(mat)
        apply_smooth(shank_obj)
        objects_to_join.append(shank_obj)

    # ── Filetage ──────────────────────────────────────────────────────
    thread_mesh = build_thread(
        DIAMETER, PITCH, THREAD_DEPTH,
        SHAFT_LENGTH, THREAD_SEGMENTS, THREAD_PROFILE
    )
    thread_obj = bpy.data.objects.new(NAME + "_thread", thread_mesh)
    thread_obj.location = (0, 0, z_thread_top)
    col.objects.link(thread_obj)
    thread_obj.data.materials.append(mat)
    apply_smooth(thread_obj)
    objects_to_join.append(thread_obj)

    # ── Pointe ────────────────────────────────────────────────────────
    if TIP_TYPE != 'FLAT':
        tip_mesh = build_tip(shaft_r, TIP_TYPE, TIP_LENGTH, SHAFT_SEGMENTS)
        tip_obj  = bpy.data.objects.new(NAME + "_tip", tip_mesh)
        tip_obj.location = (0, 0, z_tip_bot)
        col.objects.link(tip_obj)
        tip_obj.data.materials.append(mat)
        apply_smooth(tip_obj)
        objects_to_join.append(tip_obj)

    # ── Join tous les objets ──────────────────────────────────────────
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects_to_join:
        o.select_set(True)
    if objects_to_join:
        bpy.context.view_layer.objects.active = objects_to_join[0]
        bpy.ops.object.join()
        final = bpy.context.active_object
        final.name = NAME
        final.location = LOCATION
        print(f"✅ Vis '{NAME}' générée")
        print(f"   Diamètre    : M{int(DIAMETER*1000)} ({DIAMETER*1000:.1f} mm)")
        print(f"   Pas         : {PITCH*1000:.2f} mm  [{THREAD_PROFILE}]")
        print(f"   Longueur    : {SHAFT_LENGTH*1000:.1f} mm  +  shank {SHANK_LENGTH*1000:.1f} mm")
        print(f"   Tête        : {HEAD_TYPE}  ø{HEAD_DIAMETER*1000:.1f} mm  h{HEAD_HEIGHT*1000:.1f} mm")
        print(f"   Empreinte   : {DRIVE_TYPE}")
        print(f"   Pointe      : {TIP_TYPE}")
        return final
    return None


# ══════════════════════════════════════════════════════════════════════
#  LANCEMENT
# ══════════════════════════════════════════════════════════════════════
if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

assemble_screw()
