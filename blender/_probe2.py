import bpy
s = bpy.context.scene
# view transform
print("cur view_transform:", s.view_settings.view_transform, "display:", s.display_settings.display_device)
for vt in ("AgX", "Filmic", "Khronos PBR Neutral", "Standard"):
    try:
        s.view_settings.view_transform = vt
        print("set VT ok:", vt, "-> looks:", [e.identifier for e in s.view_settings.bl_rna.properties['look'].enum_items])
    except Exception as e:
        print("VT fail", vt, e)
# compositor node group
ng = bpy.data.node_groups.new("Comp", "CompositorNodeTree")
s.compositing_node_group = ng
print("comp tree assigned:", s.compositing_node_group.name)
gl = ng.nodes.new("CompositorNodeGlare")
print("glare inputs:", [(i.name, i.identifier, getattr(i, 'default_value', None) if i.type != 'RGBA' else 'rgba') for i in gl.inputs])
print("glare outputs:", [o.name for o in gl.outputs])
# glare type enum socket
for i in gl.inputs:
    if i.type == 'MENU' or 'Type' in i.name:
        try:
            print("menu socket", i.name, i.type, i.default_value, [e.identifier for e in i.bl_rna.properties['default_value'].enum_items])
        except Exception as e:
            print("menu err", i.name, e)
# other node types
for t in ("CompositorNodeRLayers","CompositorNodeComposite","CompositorNodeViewer","CompositorNodeLensdist","CompositorNodeColorBalance","CompositorNodeMixRGB","CompositorNodeCurveRGB","CompositorNodeEllipseMask","CompositorNodeBlur","CompositorNodeMath","CompositorNodeColorCorrection","CompositorNodeHueSat","CompositorNodeGroup","CompositorNodeOutputFile","CompositorNodeVignette","CompositorNodeFilmGrain","CompositorNodeChromaticAberration","CompositorNodeGamma","CompositorNodeBrightContrast"):
    print(t, hasattr(bpy.types, t))
print("compositor_device:", [e.identifier for e in s.render.bl_rna.properties['compositor_device'].enum_items], s.render.compositor_device)
print("compositor_precision:", [e.identifier for e in s.render.bl_rna.properties['compositor_precision'].enum_items])
print("rt method:", [e.identifier for e in s.eevee.bl_rna.properties['ray_tracing_method'].enum_items])
print("vol dist:", s.eevee.volumetric_tile_size, s.eevee.volumetric_samples)
# World volume
w = bpy.data.worlds[0] if bpy.data.worlds else bpy.data.worlds.new("W")
w.use_nodes = True
print("world nodes:", [n.bl_idname for n in w.node_tree.nodes])
# Principled volume
m = bpy.data.materials.new("M"); m.use_nodes = True
print("mat nodes:", [n.bl_idname for n in m.node_tree.nodes])
bsdf = m.node_tree.nodes.get("Principled BSDF")
print("bsdf inputs:", [i.name for i in bsdf.inputs])
print("mat attrs:", [a for a in dir(m) if 'blend' in a or 'shadow' in a or 'surface' in a or 'volume' in a or 'transparen' in a or 'render_method' in a])
try:
    print("surface_render_method:", [e.identifier for e in m.bl_rna.properties['surface_render_method'].enum_items])
except Exception as e: print(e)
# Camera dof
c = bpy.data.cameras.new("C"); print("dof attrs:", [a for a in dir(c.dof) if not a.startswith('_')])
# light
print("light types:", [e.identifier for e in bpy.types.Light.bl_rna.properties['type'].enum_items])
l = bpy.data.lights.new("L","POINT"); print("light attrs:", [a for a in dir(l) if not a.startswith('_') and 'volume' in a or 'radius' in a or 'shadow_soft' in a or 'energy' in a])
# Geometry nodes availability for instancing? We'll keyframe instances directly.
print("bloom-like: glare done")
# Check EEVEE 'Bloom' glare type
