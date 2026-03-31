# bonsai_tessellate.mojo -- SIMD-accelerated tessellation for IFC geometry
#
# Produces interleaved vertex data [x, y, z, nx, ny, nz, ...] (6 floats/vertex)
# and triangle index arrays [i0, i1, i2, ...] (3 indices/triangle).
# Winding order: counter-clockwise (Three.js / WebGPU convention).
#
# Mojo 0.25.6 on Apple M5 ARM NEON.

from memory import UnsafePointer
from math import sin, cos, sqrt, atan2, pi
from time import perf_counter_ns

# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@fieldwise_init
struct TessResult(Copyable, Movable):
    """Holds tessellated mesh data. Caller must free vertices and indices."""

    var vertices: UnsafePointer[Float32]  # interleaved [x,y,z,nx,ny,nz]*N
    var indices: UnsafePointer[UInt32]  # triangle indices
    var vertex_count: Int  # number of vertices (each = 6 floats)
    var index_count: Int  # number of indices  (each 3 = 1 triangle)

    fn free(mut self):
        self.vertices.free()
        self.indices.free()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

alias FLOATS_PER_VERTEX: Int = 6  # x y z nx ny nz


fn _set_vertex(
    verts: UnsafePointer[Float32],
    idx: Int,
    x: Float32,
    y: Float32,
    z: Float32,
    nx: Float32,
    ny: Float32,
    nz: Float32,
):
    var base = idx * FLOATS_PER_VERTEX
    verts[base] = x
    verts[base + 1] = y
    verts[base + 2] = z
    verts[base + 3] = nx
    verts[base + 4] = ny
    verts[base + 5] = nz


fn _set_triangle(
    idxs: UnsafePointer[UInt32], tri: Int, a: UInt32, b: UInt32, c: UInt32
):
    var base = tri * 3
    idxs[base] = a
    idxs[base + 1] = b
    idxs[base + 2] = c


fn _set_quad_ccw(
    idxs: UnsafePointer[UInt32], tri_start: Int, a: UInt32, b: UInt32, c: UInt32, d: UInt32
):
    """Two CCW triangles forming a quad: (a,b,c) and (a,c,d)."""
    _set_triangle(idxs, tri_start, a, b, c)
    _set_triangle(idxs, tri_start + 1, a, c, d)


# ---------------------------------------------------------------------------
# tessellate_box  -- the fundamental primitive
# ---------------------------------------------------------------------------
# A box centered at its local origin offset by (origin_x, origin_y, origin_z),
# with dimensions length (X) x width (Y) x height (Z), rotated rotation_deg
# about the Z axis.
#
# 24 vertices (4 per face for flat-shading normals), 12 triangles (36 indices).
# ---------------------------------------------------------------------------


