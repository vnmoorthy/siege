import bpy, math
s = bpy.context.scene
LOOP = 180
def snap(f):
    s.frame_set(f)
    d = {}
    for ob in bpy.data.objects:
        m = ob.matrix_world
        d[ob.name] = (tuple(round(x, 5) for row in m for x in row), tuple(round(c, 4) for c in ob.color), ob.hide_render)
    for l in bpy.data.lights: d["L:" + l.name] = round(l.energy, 4)
    nt = bpy.data.materials["GateRing"].node_tree
    d["sweep"] = round(nt.nodes["Sweep"].outputs[0].default_value % math.tau, 5)
    return d
a, b = snap(1), snap(1 + LOOP)
bad = [k for k in a if a[k] != b[k]]
print("CHECK objects:", len(a), "mismatches:", len(bad))
for k in bad[:12]: print("  ", k, a[k] if not isinstance(a[k], tuple) else (a[k][1], a[k][2], a[k][0][:4]), "|", b[k] if not isinstance(b[k], tuple) else (b[k][1], b[k][2], b[k][0][:4]))
# also mid-loop wrap sanity: frame 91 vs 271
a, b = snap(91), snap(91 + LOOP)
print("CHECK frame 91 vs 271 mismatches:", len([k for k in a if a[k] != b[k]]))
