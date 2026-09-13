"""
siege_scene.py -- SIEGE cinematic loop, built procedurally for Blender 5.2 (EEVEE).

No external assets. Builds the scene, animates a seamless loop, sets up
bloom + vignette in the (5.x) compositor and renders PNG frames.

    Blender -b -P siege_scene.py -- --out DIR --res 1280 720 --frames 180
    Blender -b -P siege_scene.py -- --out DIR --hero --res 3200 1800 --hero-frame 90 --samples 128

Options
    --out DIR            output directory (frames go to DIR/frames/frame_####.png)
    --res W H            resolution (default 1280 720)
    --frames N           loop length in frames (default 180 = 6 s @ 30 fps)
    --start A --end B    render only a sub-range (defaults 1..N)
    --samples S          EEVEE TAA samples (default 48; 128 for --hero)
    --hero               render one still (DIR/siege_hero.png) at --hero-frame
    --hero-frame F       frame for the hero still (default 90)
    --fstop F            camera f-stop for depth of field, 0 disables (default 0)
    --count N            number of projectiles (default 96)
    --seed N             RNG seed (default 7)
    --save-blend PATH    also save the built scene as a .blend
    --no-render          build only

Story: attacks fly in from a wide circle toward a luminous typed gate.
Most shatter on the ring (amber), about one in six breaches (red) and
hits the core; a violet "defender" sweep rewrites the gate each round.
"""
import argparse
import math
import os
import random
import sys
import time

import bpy
from mathutils import Vector

TAU = math.tau


# ----------------------------------------------------------------- palette
def _srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_lin(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return (_srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b), 1.0)


def mix(c1, c2, t):
    return tuple(c1[i] * (1.0 - t) + c2[i] * t for i in range(3)) + (1.0,)


BG = hex_lin("#07080c")
EMERALD = hex_lin("#22c55e")
AMBER = hex_lin("#ffb020")
RED = hex_lin("#ff3b5c")
VIOLET = hex_lin("#a78bfa")
BLUE = hex_lin("#60a5fa")
WHITE = (1.0, 1.0, 1.0, 1.0)
NEUTRAL = mix(BLUE, WHITE, 0.45)        # colour of an attack in flight
SPARK = mix(AMBER, WHITE, 0.2)

# --------------------------------------------------------------- geometry
R_GATE = 3.0          # ring major radius
TUBE = 0.075          # ring tube radius
R_HIT = R_GATE + 0.12  # where a blocked projectile stops
R_CORE = 0.42         # where a breach ends


# ------------------------------------------------------------------- CLI
def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(description="SIEGE loop builder")
    p.add_argument("--out", required=True)
    p.add_argument("--res", nargs=2, type=int, default=[1280, 720])
    p.add_argument("--frames", type=int, default=180)
    p.add_argument("--start", type=int, default=1)
    p.add_argument("--end", type=int, default=None)
    p.add_argument("--samples", type=int, default=None)
    p.add_argument("--hero", action="store_true")
    p.add_argument("--hero-frame", type=int, default=90)
    p.add_argument("--fstop", type=float, default=0.0)
    p.add_argument("--count", type=int, default=96)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--save-blend", default=None)
    p.add_argument("--no-render", action="store_true")
    return p.parse_args(argv)


ARGS = parse_args()
LOOP = ARGS.frames
FPS = 30


# ------------------------------------------------------------ small utils
def reset_blender():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    prefs = bpy.context.preferences.edit
    prefs.keyframe_new_interpolation_type = "LINEAR"
    prefs.keyframe_new_handle_type = "AUTO_CLAMPED"


def keyed(obj, path, frame, value=None, wrap=True):
    """Set `path` on obj and key it. With wrap=True the key is duplicated at
    frame +- LOOP so the animation is periodic over the loop."""
    if value is not None:
        setattr(obj, path, value)
    offs = (-LOOP, 0, LOOP) if wrap else (0,)
    for off in offs:
        obj.keyframe_insert(data_path=path, frame=frame + off)


def key_visible(obj, t_on, t_off):
    """Render-visible in [t_on, t_off), hidden elsewhere (wrapped)."""
    keyed(obj, "hide_render", t_on, False)
    keyed(obj, "hide_render", t_off, True)