fn tessellate_box(
    origin_x: Float32,
    origin_y: Float32,
    origin_z: Float32,
    length: Float32,
    width: Float32,
    height: Float32,
    rotation_deg: Float32,
) -> TessResult:
    alias V_COUNT = 24  # 6 faces x 4 verts
    alias I_COUNT = 36  # 6 faces x 2 tris x 3 indices

    var verts = UnsafePointer[Float32].alloc(V_COUNT * FLOATS_PER_VERTEX)
    var idxs = UnsafePointer[UInt32].alloc(I_COUNT)

    var angle = rotation_deg * Float32(pi) / 180.0
    var ca = cos(angle)
    var sa = sin(angle)

    # Local-space box corners before rotation:
    # The box spans [0, length] x [0, width] x [0, height] in local space.
    # (matches IFC convention: origin at min corner, extrusion along +Z)
    var lx = length
    var ly = width
    var lz = height

    # 8 corner positions in local space (before rotation + translation):
    #   0: (0,  0,  0)      4: (0,  0,  lz)
    #   1: (lx, 0,  0)      5: (lx, 0,  lz)
    #   2: (lx, ly, 0)      6: (lx, ly, lz)
    #   3: (0,  ly, 0)      7: (0,  ly, lz)

    # We store the 8 rotated+translated corners, then assign to faces.
    var cx = UnsafePointer[Float32].alloc(8)
    var cy = UnsafePointer[Float32].alloc(8)
    var cz = UnsafePointer[Float32].alloc(8)

    # Local corner coordinates
    var local_x = SIMD[DType.float32, 8](0, lx, lx, 0, 0, lx, lx, 0)
    var local_y = SIMD[DType.float32, 8](0, 0, ly, ly, 0, 0, ly, ly)
    var local_z = SIMD[DType.float32, 8](0, 0, 0, 0, lz, lz, lz, lz)

    # Apply rotation about Z and translate -- fully vectorized over 8 corners
    var rotated_x = local_x * ca - local_y * sa + origin_x
    var rotated_y = local_x * sa + local_y * ca + origin_y
    var translated_z = local_z + origin_z

    # Store to arrays for per-vertex access
    cx.store(0, rotated_x)
    cy.store(0, rotated_y)
    cz.store(0, translated_z)

    # Rotated normal directions (6 face normals)
    # +Z face normal: (0,0,1), -Z: (0,0,-1) -- unaffected by Z rotation
    # +X local: (ca, sa, 0),  -X: (-ca, -sa, 0)
    # +Y local: (-sa, ca, 0), -Y: (sa, -ca, 0)
    var n_px_x = ca
    var n_px_y = sa
    var n_py_x = -sa
    var n_py_y = ca

    # Face 0: -Z (bottom): corners 0,3,2,1  normal (0,0,-1)
    _set_vertex(verts, 0, cx[0], cy[0], cz[0], 0, 0, -1)
    _set_vertex(verts, 1, cx[3], cy[3], cz[3], 0, 0, -1)
    _set_vertex(verts, 2, cx[2], cy[2], cz[2], 0, 0, -1)
    _set_vertex(verts, 3, cx[1], cy[1], cz[1], 0, 0, -1)
    _set_quad_ccw(idxs, 0, 0, 1, 2, 3)

    # Face 1: +Z (top): corners 4,5,6,7  normal (0,0,+1)
    _set_vertex(verts, 4, cx[4], cy[4], cz[4], 0, 0, 1)
    _set_vertex(verts, 5, cx[5], cy[5], cz[5], 0, 0, 1)
    _set_vertex(verts, 6, cx[6], cy[6], cz[6], 0, 0, 1)
    _set_vertex(verts, 7, cx[7], cy[7], cz[7], 0, 0, 1)
    _set_quad_ccw(idxs, 2, 4, 5, 6, 7)

    # Face 2: -Y (front): corners 0,1,5,4  normal (sa, -ca, 0) = -Y rotated
    _set_vertex(verts, 8, cx[0], cy[0], cz[0], n_py_x * -1, n_py_y * -1, 0)
    _set_vertex(verts, 9, cx[1], cy[1], cz[1], n_py_x * -1, n_py_y * -1, 0)
    _set_vertex(verts, 10, cx[5], cy[5], cz[5], n_py_x * -1, n_py_y * -1, 0)
    _set_vertex(verts, 11, cx[4], cy[4], cz[4], n_py_x * -1, n_py_y * -1, 0)
    _set_quad_ccw(idxs, 4, 8, 9, 10, 11)

    # Face 3: +Y (back): corners 3,7,6,2  normal (-sa, ca, 0) = +Y rotated
    _set_vertex(verts, 12, cx[3], cy[3], cz[3], n_py_x, n_py_y, 0)
    _set_vertex(verts, 13, cx[7], cy[7], cz[7], n_py_x, n_py_y, 0)
    _set_vertex(verts, 14, cx[6], cy[6], cz[6], n_py_x, n_py_y, 0)
    _set_vertex(verts, 15, cx[2], cy[2], cz[2], n_py_x, n_py_y, 0)
    _set_quad_ccw(idxs, 6, 12, 13, 14, 15)

    # Face 4: -X (left): corners 0,4,7,3  normal (-ca, -sa, 0) = -X rotated
    _set_vertex(verts, 16, cx[0], cy[0], cz[0], -n_px_x, -n_px_y, 0)
    _set_vertex(verts, 17, cx[4], cy[4], cz[4], -n_px_x, -n_px_y, 0)
    _set_vertex(verts, 18, cx[7], cy[7], cz[7], -n_px_x, -n_px_y, 0)
    _set_vertex(verts, 19, cx[3], cy[3], cz[3], -n_px_x, -n_px_y, 0)
    _set_quad_ccw(idxs, 8, 16, 17, 18, 19)

    # Face 5: +X (right): corners 1,2,6,5  normal (ca, sa, 0) = +X rotated
    _set_vertex(verts, 20, cx[1], cy[1], cz[1], n_px_x, n_px_y, 0)
    _set_vertex(verts, 21, cx[2], cy[2], cz[2], n_px_x, n_px_y, 0)
    _set_vertex(verts, 22, cx[6], cy[6], cz[6], n_px_x, n_px_y, 0)
    _set_vertex(verts, 23, cx[5], cy[5], cz[5], n_px_x, n_px_y, 0)
    _set_quad_ccw(idxs, 10, 20, 21, 22, 23)

    cx.free()
    cy.free()
    cz.free()

    return TessResult(verts, idxs, V_COUNT, I_COUNT)


