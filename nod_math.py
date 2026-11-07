import re
from mathutils import Matrix, Vector
from .vector4 import Vector4

_BONE_INDEX_RE = re.compile(r"^Bone_(\d+)$")


def order_blender_bones(armature_obj):
    """Return armature bones in NOD index order (Bone_000..N-1 or topological pre-order)."""
    bones = list(armature_obj.data.bones)
    if not bones:
        return []

    indexed = {}
    all_standard = True
    for b in bones:
        m = _BONE_INDEX_RE.match(b.name)
        if m:
            idx = int(m.group(1))
            indexed[idx] = b
        else:
            all_standard = False
            break

    if all_standard and set(indexed.keys()) == set(range(len(bones))):
        ordered_std = [indexed[i] for i in range(len(bones))]
        name_to_idx = {b.name: i for i, b in enumerate(ordered_std)}
        topo_valid = (
            ordered_std[0].parent is None
            and all(
                b.parent is None or name_to_idx.get(b.parent.name, -1) < i
                for i, b in enumerate(ordered_std)
            )
        )
        if topo_valid:
            return ordered_std

    ordered = []
    visited = set()

    def _visit(b):
        if b.name in visited:
            return
        visited.add(b.name)
        ordered.append(b)
        for child in b.children:
            _visit(child)

    roots = [b for b in bones if b.parent is None]
    for r in roots:
        _visit(r)
    for b in bones:
        _visit(b)
    return ordered


def nod_inverse_bind_matrix(nod_bone) -> Matrix:
    """Convert NOD's serialized row-vector Matrix43 to a Blender matrix."""
    values = []
    for row in nod_bone.rest_matrix_inverse:
        values.extend((row.x, row.y, row.z, row.w))
    return Matrix((
        (values[0], values[3], values[6], values[9]),
        (values[1], values[4], values[7], values[10]),
        (values[2], values[5], values[8], values[11]),
        (0.0, 0.0, 0.0, 1.0),
    ))


def matrix_to_nod_rest_matrix_inverse(inv_bind_matrix: Matrix) -> list[Vector4]:
    """Convert a Blender 4x4 inverse bind matrix to NOD's 3x Vector4 (row-vector Matrix43)."""
    values = (
        float(inv_bind_matrix[0][0]), float(inv_bind_matrix[1][0]), float(inv_bind_matrix[2][0]),
        float(inv_bind_matrix[0][1]), float(inv_bind_matrix[1][1]), float(inv_bind_matrix[2][1]),
        float(inv_bind_matrix[0][2]), float(inv_bind_matrix[1][2]), float(inv_bind_matrix[2][2]),
        float(inv_bind_matrix[0][3]), float(inv_bind_matrix[1][3]), float(inv_bind_matrix[2][3]),
    )
    return [
        Vector4(values[0], values[1], values[2], values[3]),
        Vector4(values[4], values[5], values[6], values[7]),
        Vector4(values[8], values[9], values[10], values[11]),
    ]


def nod_bind_world_matrix(nod_bone) -> Matrix:
    """Compute the world-space bind matrix for a NOD bone."""
    return nod_inverse_bind_matrix(nod_bone).inverted_safe()


def nod_bind_world_position(nod_bone) -> Vector:
    """Compute the world-space bind position for a NOD bone."""
    return nod_bind_world_matrix(nod_bone).translation