def link_obj(obj, parent=None):
    bpy.context.scene.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def new_obj(name, mesh, material=None, parent=None):
    ob = bpy.data.objects.new(name, mesh)
    if material is not None and mesh is not None:
        if len(ob.material_slots) == 0:
            ob.data.materials.append(material) if not ob.data.materials else None
        ob.material_slots[0].link = "OBJECT"
        ob.material_slots[0].material = material
    return link_obj(ob, parent)


# ------------------------------------------------------------ node utils
def sock_in(n, key):
    for s in n.inputs:
        if s.identifier == key:
            return s
    for s in n.inputs:
        if s.name == key:
            return s
    raise KeyError(f"{n.bl_idname}: no input {key!r}")


def sock_out(n, key):
    for s in n.outputs:
        if s.identifier == key or s.name == key:
            return s
    raise KeyError(f"{n.bl_idname}: no output {key!r}")


def feed(tree, socket, value):
    """Link a socket to `value` if it is a socket, else set its default."""
    if isinstance(value, bpy.types.NodeSocket):
        tree.links.new(value, socket)
    else:
        socket.default_value = value


def nmath(tree, op, a, b=None, c=None, clamp=False):
    n = tree.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b, c)):
        if v is not None:
            feed(tree, n.inputs[i], v)
    return n.outputs[0]


def nrange(tree, v, fmin, fmax, tmin, tmax, interp="LINEAR"):
    n = tree.nodes.new("ShaderNodeMapRange")
    n.interpolation_type = interp
    n.clamp = True
    feed(tree, n.inputs["Value"], v)
    n.inputs["From Min"].default_value = fmin
    n.inputs["From Max"].default_value = fmax
    n.inputs["To Min"].default_value = tmin
    n.inputs["To Max"].default_value = tmax
    return n.outputs["Result"]


def nmix_color(tree, fac, a, b):
    n = tree.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    n.blend_type = "MIX"
    n.clamp_factor = True
    feed(tree, sock_in(n, "Factor_Float"), fac)
    feed(tree, sock_in(n, "A_Color"), a)
    feed(tree, sock_in(n, "B_Color"), b)
    return sock_out(n, "Result_Color")


def angle_of(tree):
    """Polar angle (radians) of the object-space XY coordinate."""
    tc = tree.nodes.new("ShaderNodeTexCoord")
    sep = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(tc.outputs["Object"], sep.inputs[0])
    return nmath(tree, "ARCTAN2", sep.outputs["Y"], sep.outputs["X"]), tc


def dash_pattern(tree, angle, count, inner, outer, low=0.0, high=1.0):
    """`count` soft dashes around the ring: 1 inside a dash, 0 in the gap."""
    a = nmath(tree, "MULTIPLY", angle, count / TAU)
    f = nmath(tree, "FRACT", a)
    d = nmath(tree, "ABSOLUTE", nmath(tree, "SUBTRACT", f, 0.5))
    return nrange(tree, d, inner, outer, high, low, "SMOOTHSTEP")


# -------------------------------------------------------------- materials
def mat_gate_ring():
    """Emerald neon ring with rotating typed dashes and a violet defender
    sweep. Returns (material, sweep_value_socket)."""
    m = bpy.data.materials.new("GateRing")
    m.use_nodes = True
    t = m.node_tree
    bsdf = t.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.01, 0.03, 0.02, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.85
    bsdf.inputs["Roughness"].default_value = 0.32

    ang, _ = angle_of(t)
    dash_fine = dash_pattern(t, ang, 48, 0.10, 0.30)           # typed segments
    dash_coarse = dash_pattern(t, ang, 12, 0.18, 0.46, 0.4, 1.0)  # slow grouping
    pattern = nmath(t, "MULTIPLY", dash_fine, dash_coarse)
    strength = nmath(t, "ADD", 3.2, nmath(t, "MULTIPLY", pattern, 5.5))

    sweep = t.nodes.new("ShaderNodeValue")
    sweep.name = "Sweep"
    sweep.outputs[0].default_value = 0.0
    diff = nmath(t, "SUBTRACT", ang, sweep.outputs[0])
    u = nmath(t, "DIVIDE", nmath(t, "WRAP", diff, TAU, 0.0), TAU)
    tail = nmath(t, "POWER", nrange(t, u, 0.78, 1.0, 0.0, 1.0), 2.4)

    color = nmix_color(t, tail, EMERALD, VIOLET)
    total = nmath(t, "ADD", strength, nmath(t, "MULTIPLY", tail, 9.0))
    t.links.new(color, bsdf.inputs["Emission Color"])
    t.links.new(total, bsdf.inputs["Emission Strength"])
    return m, sweep.outputs[0]