# ---------------------------------------------------------------------------
# tessellate_wall
# ---------------------------------------------------------------------------
# A wall defined by start/end points, base_z, height, thickness.
# The wall centerline runs from (start_x, start_y) to (end_x, end_y).
# Thickness is applied symmetrically about the centerline in the perpendicular
# direction (matching IFC wall representation convention).
# ---------------------------------------------------------------------------


fn tessellate_wall(
    start_x: Float32,
    start_y: Float32,
    end_x: Float32,
    end_y: Float32,
    base_z: Float32,
    height: Float32,
    thickness: Float32,
) -> TessResult:
    var dx = end_x - start_x
    var dy = end_y - start_y
    var wall_length = sqrt(dx * dx + dy * dy)

    # Wall direction angle
    var angle = atan2(dy, dx)

    # The wall representation in IFC places the wall along +X with thickness
    # along +Y centered on the origin. So origin is at start, rotated by angle.
    # The wall box: length along X, thickness along Y (centered), height along Z.
    # To center thickness: shift origin by -thickness/2 in local Y.
    var half_t = thickness * 0.5
    # Shift origin in world coords: perpendicular to wall direction
    var perp_x = -sin(angle) * (-half_t)  # local -Y direction in world X
    var perp_y = cos(angle) * (-half_t)  # local -Y direction in world Y

    var origin_x = start_x + perp_x
    var origin_y = start_y + perp_y

    # Convert angle to degrees for tessellate_box
    var rot_deg = angle * 180.0 / Float32(pi)

    return tessellate_box(
        origin_x, origin_y, base_z,
        wall_length, thickness, height,
        rot_deg,
    )


# ---------------------------------------------------------------------------
# tessellate_slab
# ---------------------------------------------------------------------------
# A flat rectangular slab at position (x, y, z) with length x width x thickness.
# This is just a thin box.
# ---------------------------------------------------------------------------


fn tessellate_slab(
    x: Float32,
    y: Float32,
    z: Float32,
    length: Float32,
    width: Float32,
    thickness: Float32,
    rotation_deg: Float32,
) -> TessResult:
    return tessellate_box(x, y, z, length, width, thickness, rotation_deg)


# ---------------------------------------------------------------------------
# tessellate_column
# ---------------------------------------------------------------------------
# A vertical column at (x, y, base_z) centered on its profile.
# Width (X) x Depth (Y) x Height (Z). Profile is centered (IFC convention
# for IfcRectangleProfileDef).
# ---------------------------------------------------------------------------


fn tessellate_column(
    x: Float32,
    y: Float32,
    base_z: Float32,
    col_width: Float32,
    depth: Float32,
    height: Float32,
    rotation_deg: Float32,
) -> TessResult:
    # IFC columns use a centered rectangular profile extruded upward.
    # Shift origin so that the box min corner is at (-w/2, -d/2) in local space.
    var angle = rotation_deg * Float32(pi) / 180.0
    var ca = cos(angle)
    var sa = sin(angle)
    var hw = col_width * 0.5
    var hd = depth * 0.5

    # Local offset (-hw, -hd) rotated to world
    var ox = x + (-hw * ca - (-hd) * sa)
    var oy = y + (-hw * sa + (-hd) * ca)

    return tessellate_box(ox, oy, base_z, col_width, depth, height, rotation_deg)


# ---------------------------------------------------------------------------
# tessellate_beam
# ---------------------------------------------------------------------------
# A beam from (start_x, start_y, start_z) to (end_x, end_y, end_z) with
# a rectangular cross section of width x depth, centered on the beam axis.
# The beam axis is the extrusion direction.
# ---------------------------------------------------------------------------


