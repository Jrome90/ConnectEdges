import bpy
import bmesh
from bmesh.types import *
from mathutils import Vector, Matrix


def bmesh_face_loop_walker(face: BMFace):
    # Get the first loop
    next_loop = face.loops[0]
    test_condition = True
    while test_condition:
        yield next_loop

        next_loop = next_loop.link_loop_next
        test_condition = next_loop.index != face.loops[0].index


def bmesh_subdivide_edge(bm: BMesh, edge: BMEdge, n=1):
    ret = []
    for i in range(0, n):
        percent = 1.0 / float((n + 1 - i))
        ret.extend(bmesh.utils.edge_split(edge, edge.verts[0], percent))

    bm.verts.index_update()
    return ret


def bmesh_scale(bm: BMesh, vec, space_mat: Matrix, verts):
    scale_mat = Matrix()
    scale_mat[0][0] = vec[0]
    scale_mat[1][1] = vec[1]
    scale_mat[2][2] = vec[2]

    space_mat_inv = space_mat.inverted()
    mat = space_mat_inv @ scale_mat @ space_mat

    bm.verts.ensure_lookup_table()
    for vert_idx in verts:
        bm_vert = bm.verts[vert_idx]

        bm_vert.co = mat @ bm_vert.co

# Credit: https://gist.github.com/zeffii/71862f5b1cad1bf1d2c1
def scale_verts_along_edge(bm, verts, start, end, factor):
    origin = (start + end) * 0.5
    mat = Matrix.Translation((-origin[0], -origin[1], -origin[2]))

    bmesh_scale(bm, [factor, factor, factor], mat, verts)

def clamp(minvalue, value, maxvalue):
    return max(minvalue, min(value, maxvalue))


def ensure(mesh: BMesh):
    mesh.edges.ensure_lookup_table()
    mesh.verts.ensure_lookup_table()
    mesh.faces.ensure_lookup_table()


def get_perc_along(vec_a: Vector, vec_b: Vector, vec_c: Vector) -> float:
    """ Calculate the percent along a vector

        Projects the vector ac onto the vector ab and then returns as a float the percentage along ab that ac is.

        Args:
            vec_a: Normalized vector.
            vec_b: Normalized vector.
            vec_c: Normalized vector.

        Returns:
            The percentage along the vector ab.
    """

    ab: Vector = vec_b - vec_a
    ac: Vector = vec_c - vec_a

    return ab.dot(ac) / ab.length_squared  # Why does dot() return a vector?

# Credit: https://stackoverflow.com/a/48339861
class Event(object):
    def __init__(self):
        self.callbacks = []

    def notify(self, *args, **kwargs):
        for callback in self.callbacks:
            callback(*args, **kwargs)

    def register(self, callback):
        self.callbacks.append(callback)
        return callback


def get_addon_prefs(context):
    preferences = context.preferences
    return preferences.addons[__package__].preferences