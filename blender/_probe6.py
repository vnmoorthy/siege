import bpy, time
s = bpy.context.scene
ob = bpy.data.objects.new("O", None); s.collection.objects.link(ob)
act = bpy.data.actions.new("A")
print("action attrs:", [a for a in dir(act) if a in ('slots','layers','fcurves','is_action_layered','is_action_legacy','fcurve_ensure_for_datablock')])
slot = act.slots.new('OBJECT', "O")
layer = act.layers.new("L")
strip = layer.strips.new(type='KEYFRAME')
cb = strip.channelbag(slot, ensure=True)
fc = cb.fcurves.new("location", index=0)
fc.keyframe_points.add(3)
fc.keyframe_points.foreach_set("co", [1,0, 10,5, 20,0])
try:
    fc.keyframe_points.foreach_set("interpolation", [1,1,1]); print("interp foreach ok")
except Exception as e: print("interp foreach fail", e)
for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
fc.update()
ad = ob.animation_data_create(); ad.action = act; ad.action_slot = slot
s.frame_set(10); print("loc at 10:", ob.location.x)
s.frame_set(15); print("loc at 15:", ob.location.x)
# bool channel
fc2 = cb.fcurves.new("hide_render", index=0); fc2.keyframe_points.add(2); fc2.keyframe_points.foreach_set("co", [5,1, 12,0])
for kp in fc2.keyframe_points: kp.interpolation = 'CONSTANT'
fc2.update(); s.frame_set(8); print("hide at 8:", ob.hide_render); s.frame_set(13); print("hide at 13:", ob.hide_render)
# color channel
fc3 = cb.fcurves.new("color", index=3); fc3.keyframe_points.add(2); fc3.keyframe_points.foreach_set("co", [1,0, 10,7]); fc3.update()
s.frame_set(10); print("color a at 10:", ob.color[3])
# light data
ld = bpy.data.lights.new("L", "POINT"); act2 = bpy.data.actions.new("A2"); sl2 = act2.slots.new('LIGHT', "L"); cb2 = act2.layers.new("L").strips.new(type='KEYFRAME').channelbag(sl2, ensure=True)
f = cb2.fcurves.new("energy"); f.keyframe_points.add(2); f.keyframe_points.foreach_set("co",[1,0,10,100]); f.update(); ad2 = ld.animation_data_create(); ad2.action = act2; ad2.action_slot = sl2
s.frame_set(10); print("energy at 10:", ld.energy)
# node socket
m = bpy.data.materials.new("M"); m.use_nodes = True; v = m.node_tree.nodes.new("ShaderNodeValue")
act3 = bpy.data.actions.new("A3"); sl3 = act3.slots.new('NODETREE', "NT"); cb3 = act3.layers.new("L").strips.new(type='KEYFRAME').channelbag(sl3, ensure=True)
f = cb3.fcurves.new(f'nodes["{v.name}"].outputs[0].default_value'); f.keyframe_points.add(2); f.keyframe_points.foreach_set("co",[1,0,181,5.76]); f.update()
ad3 = m.node_tree.animation_data_create(); ad3.action = act3; ad3.action_slot = sl3
s.frame_set(91); print("sweep at 91:", v.outputs[0].default_value)
# speed test
t=time.time()
for i in range(300):
    o = bpy.data.objects.new(f"P{i}", None); s.collection.objects.link(o)
    a = bpy.data.actions.new(f"P{i}"); sl = a.slots.new('OBJECT', o.name); c = a.layers.new("L").strips.new(type='KEYFRAME').channelbag(sl, ensure=True)
    for path, idx, n in (("location",0,60),("location",1,60),("location",2,60),("scale",0,15),("scale",1,15),("scale",2,15),("color",0,18),("color",1,18),("color",2,18),("color",3,18),("hide_render",0,6)):
        f = c.fcurves.new(path, index=idx); f.keyframe_points.add(n); f.keyframe_points.foreach_set("co", [float(x) for k in range(n) for x in (k, k)])
        for kp in f.keyframe_points: kp.interpolation = 'LINEAR'
        f.update()
    ad = o.animation_data_create(); ad.action = a; ad.action_slot = sl
print("300 objs direct fcurves:", round(time.time()-t,2), "s")