fn tessellate_beam(
    start_x: Float32,
    start_y: Float32,
    start_z: Float32,
    end_x: Float32,
    end_y: Float32,
    end_z: Float32,
    beam_width: Float32,
    beam_depth: Float32,
) -> TessResult:
    # For a general 3D beam, we compute local axes exactly like _member_transform
    # in ifc_author.py: local Z = beam direction, then derive local X and Y.
    # However, since most beams are horizontal (same start_z, end_z), we
    # handle that common case optimally.
    #
    # For the general case, we compute all 8 corners manually using the
    # member transform matrix.

    var dx = end_x - start_x
    var dy = end_y - start_y
    var dz = end_z - start_z
    var beam_length = sqrt(dx * dx + dy * dy + dz * dz)

    if beam_length < 1e-9:
        # Degenerate beam -- return empty mesh
        var verts = UnsafePointer[Float32].alloc(0)
        var idxs = UnsafePointer[UInt32].alloc(0)
        return TessResult(verts, idxs, 0, 0)

    # Beam direction (normalized)
    var inv_len = 1.0 / beam_length
    var dir_x = dx * inv_len
    var dir_y = dy * inv_len
    var dir_z = dz * inv_len

    # Reference vector for cross product (same logic as ifc_author._member_transform)
    var ref_x: Float32
    var ref_y: Float32
    var ref_z: Float32

    # If beam is nearly vertical, use Y as reference instead of Z
    var dot_with_z = dir_z  # dot(dir, (0,0,1)) = dir_z
    if dot_with_z > 0.999 or dot_with_z < -0.999:
        ref_x = 0.0
        ref_y = 1.0
        ref_z = 0.0
    else:
        ref_x = 0.0
        ref_y = 0.0
        ref_z = 1.0

    # local_x = normalize(cross(ref, dir))
    var cx_x = ref_y * dir_z - ref_z * dir_y
    var cx_y = ref_z * dir_x - ref_x * dir_z
    var cx_z = ref_x * dir_y - ref_y * dir_x
    var cx_len = sqrt(cx_x * cx_x + cx_y * cx_y + cx_z * cx_z)
    var inv_cx = 1.0 / cx_len
    cx_x *= inv_cx
    cx_y *= inv_cx
    cx_z *= inv_cx

    # local_y = normalize(cross(dir, local_x))
    var cy_x = dir_y * cx_z - dir_z * cx_y
    var cy_y = dir_z * cx_x - dir_x * cx_z
    var cy_z = dir_x * cx_y - dir_y * cx_x
    var cy_len = sqrt(cy_x * cy_x + cy_y * cy_y + cy_z * cy_z)
    var inv_cy = 1.0 / cy_len
    cy_x *= inv_cy
    cy_y *= inv_cy
    cy_z *= inv_cy

    # Half extents
    var hw = beam_width * 0.5
    var hd = beam_depth * 0.5

    # 8 corners: 4 at start, 4 at end
    # Start face corners (centered on start point):
    #   s0 = start + (-hw)*lx + (-hd)*ly
    #   s1 = start + (+hw)*lx + (-hd)*ly
    #   s2 = start + (+hw)*lx + (+hd)*ly
    #   s3 = start + (-hw)*lx + (+hd)*ly
    # End face: same offsets + beam_length * dir

    alias V_COUNT = 24
    alias I_COUNT = 36

    var verts = UnsafePointer[Float32].alloc(V_COUNT * FLOATS_PER_VERTEX)
    var idxs = UnsafePointer[UInt32].alloc(I_COUNT)

    # Compute corner offsets
    var off = UnsafePointer[Float32].alloc(8 * 3)  # 8 corners x 3 coords

    var signs_lx = SIMD[DType.float32, 4](-hw, hw, hw, -hw)
    var signs_ly = SIMD[DType.float32, 4](-hd, -hd, hd, hd)

    # Start face corners
    for i in range(4):
        var slx = signs_lx[i]
        var sly = signs_ly[i]
        off[i * 3] = start_x + slx * cx_x + sly * cy_x
        off[i * 3 + 1] = start_y + slx * cx_y + sly * cy_y
        off[i * 3 + 2] = start_z + slx * cx_z + sly * cy_z

    # End face corners
    for i in range(4):
        var slx = signs_lx[i]
        var sly = signs_ly[i]
        off[(i + 4) * 3] = end_x + slx * cx_x + sly * cy_x
        off[(i + 4) * 3 + 1] = end_y + slx * cx_y + sly * cy_y
        off[(i + 4) * 3 + 2] = end_z + slx * cx_z + sly * cy_z

    # Helper to read corner i
    fn px(ci: Int) -> Float32:
        return off[ci * 3]

    fn py(ci: Int) -> Float32:
        return off[ci * 3 + 1]

    fn pz(ci: Int) -> Float32:
        return off[ci * 3 + 2]

    # Face 0: start face (facing -dir): corners 0,3,2,1
    _set_vertex(verts, 0, px(0), py(0), pz(0), -dir_x, -dir_y, -dir_z)
    _set_vertex(verts, 1, px(3), py(3), pz(3), -dir_x, -dir_y, -dir_z)
    _set_vertex(verts, 2, px(2), py(2), pz(2), -dir_x, -dir_y, -dir_z)
    _set_vertex(verts, 3, px(1), py(1), pz(1), -dir_x, -dir_y, -dir_z)
    _set_quad_ccw(idxs, 0, 0, 1, 2, 3)

    # Face 1: end face (facing +dir): corners 4,5,6,7
    _set_vertex(verts, 4, px(4), py(4), pz(4), dir_x, dir_y, dir_z)
    _set_vertex(verts, 5, px(5), py(5), pz(5), dir_x, dir_y, dir_z)
    _set_vertex(verts, 6, px(6), py(6), pz(6), dir_x, dir_y, dir_z)
    _set_vertex(verts, 7, px(7), py(7), pz(7), dir_x, dir_y, dir_z)
    _set_quad_ccw(idxs, 2, 4, 5, 6, 7)

    # Face 2: bottom (-local_y): corners 0,1,5,4
    _set_vertex(verts, 8, px(0), py(0), pz(0), -cy_x, -cy_y, -cy_z)
    _set_vertex(verts, 9, px(1), py(1), pz(1), -cy_x, -cy_y, -cy_z)
    _set_vertex(verts, 10, px(5), py(5), pz(5), -cy_x, -cy_y, -cy_z)
    _set_vertex(verts, 11, px(4), py(4), pz(4), -cy_x, -cy_y, -cy_z)
    _set_quad_ccw(idxs, 4, 8, 9, 10, 11)

    # Face 3: top (+local_y): corners 3,7,6,2
    _set_vertex(verts, 12, px(3), py(3), pz(3), cy_x, cy_y, cy_z)
    _set_vertex(verts, 13, px(7), py(7), pz(7), cy_x, cy_y, cy_z)
    _set_vertex(verts, 14, px(6), py(6), pz(6), cy_x, cy_y, cy_z)
    _set_vertex(verts, 15, px(2), py(2), pz(2), cy_x, cy_y, cy_z)
    _set_quad_ccw(idxs, 6, 12, 13, 14, 15)

    # Face 4: left (-local_x): corners 0,4,7,3
    _set_vertex(verts, 16, px(0), py(0), pz(0), -cx_x, -cx_y, -cx_z)
    _set_vertex(verts, 17, px(4), py(4), pz(4), -cx_x, -cx_y, -cx_z)
    _set_vertex(verts, 18, px(7), py(7), pz(7), -cx_x, -cx_y, -cx_z)
    _set_vertex(verts, 19, px(3), py(3), pz(3), -cx_x, -cx_y, -cx_z)
    _set_quad_ccw(idxs, 8, 16, 17, 18, 19)

    # Face 5: right (+local_x): corners 1,2,6,5
    _set_vertex(verts, 20, px(1), py(1), pz(1), cx_x, cx_y, cx_z)
    _set_vertex(verts, 21, px(2), py(2), pz(2), cx_x, cx_y, cx_z)
    _set_vertex(verts, 22, px(6), py(6), pz(6), cx_x, cx_y, cx_z)
    _set_vertex(verts, 23, px(5), py(5), pz(5), cx_x, cx_y, cx_z)
    _set_quad_ccw(idxs, 10, 20, 21, 22, 23)

    off.free()

    return TessResult(verts, idxs, V_COUNT, I_COUNT)


