import bpy
import colorsys

hue_base = 0.65 # 0.0 = rouge, 0.33 = vert, 0.65 = bleu
n_stops  = 20

def hsv_to_rgba(h, s, v, a=1.0):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (r, g, b, a)

def create_colorramp_material(mat_name="Mat_ColorRamp_Triade", n_stops=20):
    if mat_name in bpy.data.materials:
        bpy.data.materials.remove(bpy.data.materials[mat_name])

    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output   = nodes.new("ShaderNodeOutputMaterial")
    bsdf     = nodes.new("ShaderNodeBsdfPrincipled")
    ramp     = nodes.new("ShaderNodeValToRGB")
    tex_coord = nodes.new("ShaderNodeTexCoord")
    mapping  = nodes.new("ShaderNodeMapping")
    noise    = nodes.new("ShaderNodeTexNoise")

    output.location    = (600, 0)
    bsdf.location      = (300, 0)
    ramp.location      = (0, 0)
    noise.location     = (-300, 0)
    mapping.location   = (-500, 0)
    tex_coord.location = (-700, 0)

    links.new(tex_coord.outputs["UV"],       mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"],     noise.inputs["Vector"])
    links.new(noise.outputs["Fac"],          ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"],         bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"],          output.inputs["Surface"])

    hue_base = 0.65
    hue_tri1 = (hue_base + 1/3) % 1.0 # +120° inv → orange-rouge
    hue_tri2 = (hue_base + 2/3) % 1.0 # +240° inv → vert

    palette_hues = [hue_base, hue_tri1, hue_tri2]

    spacing = 1.0 / (n_stops - 1) # = 0.0526315789473684 pour 20
    # 0.0909090909090909 12 so 11
    cr = ramp.color_ramp
    cr.interpolation = 'LINEAR'

    while len(cr.elements) > 1:
        cr.elements.remove(cr.elements[-1])

    for i in range(n_stops):
        pos = i * spacing
        pos = min(pos, 1.0)

        # Choix de teinte dans la triade + petite variation analogique ±5°
        hue_idx   = i % 3
        base_hue  = palette_hues[hue_idx]
        variation = ((i // 3) % 4) * 0.03  # décalage subtil similaire
        hue       = (base_hue + variation) % 1.0

        sat = 0.7 + 0.15 * ((i % 4) / 3)   # entre 0.70 et 0.85
        val = 0.6 + 0.3  * ((i % 5) / 4)   # entre 0.60 et 0.90

        color = hsv_to_rgba(hue, sat, val)

        if i == 0:
            cr.elements[0].position = 0.0
            cr.elements[0].color = color
        else:
            el = cr.elements.new(pos)
            el.color = color

    return mat

mat = create_colorramp_material()

obj = bpy.context.active_object
if obj and obj.type == 'Cylinder.001':
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