def mat_outer_ring():
    m = bpy.data.materials.new("OuterRing")
    m.use_nodes = True
    t = m.node_tree
    bsdf = t.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.005, 0.01, 0.01, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.5
    ang, _ = angle_of(t)
    dash = dash_pattern(t, ang, 96, 0.12, 0.28)
    bsdf.inputs["Emission Color"].default_value = mix(EMERALD, BLUE, 0.4)
    t.links.new(nmath(t, "MULTIPLY", dash, 1.8), bsdf.inputs["Emission Strength"])
    return m


def mat_object_glow(name):
    """Opaque emitter driven entirely by per-object colour (rgb) and
    brightness (alpha) so hundreds of objects share one material."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree
    t.nodes.remove(t.nodes["Principled BSDF"])
    out = t.nodes["Material Output"]
    info = t.nodes.new("ShaderNodeObjectInfo")
    em = t.nodes.new("ShaderNodeEmission")
    t.links.new(info.outputs["Color"], em.inputs["Color"])
    t.links.new(info.outputs["Alpha"], em.inputs["Strength"])
    t.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def mat_core():
    m = bpy.data.materials.new("Core")
    m.use_nodes = True
    t = m.node_tree
    t.nodes.remove(t.nodes["Principled BSDF"])
    out = t.nodes["Material Output"]
    info = t.nodes.new("ShaderNodeObjectInfo")
    lw = t.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.45
    rim = nmath(t, "ADD", 0.55, nmath(t, "MULTIPLY", lw.outputs["Facing"], 1.1))
    strength = nmath(t, "MULTIPLY", info.outputs["Alpha"], rim)
    em = t.nodes.new("ShaderNodeEmission")
    t.links.new(info.outputs["Color"], em.inputs["Color"])
    t.links.new(strength, em.inputs["Strength"])
    t.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def _blended(m):
    m.blend_method = "BLEND"
    m.surface_render_method = "BLENDED"
    m.show_transparent_back = False
    m.use_backface_culling = True


def mat_soft_blob():
    """Soft transparent-edged glow ball for the breach flash."""
    m = bpy.data.materials.new("FlashBlob")
    m.use_nodes = True
    t = m.node_tree
    t.nodes.remove(t.nodes["Principled BSDF"])
    out = t.nodes["Material Output"]
    info = t.nodes.new("ShaderNodeObjectInfo")
    lw = t.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    opacity = nmath(t, "POWER", nmath(t, "SUBTRACT", 1.0, lw.outputs["Facing"]), 1.6, clamp=True)
    em = t.nodes.new("ShaderNodeEmission")
    t.links.new(info.outputs["Color"], em.inputs["Color"])
    t.links.new(info.outputs["Alpha"], em.inputs["Strength"])
    tr = t.nodes.new("ShaderNodeBsdfTransparent")
    mixs = t.nodes.new("ShaderNodeMixShader")
    t.links.new(opacity, mixs.inputs[0])
    t.links.new(tr.outputs[0], mixs.inputs[1])
    t.links.new(em.outputs[0], mixs.inputs[2])
    t.links.new(mixs.outputs[0], out.inputs["Surface"])
    _blended(m)
    return m


def mat_impact_disc(radius):
    """Radial-falloff splash used where an attack meets the gate."""
    m = bpy.data.materials.new("Impact")
    m.use_nodes = True
    t = m.node_tree
    t.nodes.remove(t.nodes["Principled BSDF"])
    out = t.nodes["Material Output"]
    info = t.nodes.new("ShaderNodeObjectInfo")
    tc = t.nodes.new("ShaderNodeTexCoord")
    ln = t.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    t.links.new(tc.outputs["Object"], ln.inputs[0])
    fall = nmath(t, "POWER", nrange(t, ln.outputs["Value"], 0.0, radius, 1.0, 0.0), 1.8)
    em = t.nodes.new("ShaderNodeEmission")
    t.links.new(info.outputs["Color"], em.inputs["Color"])
    t.links.new(nmath(t, "MULTIPLY", info.outputs["Alpha"], fall), em.inputs["Strength"])
    tr = t.nodes.new("ShaderNodeBsdfTransparent")
    mixs = t.nodes.new("ShaderNodeMixShader")
    t.links.new(fall, mixs.inputs[0])
    t.links.new(tr.outputs[0], mixs.inputs[1])
    t.links.new(em.outputs[0], mixs.inputs[2])
    t.links.new(mixs.outputs[0], out.inputs["Surface"])
    _blended(m)
    m.use_backface_culling = False
    return m


# ------------------------------------------------------------ mesh makers
def _take_mesh(name):
    ob = bpy.context.active_object
    me = ob.data
    me.name = name
    me.shade_smooth()
    me.use_fake_user = True
    bpy.data.objects.remove(ob)
    return me


def mesh_sphere(name, r, seg=24, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=seg, ring_count=rings)
    return _take_mesh(name)


def mesh_disc(name, r):
    bpy.ops.mesh.primitive_circle_add(radius=r, vertices=48, fill_type="NGON")
    return _take_mesh(name)


def mesh_torus(name, major, minor, seg_major=256, seg_minor=24):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     major_segments=seg_major, minor_segments=seg_minor)
    return _take_mesh(name)


# ------------------------------------------------------------------ build
def build(scene):
    rng = random.Random(ARGS.seed)

    # World: near-black background + light volumetric fog for depth
    world = bpy.data.worlds.new("SiegeWorld")
    world.use_nodes = True
    scene.world = world
    wt = world.node_tree
    bgn = wt.nodes["Background"]
    bgn.inputs["Color"].default_value = BG
    bgn.inputs["Strength"].default_value = 1.0
    vol = wt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = 0.012
    vol.inputs["Color"].default_value = (0.55, 0.66, 0.95, 1.0)
    vol.inputs["Anisotropy"].default_value = 0.35
    wt.links.new(vol.outputs[0], wt.nodes["World Output"].inputs["Volume"])

    # Rig: local XY plane is the gate plane, facing the camera (-Y world)
    rig = link_obj(bpy.data.objects.new("GateRig", None))
    rig.rotation_mode = "XYZ"
    for f in range(1, LOOP + 2):
        t = (f - 1) / LOOP
        rig.rotation_euler = (math.radians(90.0 + 1.5 * math.sin(TAU * t)),
                              math.radians(1.2 * math.sin(TAU * t + 1.1)), 0.0)
        rig.keyframe_insert("rotation_euler", frame=f)

    # Gate ring
    ring_mat, sweep_sock = mat_gate_ring()
    ring = new_obj("Gate", mesh_torus("GateMesh", R_GATE, TUBE), ring_mat, rig)
    ring.rotation_euler = (0, 0, 0)
    ring.keyframe_insert("rotation_euler", frame=1)
    ring.rotation_euler = (0, 0, math.radians(30.0))       # 3 dash-periods -> seamless
    ring.keyframe_insert("rotation_euler", frame=LOOP + 1)
    sweep_sock.default_value = 0.0
    sweep_sock.keyframe_insert("default_value", frame=1)
    sweep_sock.default_value = math.radians(330.0)         # + ring spin = one full turn
    sweep_sock.keyframe_insert("default_value", frame=LOOP + 1)

    outer = new_obj("OuterRing", mesh_torus("OuterMesh", R_GATE + 0.42, 0.018, 320, 8),
                    mat_outer_ring(), rig)
    outer.keyframe_insert("rotation_euler", frame=1)
    outer.rotation_euler = (0, 0, math.radians(-22.5))     # 6 dash-periods -> seamless
    outer.keyframe_insert("rotation_euler", frame=LOOP + 1)

    # Core
    core = new_obj("Core", mesh_sphere("CoreMesh", 0.34, 48, 24), mat_core(), rig)
    core_col = mix(BLUE, WHITE, 0.25)
    for f in range(1, LOOP + 2, 3):
        t = (f - 1) / LOOP
        core.color = core_col[:3] + (15.0 + 4.0 * math.sin(2 * TAU * t),)
        core.keyframe_insert("color", frame=f)

    # Lights ---------------------------------------------------------------
    def point_light(name, color, energy, radius, parent=None, loc=(0, 0, 0), shadow=False, volume=1.0):
        ld = bpy.data.lights.new(name, "POINT")
        ld.color = color[:3]
        ld.energy = energy
        ld.shadow_soft_size = radius
        ld.use_shadow = shadow
        ld.volume_factor = volume
        ld.diffuse_factor = 0.5
        ld.specular_factor = 0.8
        ob = link_obj(bpy.data.objects.new(name, ld), parent)
        ob.location = loc
        return ob, ld

    n_ring_lights = 10
    for i in range(n_ring_lights):
        a = TAU * i / n_ring_lights
        point_light(f"GateLight.{i:02d}", EMERALD, 55.0, 0.7, rig,
                    (R_GATE * math.cos(a), R_GATE * math.sin(a), 0.0), volume=1.4)
    point_light("CoreLight", BLUE, 320.0, 0.35, rig, (0, 0, 0), volume=1.2)

    key = bpy.data.lights.new("Key", "AREA")
    key.color = (0.75, 0.82, 1.0)
    key.energy = 900.0
    key.size = 9.0
    key.use_shadow = True
    key.volume_factor = 0.15
    key_ob = link_obj(bpy.data.objects.new("Key", key))
    key_ob.location = (8.0, -9.0, 11.0)
    target = link_obj(bpy.data.objects.new("Target", None))
    target.location = (0.0, 0.0, 0.0)
    c = key_ob.constraints.new("TRACK_TO")
    c.target = target
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"

    flash_lights = []
    for i in range(3):
        _, ld = point_light(f"BreachLight.{i}", RED, 0.0, 0.5, rig, (0, 0, 0), volume=1.6)
        ld.keyframe_insert("energy", frame=1)
        flash_lights.append(ld)

    # Camera ---------------------------------------------------------------
    cam = bpy.data.cameras.new("SiegeCam")
    cam.lens = 35.0
    cam.sensor_width = 36.0
    cam.clip_end = 300.0
    if ARGS.fstop > 0:
        cam.dof.use_dof = True
        cam.dof.focus_object = target
        cam.dof.aperture_fstop = ARGS.fstop
        cam.dof.aperture_blades = 7
    cam_ob = link_obj(bpy.data.objects.new("Camera", cam))
    c = cam_ob.constraints.new("TRACK_TO")
    c.target = target
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    scene.camera = cam_ob
    for f in range(1, LOOP + 2):
        t = (f - 1) / LOOP
        az = math.radians(20.0 + 3.5 * math.sin(TAU * t))
        el = math.radians(8.0 + 1.6 * math.sin(TAU * t + 0.9))
        d = 21.0 + 0.9 * math.sin(TAU * t + 2.2)
        cam_ob.location = (d * math.sin(az) * math.cos(el),
                           -d * math.cos(az) * math.cos(el),
                           d * math.sin(el))
        cam_ob.keyframe_insert("location", frame=f)

    # Shared meshes / materials for the swarm --------------------------------
    m_glow = mat_object_glow("Glow")
    m_disc = mat_impact_disc(0.35)
    m_blob = mat_soft_blob()
    proj_mesh = mesh_sphere("ProjMesh", 0.08, 20, 10)
    spark_mesh = mesh_sphere("SparkMesh", 0.04, 12, 6)
    disc_mesh = mesh_disc("DiscMesh", 0.35)
    flash_mesh = mesh_sphere("FlashMesh", 0.55, 32, 16)

    flashes = []
    for i in range(4):
        fl = new_obj(f"Flash.{i}", flash_mesh, m_blob, rig)
        fl.color = RED[:3] + (0.0,)
        fl.hide_render = True
        fl.keyframe_insert("hide_render", frame=-LOOP)
        flashes.append(fl)

    # Projectiles ----------------------------------------------------------
    A_FLY = 7.0
    ELONG = (2.6, 0.75, 0.75)
    core_events = []
    n_breach = n_block = 0

    for i in range(ARGS.count):
        theta = rng.uniform(0.0, TAU)
        r0 = rng.uniform(7.0, 10.5)
        v = rng.uniform(0.075, 0.11)
        zj = rng.uniform(-0.6, 0.6)
        t0 = 1.0 + rng.uniform(0.0, LOOP)
        T = (r0 - R_HIT) / v
        t_hit = t0 + T
        phase = ((t_hit - 1.0) % LOOP) / LOOP
        breach = rng.random() < (0.27 if phase < 0.5 else 0.08)
        ct, st = math.cos(theta), math.sin(theta)

        def pos(r):
            zf = max(0.0, (r - R_GATE) / (r0 - R_GATE))
            return (r * ct, r * st, zj * zf)

        ob = new_obj(f"Proj.{i:03d}", proj_mesh, m_glow, rig)
        ob.rotation_euler = (0.0, 0.0, theta)
        fly_col = mix(NEUTRAL, RED, 0.5) if breach else NEUTRAL

        # flight path, slight ease-in, sampled every ~4 frames
        n = max(3, int(math.ceil(T / 4.0)))
        for k in range(n + 1):
            u = k / n
            keyed(ob, "location", t0 + u * T, pos(r0 - (r0 - R_HIT) * (u ** 1.12)))

        keyed(ob, "scale", t0, (0.4, 0.2, 0.2))
        keyed(ob, "scale", t0 + 10, ELONG)
        keyed(ob, "color", t0, fly_col[:3] + (0.0,))
        keyed(ob, "color", t0 + 10, fly_col[:3] + (A_FLY,))
        keyed(ob, "color", t_hit - 1, fly_col[:3] + (A_FLY,))

        disc = new_obj(f"Impact.{i:03d}", disc_mesh, m_disc, rig)
        disc.location = (R_GATE * ct, R_GATE * st, 0.0)

        if not breach:
            n_block += 1
            keyed(ob, "scale", t_hit - 2, ELONG)
            keyed(ob, "scale", t_hit, (1.4, 1.5, 1.5))
            keyed(ob, "scale", t_hit + 3, (1.0, 1.3, 1.3))
            keyed(ob, "scale", t_hit + 10, (0.05, 0.05, 0.05))
            keyed(ob, "location", t_hit + 10, pos(R_HIT))
            keyed(ob, "color", t_hit, AMBER[:3] + (36.0,))
            keyed(ob, "color", t_hit + 3, AMBER[:3] + (12.0,))
            keyed(ob, "color", t_hit + 10, AMBER[:3] + (0.0,))
            key_visible(ob, t0, t_hit + 10)

            keyed(disc, "scale", t_hit, (0.25,) * 3)
            keyed(disc, "scale", t_hit + 5, (1.0,) * 3)
            keyed(disc, "scale", t_hit + 13, (1.35,) * 3)
            keyed(disc, "color", t_hit, AMBER[:3] + (10.0,))
            keyed(disc, "color", t_hit + 5, AMBER[:3] + (3.5,))
            keyed(disc, "color", t_hit + 13, AMBER[:3] + (0.0,))
            key_visible(disc, t_hit, t_hit + 13)

            p0 = Vector(pos(R_HIT))
            for k in range(4):
                d = (Vector((ct, st, 0.0)) * rng.uniform(0.35, 1.0)
                     + Vector((-st, ct, 0.0)) * rng.uniform(-1.0, 1.0)
                     + Vector((0.0, 0.0, 1.0)) * rng.uniform(-0.7, 0.7))
                d.normalize()
                dist = rng.uniform(0.45, 1.2)
                dur = rng.uniform(10.0, 18.0)
                sp = new_obj(f"Spark.{i:03d}.{k}", spark_mesh, m_glow, rig)
                for u in (0.0, 0.3, 0.6, 1.0):
                    s = 1.0 - (1.0 - u) ** 2
                    keyed(sp, "location", t_hit + u * dur, tuple(p0 + d * dist * s))
                keyed(sp, "scale", t_hit, (0.3,) * 3)
                keyed(sp, "scale", t_hit + 1.5, (1.0,) * 3)
                keyed(sp, "scale", t_hit + dur, (0.15,) * 3)
                keyed(sp, "color", t_hit, SPARK[:3] + (26.0,))
                keyed(sp, "color", t_hit + dur * 0.5, SPARK[:3] + (8.0,))
                keyed(sp, "color", t_hit + dur, SPARK[:3] + (0.0,))
                key_visible(sp, t_hit, t_hit + dur)
        else:
            n_breach += 1
            t_c = t_hit + (R_HIT - R_CORE) / v
            keyed(ob, "location", t_c, pos(R_CORE))
            keyed(ob, "scale", t_hit - 1, ELONG)
            keyed(ob, "scale", t_hit, (2.0, 1.1, 1.1))
            keyed(ob, "scale", t_hit + 4, ELONG)
            keyed(ob, "scale", t_c - 1, ELONG)
            keyed(ob, "scale", t_c + 1, (0.1,) * 3)
            keyed(ob, "color", t_hit, RED[:3] + (45.0,))
            keyed(ob, "color", t_hit + 4, RED[:3] + (16.0,))
            keyed(ob, "color", t_c - 1, RED[:3] + (16.0,))
            keyed(ob, "color", t_c + 1, RED[:3] + (0.0,))
            key_visible(ob, t0, t_c + 1)

            keyed(disc, "scale", t_hit, (0.2,) * 3)
            keyed(disc, "scale", t_hit + 4, (0.8,) * 3)
            keyed(disc, "scale", t_hit + 9, (1.05,) * 3)
            keyed(disc, "color", t_hit, RED[:3] + (12.0,))
            keyed(disc, "color", t_hit + 4, RED[:3] + (3.0,))
            keyed(disc, "color", t_hit + 9, RED[:3] + (0.0,))
            key_visible(disc, t_hit, t_hit + 9)
            core_events.append(t_c)

    # Breach flashes at the core, round-robin over a small pool so that
    # overlapping events never fight over one object's keyframes.
    core_events.sort()
    for j, t_c in enumerate(core_events):
        fl = flashes[j % len(flashes)]
        keyed(fl, "scale", t_c - 1, (0.2,) * 3)
        keyed(fl, "scale", t_c + 1, (1.0,) * 3)
        keyed(fl, "scale", t_c + 4, (1.6,) * 3)
        keyed(fl, "scale", t_c + 14, (2.4,) * 3)
        keyed(fl, "color", t_c - 1, RED[:3] + (0.0,))
        keyed(fl, "color", t_c + 1, RED[:3] + (40.0,))
        keyed(fl, "color", t_c + 4, RED[:3] + (20.0,))
        keyed(fl, "color", t_c + 14, RED[:3] + (0.0,))
        key_visible(fl, t_c - 1, t_c + 14)
        ld = flash_lights[j % len(flash_lights)]
        keyed(ld, "energy", t_c - 1, 0.0)
        keyed(ld, "energy", t_c + 1, 2200.0)
        keyed(ld, "energy", t_c + 4, 1200.0)
        keyed(ld, "energy", t_c + 14, 0.0)

    print(f"[siege] projectiles={ARGS.count} blocked={n_block} breached={n_breach} "
          f"objects={len(bpy.data.objects)}")


# ------------------------------------------------------------- compositor
def build_compositor(scene, width, height):
    ng = bpy.data.node_groups.new("SiegeComp", "CompositorNodeTree")
    scene.compositing_node_group = ng
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    rl.scene = scene

    glare = ng.nodes.new("CompositorNodeGlare")
    glare.inputs["Type"].default_value = "Bloom"
    glare.inputs["Quality"].default_value = "High"
    sock_in(glare, "Highlights Threshold").default_value = 1.0
    sock_in(glare, "Highlights Smoothness").default_value = 0.15
    glare.inputs["Strength"].default_value = 0.5
    glare.inputs["Size"].default_value = 0.55
    glare.inputs["Saturation"].default_value = 0.95
    ng.links.new(rl.outputs["Image"], glare.inputs["Image"])

    # Vignette: blurred ellipse mask multiplied into the image
    mask = ng.nodes.new("CompositorNodeEllipseMask")
    mask.inputs["Position"].default_value = (0.5, 0.5)
    mask.inputs["Size"].default_value = (1.25, 1.25)
    blur = ng.nodes.new("CompositorNodeBlur")
    blur.inputs["Type"].default_value = "Gaussian"
    blur.inputs["Size"].default_value = (int(width * 0.18), int(width * 0.18))
    ng.links.new(mask.outputs[0], blur.inputs["Image"])
    vig = ng.nodes.new("ShaderNodeMapRange")
    vig.interpolation_type = "SMOOTHSTEP"
    vig.inputs["From Min"].default_value = 0.0
    vig.inputs["From Max"].default_value = 1.0
    vig.inputs["To Min"].default_value = 0.48
    vig.inputs["To Max"].default_value = 1.0
    ng.links.new(blur.outputs[0], vig.inputs["Value"])
    mul = ng.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    sock_in(mul, "Factor_Float").default_value = 1.0
    ng.links.new(glare.outputs["Image"], sock_in(mul, "A_Color"))
    ng.links.new(vig.outputs["Result"], sock_in(mul, "B_Color"))

    out = ng.nodes.new("NodeGroupOutput")
    ng.links.new(sock_out(mul, "Result_Color"), out.inputs[0])

    scene.render.use_compositing = True
    scene.render.compositor_device = "GPU"


# ------------------------------------------------------------ render setup
def setup_render(scene, width, height, samples):
    r = scene.render
    r.engine = "BLENDER_EEVEE"
    r.resolution_x, r.resolution_y = width, height
    r.resolution_percentage = 100
    r.fps = FPS
    r.film_transparent = False
    r.use_motion_blur = False
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.color_depth = "8"
    r.image_settings.compression = 25

    ev = scene.eevee
    ev.taa_render_samples = samples
    ev.use_shadows = True
    ev.shadow_ray_count = 1
    ev.shadow_step_count = 3
    ev.use_raytracing = True
    ev.use_volumetric_shadows = False
    ev.volumetric_tile_size = "4"
    ev.volumetric_samples = 96
    ev.volumetric_start = 1.0
    ev.volumetric_end = 60.0
    ev.use_fast_gi = False

    vs = scene.view_settings
    scene.display_settings.display_device = "sRGB"
    vs.view_transform = "AgX"
    try:
        vs.look = "AgX - Punchy"
    except TypeError:
        pass
    vs.exposure = 0.0
    vs.gamma = 1.0


_timing = {"last": None, "times": []}


def _on_frame_written(*_args):
    now = time.time()
    if _timing["last"] is not None:
        dt = now - _timing["last"]
        _timing["times"].append(dt)
        print(f"[siege] frame {bpy.context.scene.frame_current} rendered in {dt:.2f}s", flush=True)
    _timing["last"] = now


def main():
    reset_blender()
    scene = bpy.context.scene
    width, height = ARGS.res
    out = os.path.abspath(ARGS.out)
    os.makedirs(out, exist_ok=True)

    scene.frame_start = 1
    scene.frame_end = LOOP
    scene.frame_current = 1
    build(scene)
    samples = ARGS.samples or (128 if ARGS.hero else 48)
    setup_render(scene, width, height, samples)
    build_compositor(scene, width, height)

    if ARGS.save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(ARGS.save_blend))
        print(f"[siege] saved {ARGS.save_blend}")
    if ARGS.no_render:
        return

    if ARGS.hero:
        scene.frame_set(ARGS.hero_frame)
        scene.render.filepath = os.path.join(out, "siege_hero.png")
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[siege] hero {width}x{height} @ {samples} spp in {time.time() - t0:.1f}s "
              f"-> {scene.render.filepath}")
        return

    scene.frame_start = ARGS.start
    scene.frame_end = ARGS.end or LOOP
    frames_dir = os.path.join(out, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    scene.render.filepath = os.path.join(frames_dir, "frame_")
    bpy.app.handlers.render_write.append(_on_frame_written)
    _timing["last"] = time.time()
    t_all = time.time()
    bpy.ops.render.render(animation=True)
    n = scene.frame_end - scene.frame_start + 1
    total = time.time() - t_all
    print(f"[siege] rendered {n} frames at {width}x{height} @ {samples} spp in {total:.1f}s "
          f"({total / max(n, 1):.2f}s/frame)")


main()