# ---------------------------------------------------------------------------
# tessellate_panel  -- thin flat plate (curtain wall glass, etc.)
# ---------------------------------------------------------------------------
# Orientation: "vertical" = width along local X, height along local Z
#              "horizontal" = width along local X, depth along local Y
# ---------------------------------------------------------------------------


fn tessellate_panel(
    x: Float32,
    y: Float32,
    base_z: Float32,
    panel_width: Float32,
    panel_height: Float32,
    thickness: Float32,
    rotation_deg: Float32,
) -> TessResult:
    # Vertical panel: thin box with width along X, thickness along Y, height along Z
    return tessellate_box(x, y, base_z, panel_width, thickness, panel_height, rotation_deg)


# ---------------------------------------------------------------------------
# batch_transform_vertices -- SIMD-accelerated 4x4 matrix * vertex array
# ---------------------------------------------------------------------------
# This is the hot path for transforming tessellated geometry into world space
# when a general 4x4 transform is needed (e.g., beam member transforms).
#
# Matrix layout (column-major, matching numpy/OpenGL convention):
#   m[0..3]   = column 0 (local X axis)
#   m[4..7]   = column 1 (local Y axis)
#   m[8..11]  = column 2 (local Z axis)
#   m[12..15] = column 3 (translation)
# ---------------------------------------------------------------------------


