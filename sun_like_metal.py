import bpy
import math

# ── Paramètres identiques à ton code Metal ────────────────────────
CYCLE_SECONDS = 120.0   # fmod(..., 120.f)
TILT_DEG      = 18.0    # M_PI * 0.1 ≈ 18°
FPS           = 120
FRAME_START   = 1
FRAME_END     = 450

SUN_NAME      = "Sun"

# ── Récupère ou crée le soleil ────────────────────────────────────
sun = bpy.data.objects.get(SUN_NAME)
if sun is None:
    bpy.ops.object.light_add(type='SUN')
    sun = bpy.context.active_object
    sun.name = SUN_NAME

sun.data.energy = 3.0   # ajuste selon ton sunColor

tilt = math.radians(TILT_DEG)

# ── Calcul de sunDirection → rotation Euler équivalente ──────────
# Ton Metal : 
#   x = cos(sunAngle) * sin(tilt)
#   y = sin(sunAngle)
#   z = cos(sunAngle) * cos(tilt)
# Blender Sun pointe selon -Z local → on oriente l'objet pour que
# -Z local == sunDirection

def sun_direction(time_of_day):
    angle = time_of_day * 2.0 * math.pi
    x = math.cos(angle) * math.sin(tilt)
    y = math.sin(angle)
    z = math.cos(angle) * math.cos(tilt)
    return (x, y, z)

def direction_to_euler(dx, dy, dz):
    # Rotation pour que l'axe -Z pointe vers (dx, dy, dz)
    # Blender: X = pitch, Z = azimuth
    length = math.sqrt(dx*dx + dy*dy + dz*dz)
    dx, dy, dz = dx/length, dy/length, dz/length
    rot_x = math.asin(-dy)           # élévation
    rot_z = math.atan2(dx, dz)       # azimut
    return (rot_x, 0.0, rot_z)

# ── Keyframes ────────────────────────────────────────────────────
sun.rotation_mode = 'XYZ'

for frame in range(FRAME_START, FRAME_END + 1):
    # Temps dans le cycle (en secondes) correspondant à cette frame
    time_in_seconds = (frame - FRAME_START) / FPS
    time_of_day     = math.fmod(time_in_seconds, CYCLE_SECONDS) / CYCLE_SECONDS
    
    dx, dy, dz = sun_direction(time_of_day)
    rx, ry, rz = direction_to_euler(dx, dy, dz)
    
    sun.rotation_euler = (rx, ry, rz)
    sun.keyframe_insert(data_path="rotation_euler", frame=frame)

# LINEAR sur toutes les keyframes du soleil
if sun.animation_data and sun.animation_data.action:
    slot = sun.animation_data.action_slot
    for layer in sun.animation_data.action.layers:
        for strip in layer.strips:
            cb = strip.channelbag(slot)
            if cb:
                for fc in cb.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'

bpy.context.scene.frame_set(FRAME_START)
print("✅ Soleil animé — cycle de", CYCLE_SECONDS, "s | tilt", TILT_DEG, "°")
