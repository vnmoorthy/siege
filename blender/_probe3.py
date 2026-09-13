import bpy
s = bpy.context.scene
o = bpy.data.objects.new("O", None); s.collection.objects.link(o)
o.color = (5.0, 3.0, 0.5, 2.0); print("obj.color readback:", tuple(o.color))
o.keyframe_insert("color", frame=1); print("color kf ok")
print("color prop hard range:", bpy.types.Object.bl_rna.properties['color'].hard_min, bpy.types.Object.bl_rna.properties['color'].hard_max)
ng = bpy.data.node_groups.new("Comp", "CompositorNodeTree"); s.compositing_node_group = ng
for t in ("ShaderNodeMix","ShaderNodeMath","ShaderNodeValToRGB","ShaderNodeRGBCurve","NodeGroupOutput","NodeGroupInput","ShaderNodeMapRange","ShaderNodeSeparateColor","ShaderNodeCombineColor","CompositorNodeCurveRGB","ShaderNodeValue","ShaderNodeRGB","CompositorNodeTonemap","CompositorNodeDilateErode","CompositorNodeScale","CompositorNodeTranslate","CompositorNodeTexture","ShaderNodeTexNoise","CompositorNodeSetAlpha","CompositorNodeAlphaOver","CompositorNodeBokehBlur","CompositorNodeDBlur","CompositorNodeDefocus"):
    try:
        n = ng.nodes.new(t); print("OK", t, [i.name for i in n.inputs][:8])
    except Exception as e:
        print("NO", t, str(e)[:60])
print("interface items:", [i.name for i in ng.interface.items_tree])
try:
    ng.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor'); print("iface out ok:", [ (i.name, i.in_out) for i in ng.interface.items_tree])
except Exception as e: print("iface err", e)
gl = ng.nodes.new("CompositorNodeGlare")
for v in ("Bloom","BLOOM","Fog Glow","FOG_GLOW"):
    try: gl.inputs["Type"].default_value = v; print("glare type set:", v, "->", gl.inputs["Type"].default_value)
    except Exception as e: print("glare type fail", v, str(e)[:80])
for v in ("High","HIGH"):
    try: gl.inputs["Quality"].default_value = v; print("quality set:", v)
    except Exception as e: print("quality fail", v, str(e)[:80])
for lk in ("AgX - Punchy","Punchy","AgX - Medium High Contrast","Medium High Contrast"):
    try: s.view_settings.look = lk; print("look ok:", lk, "->", s.view_settings.look)
    except Exception as e: print("look fail", lk, str(e)[:60])
# torus op headless
try:
    bpy.ops.mesh.primitive_torus_add(major_radius=3, minor_radius=0.07); print("torus op ok", bpy.context.active_object.name)
except Exception as e: print("torus op fail", e)
# world volume
w = bpy.data.worlds.new("W"); w.use_nodes = True; s.world = w
pv = w.node_tree.nodes.new("ShaderNodeVolumePrincipled"); print("pv inputs:", [i.name for i in pv.inputs])
out = w.node_tree.nodes["World Output"]; print("world out inputs:", [i.name for i in out.inputs])
# emission node / object info
m = bpy.data.materials.new("M"); m.use_nodes = True
oi = m.node_tree.nodes.new("ShaderNodeObjectInfo"); print("objinfo outs:", [o_.name for o_ in oi.outputs])
em = m.node_tree.nodes.new("ShaderNodeEmission"); print("emission ins:", [i.name for i in em.inputs])
print("math ops sample:", [e.identifier for e in bpy.types.ShaderNodeMath.bl_rna.properties['operation'].enum_items if e.identifier in ('ARCTAN2','FRACT','SMOOTH_MIN','WRAP','PINGPONG','SMOOTHSTEP')])
print("maprange types:", [e.identifier for e in bpy.types.ShaderNodeMapRange.bl_rna.properties['interpolation_type'].enum_items])
print("render attrs:", [a for a in dir(s.render) if 'motion' in a or 'film' in a or 'threads' in a])
print("image settings:", s.render.image_settings.color_mode, s.render.image_settings.color_depth)
print("ffmpeg encode:", hasattr(s.render, 'ffmpeg'))