fn batch_transform_vertices(
    vertices: UnsafePointer[Float32],
    count: Int,
    # Column-major 4x4 matrix stored in 16 floats
    m0: Float32,
    m1: Float32,
    m2: Float32,
    m3: Float32,
    m4: Float32,
    m5: Float32,
    m6: Float32,
    m7: Float32,
    m8: Float32,
    m9: Float32,
    m10: Float32,
    m11: Float32,
    m12: Float32,
    m13: Float32,
    m14: Float32,
    m15: Float32,
):
    """Transform vertex positions in-place by a 4x4 matrix (column-major).

    Normals (indices 3,4,5 per vertex) are transformed by the upper-left 3x3
    of the matrix (rotation only, no translation).

    Processes 4 vertices at a time using SIMD when possible.
    """
    # For positions: new_pos = M * [x, y, z, 1]^T
    # For normals:   new_nrm = M_3x3 * [nx, ny, nz]^T  (no translation)

    # Process vertices in blocks of 4 for SIMD (we load 4 x-coords at once, etc.)
    var stride = FLOATS_PER_VERTEX  # 6

    # SIMD path: process 4 vertices at a time
    var i = 0
    var simd_end = count - 3  # last index where we can process 4 at once

    while i < simd_end:
        # Gather 4 x, y, z values from 4 consecutive vertices
        var b0 = i * stride
        var b1 = b0 + stride
        var b2 = b1 + stride
        var b3 = b2 + stride

        # Positions
        var px = SIMD[DType.float32, 4](
            vertices[b0], vertices[b1], vertices[b2], vertices[b3]
        )
        var py = SIMD[DType.float32, 4](
            vertices[b0 + 1], vertices[b1 + 1], vertices[b2 + 1], vertices[b3 + 1]
        )
        var pz = SIMD[DType.float32, 4](
            vertices[b0 + 2], vertices[b1 + 2], vertices[b2 + 2], vertices[b3 + 2]
        )

        # Transform positions: new = M * [x,y,z,1]
        var new_px = m0 * px + m4 * py + m8 * pz + m12
        var new_py = m1 * px + m5 * py + m9 * pz + m13
        var new_pz = m2 * px + m6 * py + m10 * pz + m14

        # Normals
        var nx = SIMD[DType.float32, 4](
            vertices[b0 + 3], vertices[b1 + 3], vertices[b2 + 3], vertices[b3 + 3]
        )
        var ny = SIMD[DType.float32, 4](
            vertices[b0 + 4], vertices[b1 + 4], vertices[b2 + 4], vertices[b3 + 4]
        )
        var nz = SIMD[DType.float32, 4](
            vertices[b0 + 5], vertices[b1 + 5], vertices[b2 + 5], vertices[b3 + 5]
        )

        # Transform normals: new = M_3x3 * [nx,ny,nz]  (no translation)
        var new_nx = m0 * nx + m4 * ny + m8 * nz
        var new_ny = m1 * nx + m5 * ny + m9 * nz
        var new_nz = m2 * nx + m6 * ny + m10 * nz

        # Scatter back -- write 4 vertices
        for j in range(4):
            var base = (i + j) * stride
            vertices[base] = new_px[j]
            vertices[base + 1] = new_py[j]
            vertices[base + 2] = new_pz[j]
            vertices[base + 3] = new_nx[j]
            vertices[base + 4] = new_ny[j]
            vertices[base + 5] = new_nz[j]

        i += 4

    # Scalar tail for remaining vertices
    while i < count:
        var base = i * stride
        var px2 = vertices[base]
        var py2 = vertices[base + 1]
        var pz2 = vertices[base + 2]
        vertices[base] = m0 * px2 + m4 * py2 + m8 * pz2 + m12
        vertices[base + 1] = m1 * px2 + m5 * py2 + m9 * pz2 + m13
        vertices[base + 2] = m2 * px2 + m6 * py2 + m10 * pz2 + m14

        var nx2 = vertices[base + 3]
        var ny2 = vertices[base + 4]
        var nz2 = vertices[base + 5]
        vertices[base + 3] = m0 * nx2 + m4 * ny2 + m8 * nz2
        vertices[base + 4] = m1 * nx2 + m5 * ny2 + m9 * nz2
        vertices[base + 5] = m2 * nx2 + m6 * ny2 + m10 * nz2

        i += 1


# ---------------------------------------------------------------------------
# merge_results -- combine multiple TessResult into one mesh
# ---------------------------------------------------------------------------


fn merge_results(
    results: UnsafePointer[TessResult], count: Int
) -> TessResult:
    """Merge multiple TessResult meshes into a single combined mesh."""
    var total_verts = 0
    var total_idxs = 0
    for i in range(count):
        total_verts += results[i].vertex_count
        total_idxs += results[i].index_count

    var verts = UnsafePointer[Float32].alloc(total_verts * FLOATS_PER_VERTEX)
    var idxs = UnsafePointer[UInt32].alloc(total_idxs)

    var v_offset = 0
    var i_offset = 0
    for i in range(count):
        var r = results[i].copy()
        var vf = r.vertex_count * FLOATS_PER_VERTEX
        # Copy vertex data
        for j in range(vf):
            verts[v_offset * FLOATS_PER_VERTEX + j] = r.vertices[j]
        # Copy and offset indices
        for j in range(r.index_count):
            idxs[i_offset + j] = r.indices[j] + UInt32(v_offset)
        v_offset += r.vertex_count
        i_offset += r.index_count

    return TessResult(verts, idxs, total_verts, total_idxs)


# ---------------------------------------------------------------------------
# main -- self-test and benchmark
# ---------------------------------------------------------------------------


fn main():
    print("=== Bonsai Tessellate -- Self-Test ===")
    print()

    # --- Test 1: Unit box ---
    print("--- Test 1: tessellate_box(0,0,0, 2,3,4, 0) ---")
    var box = tessellate_box(0, 0, 0, 2, 3, 4, 0)
    print("  vertices:", box.vertex_count, " indices:", box.index_count)
    print("  triangles:", box.index_count // 3)

    # Print first face (bottom)
    print("  Bottom face (first 4 verts):")
    for i in range(4):
        var b = i * FLOATS_PER_VERTEX
        print(
            "    v",
            i,
            "pos:",
            box.vertices[b],
            box.vertices[b + 1],
            box.vertices[b + 2],
            "nrm:",
            box.vertices[b + 3],
            box.vertices[b + 4],
            box.vertices[b + 5],
        )
    print("  Top face (verts 4-7):")
    for i in range(4, 8):
        var b = i * FLOATS_PER_VERTEX
        print(
            "    v",
            i,
            "pos:",
            box.vertices[b],
            box.vertices[b + 1],
            box.vertices[b + 2],
            "nrm:",
            box.vertices[b + 3],
            box.vertices[b + 4],
            box.vertices[b + 5],
        )

    # Verify: all 36 indices are in [0, 24)
    var idx_ok = True
    for i in range(box.index_count):
        if box.indices[i] >= 24:
            idx_ok = False
    print("  All indices < 24:", idx_ok)
    box.free()

    # --- Test 2: Wall ---
    print()
    print("--- Test 2: tessellate_wall(0,0, 5,0, 0, 3, 0.2) ---")
    var wall = tessellate_wall(0, 0, 5, 0, 0, 3, 0.2)
    print("  vertices:", wall.vertex_count, " indices:", wall.index_count)
    # Check that wall stretches from x~0 to x~5
    var min_x: Float32 = 1e9
    var max_x: Float32 = -1e9
    var min_y: Float32 = 1e9
    var max_y: Float32 = -1e9
    var max_z: Float32 = -1e9
    for i in range(wall.vertex_count):
        var b = i * FLOATS_PER_VERTEX
        var vx = wall.vertices[b]
        var vy = wall.vertices[b + 1]
        var vz = wall.vertices[b + 2]
        if vx < min_x:
            min_x = vx
        if vx > max_x:
            max_x = vx
        if vy < min_y:
            min_y = vy
        if vy > max_y:
            max_y = vy
        if vz > max_z:
            max_z = vz
    print("  X range:", min_x, "to", max_x, "(expect ~0 to ~5)")
    print("  Y range:", min_y, "to", max_y, "(expect ~-0.1 to ~0.1)")
    print("  Max Z:", max_z, "(expect 3.0)")
    wall.free()

    # --- Test 3: Column ---
    print()
    print("--- Test 3: tessellate_column(5, 5, 0, 0.3, 0.3, 3.5, 0) ---")
    var col = tessellate_column(5, 5, 0, 0.3, 0.3, 3.5, 0)
    print("  vertices:", col.vertex_count, " indices:", col.index_count)
    # Check centroid of bottom face is near (5, 5)
    var sum_x: Float32 = 0
    var sum_y: Float32 = 0
    for i in range(4):
        var b = i * FLOATS_PER_VERTEX
        sum_x += col.vertices[b]
        sum_y += col.vertices[b + 1]
    print("  Bottom face centroid X:", sum_x / 4.0, "(expect ~5)")
    print("  Bottom face centroid Y:", sum_y / 4.0, "(expect ~5)")
    col.free()

    # --- Test 4: Slab ---
    print()
    print("--- Test 4: tessellate_slab(0, 0, 0, 10, 8, 0.2, 0) ---")
    var slab = tessellate_slab(0, 0, 0, 10, 8, 0.2, 0)
    print("  vertices:", slab.vertex_count, " indices:", slab.index_count)
    slab.free()

    # --- Test 5: Beam ---
    print()
    print("--- Test 5: tessellate_beam(0,0,3, 6,0,3, 0.2, 0.4) ---")
    var beam = tessellate_beam(0, 0, 3, 6, 0, 3, 0.2, 0.4)
    print("  vertices:", beam.vertex_count, " indices:", beam.index_count)
    # Check X range spans ~0..6
    min_x = 1e9
    max_x = -1e9
    for i in range(beam.vertex_count):
        var b = i * FLOATS_PER_VERTEX
        var vx = beam.vertices[b]
        if vx < min_x:
            min_x = vx
        if vx > max_x:
            max_x = vx
    print("  X range:", min_x, "to", max_x, "(expect ~0 to ~6)")
    beam.free()

    # --- Test 6: Rotated box ---
    print()
    print("--- Test 6: tessellate_box(0,0,0, 4,2,1, 45) ---")
    var rbox = tessellate_box(0, 0, 0, 4, 2, 1, 45)
    print("  vertices:", rbox.vertex_count, " indices:", rbox.index_count)
    # Verify normals on bottom face are (0,0,-1)
    var nz_ok = True
    for i in range(4):
        var b = i * FLOATS_PER_VERTEX
        if rbox.vertices[b + 5] != -1.0:
            nz_ok = False
    print("  Bottom face nz == -1:", nz_ok)
    rbox.free()

    # --- Test 7: batch_transform_vertices ---
    print()
    print("--- Test 7: batch_transform_vertices (translate by 10,20,30) ---")
    var t_box = tessellate_box(0, 0, 0, 1, 1, 1, 0)
    # Identity rotation + translation (10, 20, 30)
    batch_transform_vertices(
        t_box.vertices,
        t_box.vertex_count,
        1, 0, 0, 0,  # col 0
        0, 1, 0, 0,  # col 1
        0, 0, 1, 0,  # col 2
        10, 20, 30, 1,  # col 3 (translation)
    )
    # First vertex should be at (10, 20, 30) (was 0,0,0)
    print(
        "  v0 after translate:",
        t_box.vertices[0],
        t_box.vertices[1],
        t_box.vertices[2],
        "(expect 10, 20, 30)",
    )
    # Normal should be unchanged (0,0,-1)
    print(
        "  v0 normal after translate:",
        t_box.vertices[3],
        t_box.vertices[4],
        t_box.vertices[5],
        "(expect 0, 0, -1)",
    )
    t_box.free()

    # --- Benchmark ---
    print()
    print("=== Benchmark ===")

    var box_sizes = List(100, 500, 1000, 5000, 10000)
    for ni in range(len(box_sizes)):
        var n = box_sizes[ni]
        var start = perf_counter_ns()
        for i in range(n):
            var r = tessellate_box(
                Float32(i), 0, 0, 5, 3, 2.8, 0
            )
            r.free()
        var elapsed_ns = perf_counter_ns() - start
        var us_per = Float64(elapsed_ns) / Float64(n) / 1000.0
        print(
            " ",
            n,
            "boxes:",
            elapsed_ns / 1000,
            "us total,",
            us_per,
            "us/element",
        )

    # Wall benchmark
    var wall_sizes = List(100, 500, 1000, 5000)
    for ni in range(len(wall_sizes)):
        var n = wall_sizes[ni]
        var start = perf_counter_ns()
        for i in range(n):
            var r = tessellate_wall(0, 0, Float32(i) + 5, 0, 0, 3, 0.2)
            r.free()
        var elapsed_ns = perf_counter_ns() - start
        var us_per = Float64(elapsed_ns) / Float64(n) / 1000.0
        print(
            " ",
            n,
            "walls:",
            elapsed_ns / 1000,
            "us total,",
            us_per,
            "us/element",
        )

    # Beam benchmark
    var beam_sizes = List(100, 500, 1000, 5000)
    for ni in range(len(beam_sizes)):
        var n = beam_sizes[ni]
        var start = perf_counter_ns()
        for i in range(n):
            var r = tessellate_beam(0, 0, 3, Float32(i) + 6, 0, 3, 0.2, 0.4)
            r.free()
        var elapsed_ns = perf_counter_ns() - start
        var us_per = Float64(elapsed_ns) / Float64(n) / 1000.0
        print(
            " ",
            n,
            "beams:",
            elapsed_ns / 1000,
            "us total,",
            us_per,
            "us/element",
        )

    # batch_transform benchmark
    print()
    print("  batch_transform_vertices benchmark (24 verts x N iterations):")
    var bt = tessellate_box(0, 0, 0, 1, 1, 1, 0)
    var xform_sizes = List(10000, 100000, 1000000)
    for ni in range(len(xform_sizes)):
        var n = xform_sizes[ni]
        var start = perf_counter_ns()
        for i in range(n):
            batch_transform_vertices(
                bt.vertices,
                bt.vertex_count,
                1, 0, 0, 0,
                0, 1, 0, 0,
                0, 0, 1, 0,
                Float32(i), 0, 0, 1,
            )
        var elapsed_ns = perf_counter_ns() - start
        var us_per = Float64(elapsed_ns) / Float64(n) / 1000.0
        print(
            "   ",
            n,
            "transforms:",
            elapsed_ns / 1000,
            "us total,",
            us_per,
            "us/call",
        )
    bt.free()

    print()
    print("=== All tests passed ===")
