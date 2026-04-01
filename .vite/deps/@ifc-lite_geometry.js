import {
  IfcLiteBridge,
  IfcLiteMeshCollector
} from "./chunk-3MADGB7W.js";
import "./chunk-ALD7NFWX.js";

// viewer/node_modules/@ifc-lite/geometry/dist/platform-bridge.js
function isTauri() {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}
async function createPlatformBridge() {
  if (isTauri()) {
    const { NativeBridge } = await import("./native-bridge-PLCFR4UN.js");
    return new NativeBridge();
  } else {
    const { WasmBridge } = await import("./wasm-bridge-BCZOTWF3.js");
    return new WasmBridge();
  }
}

// viewer/node_modules/@ifc-lite/geometry/dist/buffer-builder.js
var BufferBuilder = class {
  /**
   * Build interleaved vertex buffer from mesh data
   * Format: [x,y,z,nx,ny,nz] per vertex
   */
  buildInterleavedBuffer(mesh) {
    const vertexCount = mesh.positions.length / 3;
    const buffer = new Float32Array(vertexCount * 6);
    for (let i = 0; i < vertexCount; i++) {
      const base = i * 6;
      const posBase = i * 3;
      const normBase = i * 3;
      buffer[base] = mesh.positions[posBase];
      buffer[base + 1] = mesh.positions[posBase + 1];
      buffer[base + 2] = mesh.positions[posBase + 2];
      buffer[base + 3] = mesh.normals[normBase];
      buffer[base + 4] = mesh.normals[normBase + 1];
      buffer[base + 5] = mesh.normals[normBase + 2];
    }
    return buffer;
  }
  /**
   * Process all meshes and build GPU-ready buffers
   */
  processMeshes(meshes) {
    let totalTriangles = 0;
    let totalVertices = 0;
    for (const mesh of meshes) {
      totalTriangles += mesh.indices.length / 3;
      totalVertices += mesh.positions.length / 3;
    }
    return {
      meshes,
      totalTriangles,
      totalVertices
    };
  }
};

// viewer/node_modules/@ifc-lite/geometry/dist/coordinate-handler.js
var CoordinateHandler = class {
  originShift = { x: 0, y: 0, z: 0 };
  THRESHOLD = 1e4;
  // 10km - threshold for large coordinates
  // Maximum reasonable coordinate - 10,000 km covers any georeferenced building on Earth
  // Values beyond this are garbage/corrupted data (safety net)
  MAX_REASONABLE_COORD = 1e7;
  // For incremental processing
  accumulatedBounds = null;
  shiftCalculated = false;
  // WASM RTC detection - if WASM already applied RTC, skip TypeScript shift
  wasmRtcDetected = false;
  // Threshold for "normal" coordinates when WASM RTC is active (10km = reasonable campus/site size)
  NORMAL_COORD_THRESHOLD = 1e4;
  // Active threshold for coordinate validation (set based on wasmRtcDetected)
  activeThreshold = 1e7;
  /**
   * Check if a coordinate value is reasonable (not corrupted garbage)
   */
  isReasonableValue(value) {
    return Number.isFinite(value) && Math.abs(value) < this.MAX_REASONABLE_COORD;
  }
  /**
   * Calculate bounding box from all meshes (filtering out corrupted values)
   * @param meshes - Meshes to calculate bounds from
   * @param maxCoord - Optional max coordinate threshold (default: MAX_REASONABLE_COORD).
   *   NOTE: Ignored when WASM RTC is active — coordinates are already guaranteed
   *   small and valid by the WASM layer, so the fast sampling path is used instead.
   */
  calculateBounds(meshes, maxCoord) {
    if (this.wasmRtcDetected && this.shiftCalculated) {
      return this.calculateBoundsFast(meshes);
    }
    const bounds = {
      min: { x: Infinity, y: Infinity, z: Infinity },
      max: { x: -Infinity, y: -Infinity, z: -Infinity }
    };
    const threshold = maxCoord ?? this.MAX_REASONABLE_COORD;
    let validVertexCount = 0;
    let corruptedVertexCount = 0;
    for (const mesh of meshes) {
      const positions = mesh.positions;
      for (let i = 0; i < positions.length; i += 3) {
        const x = positions[i];
        const y = positions[i + 1];
        const z = positions[i + 2];
        const coordsFinite = Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z);
        const withinThreshold = coordsFinite && Math.abs(x) < threshold && Math.abs(y) < threshold && Math.abs(z) < threshold;
        if (withinThreshold) {
          bounds.min.x = Math.min(bounds.min.x, x);
          bounds.min.y = Math.min(bounds.min.y, y);
          bounds.min.z = Math.min(bounds.min.z, z);
          bounds.max.x = Math.max(bounds.max.x, x);
          bounds.max.y = Math.max(bounds.max.y, y);
          bounds.max.z = Math.max(bounds.max.z, z);
          validVertexCount++;
        } else {
          corruptedVertexCount++;
        }
      }
    }
    if (corruptedVertexCount > 0) {
      console.log(`[CoordinateHandler] Filtered ${corruptedVertexCount} corrupted vertices, kept ${validVertexCount} valid`);
    }
    return bounds;
  }
  /**
   * Fast bounds calculation using vertex sampling.
   * Used when WASM RTC is confirmed — coordinates are small and valid.
   * Samples first and last vertex of each mesh instead of scanning all vertices.
   * For 208K meshes this is ~416K vertex checks vs 63.5M = ~150x faster.
   * Accuracy is excellent because meshes are localized objects.
   */
  calculateBoundsFast(meshes) {
    let minX = Infinity, minY = Infinity, minZ = Infinity;
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
    for (const mesh of meshes) {
      const positions = mesh.positions;
      const len = positions.length;
      if (len < 3)
        continue;
      const x0 = positions[0];
      const y0 = positions[1];
      const z0 = positions[2];
      if (x0 < minX)
        minX = x0;
      if (y0 < minY)
        minY = y0;
      if (z0 < minZ)
        minZ = z0;
      if (x0 > maxX)
        maxX = x0;
      if (y0 > maxY)
        maxY = y0;
      if (z0 > maxZ)
        maxZ = z0;
      if (len >= 6) {
        const x1 = positions[len - 3];
        const y1 = positions[len - 2];
        const z1 = positions[len - 1];
        if (x1 < minX)
          minX = x1;
        if (y1 < minY)
          minY = y1;
        if (z1 < minZ)
          minZ = z1;
        if (x1 > maxX)
          maxX = x1;
        if (y1 > maxY)
          maxY = y1;
        if (z1 > maxZ)
          maxZ = z1;
      }
    }
    return {
      min: { x: minX, y: minY, z: minZ },
      max: { x: maxX, y: maxY, z: maxZ }
    };
  }
  /**
   * Check if coordinate shift is needed
   */
  needsShift(bounds) {
    const maxCoord = Math.max(Math.abs(bounds.min.x), Math.abs(bounds.max.x), Math.abs(bounds.min.y), Math.abs(bounds.max.y), Math.abs(bounds.min.z), Math.abs(bounds.max.z));
    return maxCoord > this.THRESHOLD;
  }
  /**
   * Calculate centroid (center point) from bounds
   */
  calculateCentroid(bounds) {
    return {
      x: (bounds.min.x + bounds.max.x) / 2,
      y: (bounds.min.y + bounds.max.y) / 2,
      z: (bounds.min.z + bounds.max.z) / 2
    };
  }
  /**
   * Shift positions in-place by subtracting origin shift
   * Corrupted values are set to 0 (center of shifted coordinate system)
   * @param positions - Position array to modify
   * @param shift - Origin shift to subtract
   * @param threshold - Optional threshold for valid coordinates (defaults to MAX_REASONABLE_COORD)
   */
  shiftPositions(positions, shift, threshold) {
    const maxCoord = threshold ?? this.MAX_REASONABLE_COORD;
    for (let i = 0; i < positions.length; i += 3) {
      const x = positions[i];
      const y = positions[i + 1];
      const z = positions[i + 2];
      const coordsValid = Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z) && Math.abs(x) < maxCoord && Math.abs(y) < maxCoord && Math.abs(z) < maxCoord;
      if (coordsValid) {
        positions[i] = x - shift.x;
        positions[i + 1] = y - shift.y;
        positions[i + 2] = z - shift.z;
      } else {
        positions[i] = 0;
        positions[i + 1] = 0;
        positions[i + 2] = 0;
      }
    }
  }
  /**
   * Shift bounds by subtracting origin shift
   */
  shiftBounds(bounds, shift) {
    return {
      min: {
        x: bounds.min.x - shift.x,
        y: bounds.min.y - shift.y,
        z: bounds.min.z - shift.z
      },
      max: {
        x: bounds.max.x - shift.x,
        y: bounds.max.y - shift.y,
        z: bounds.max.z - shift.z
      }
    };
  }
  /**
   * Process meshes: detect large coordinates and shift if needed
   */
  processMeshes(meshes) {
    const emptyResult = {
      originShift: { x: 0, y: 0, z: 0 },
      originalBounds: {
        min: { x: 0, y: 0, z: 0 },
        max: { x: 0, y: 0, z: 0 }
      },
      shiftedBounds: {
        min: { x: 0, y: 0, z: 0 },
        max: { x: 0, y: 0, z: 0 }
      },
      hasLargeCoordinates: false
    };
    if (meshes.length === 0) {
      return emptyResult;
    }
    const originalBounds = this.calculateBounds(meshes);
    const hasValidBounds = originalBounds.min.x !== Infinity && originalBounds.max.x !== -Infinity;
    if (!hasValidBounds) {
      console.warn("[CoordinateHandler] No valid coordinates found in geometry");
      return emptyResult;
    }
    const size = {
      x: originalBounds.max.x - originalBounds.min.x,
      y: originalBounds.max.y - originalBounds.min.y,
      z: originalBounds.max.z - originalBounds.min.z
    };
    const maxSize = Math.max(size.x, size.y, size.z);
    console.log("[CoordinateHandler] Original bounds:", {
      min: originalBounds.min,
      max: originalBounds.max,
      size,
      maxSize: maxSize.toFixed(2) + "m"
    });
    const needsShift = this.needsShift(originalBounds);
    if (!needsShift) {
      console.log("[CoordinateHandler] Coordinates within normal range, no shift needed");
      const zeroShift = { x: 0, y: 0, z: 0 };
      for (const mesh of meshes) {
        this.shiftPositions(mesh.positions, zeroShift);
      }
      return {
        originShift: zeroShift,
        originalBounds,
        shiftedBounds: originalBounds,
        hasLargeCoordinates: false
      };
    }
    const centroid = this.calculateCentroid(originalBounds);
    this.originShift = centroid;
    console.log("[CoordinateHandler] Large coordinates detected, shifting to origin:", {
      centroid,
      maxCoord: Math.max(Math.abs(originalBounds.min.x), Math.abs(originalBounds.max.x), Math.abs(originalBounds.min.y), Math.abs(originalBounds.max.y), Math.abs(originalBounds.min.z), Math.abs(originalBounds.max.z)).toFixed(2) + "m"
    });
    for (const mesh of meshes) {
      this.shiftPositions(mesh.positions, centroid);
    }
    const shiftedBounds = this.shiftBounds(originalBounds, centroid);
    console.log("[CoordinateHandler] Shifted bounds:", {
      min: shiftedBounds.min,
      max: shiftedBounds.max,
      maxSize: maxSize.toFixed(2) + "m"
    });
    return {
      originShift: centroid,
      originalBounds,
      shiftedBounds,
      hasLargeCoordinates: true
    };
  }
  /**
   * Convert local (shifted) coordinates back to world coordinates
   */
  toWorldCoordinates(localPos) {
    return {
      x: localPos.x + this.originShift.x,
      y: localPos.y + this.originShift.y,
      z: localPos.z + this.originShift.z
    };
  }
  /**
   * Convert world coordinates to local (shifted) coordinates
   */
  toLocalCoordinates(worldPos) {
    return {
      x: worldPos.x - this.originShift.x,
      y: worldPos.y - this.originShift.y,
      z: worldPos.z - this.originShift.z
    };
  }
  /**
   * Get current origin shift
   */
  getOriginShift() {
    return { ...this.originShift };
  }
  /**
   * Process meshes incrementally for streaming
   * Accumulates bounds and applies shift once calculated
   *
   * IMPORTANT: Detects if WASM already applied RTC offset by checking if
   * majority of meshes have small coordinates. If so, skips TypeScript shift.
   */
  processMeshesIncremental(batch) {
    this.activeThreshold = this.wasmRtcDetected ? this.NORMAL_COORD_THRESHOLD : this.MAX_REASONABLE_COORD;
    const batchBounds = this.calculateBounds(batch, this.activeThreshold);
    if (this.accumulatedBounds === null) {
      this.accumulatedBounds = batchBounds;
    } else {
      this.accumulatedBounds.min.x = Math.min(this.accumulatedBounds.min.x, batchBounds.min.x);
      this.accumulatedBounds.min.y = Math.min(this.accumulatedBounds.min.y, batchBounds.min.y);
      this.accumulatedBounds.min.z = Math.min(this.accumulatedBounds.min.z, batchBounds.min.z);
      this.accumulatedBounds.max.x = Math.max(this.accumulatedBounds.max.x, batchBounds.max.x);
      this.accumulatedBounds.max.y = Math.max(this.accumulatedBounds.max.y, batchBounds.max.y);
      this.accumulatedBounds.max.z = Math.max(this.accumulatedBounds.max.z, batchBounds.max.z);
    }
    if (!this.shiftCalculated && this.accumulatedBounds) {
      const hasValidBounds = this.accumulatedBounds.min.x !== Infinity && this.accumulatedBounds.max.x !== -Infinity;
      if (hasValidBounds) {
        const size = {
          x: this.accumulatedBounds.max.x - this.accumulatedBounds.min.x,
          y: this.accumulatedBounds.max.y - this.accumulatedBounds.min.y,
          z: this.accumulatedBounds.max.z - this.accumulatedBounds.min.z
        };
        const maxSize = Math.max(size.x, size.y, size.z);
        const centroid = this.calculateCentroid(this.accumulatedBounds);
        const distanceFromOrigin = Math.sqrt(centroid.x ** 2 + centroid.y ** 2 + centroid.z ** 2);
        let smallCoordCount = 0;
        let largeCoordCount = 0;
        const SMALL_COORD_THRESHOLD = this.THRESHOLD;
        for (const mesh of batch) {
          const positions = mesh.positions;
          if (positions.length >= 3) {
            const x = Math.abs(positions[0]);
            const y = Math.abs(positions[1]);
            const z = Math.abs(positions[2]);
            const maxCoord = Math.max(x, y, z);
            if (maxCoord < SMALL_COORD_THRESHOLD) {
              smallCoordCount++;
            } else {
              largeCoordCount++;
            }
          }
        }
        const totalMeshes = smallCoordCount + largeCoordCount;
        const wasmRtcLikelyApplied = totalMeshes > 0 && smallCoordCount / totalMeshes > 0.5;
        if (wasmRtcLikelyApplied) {
          this.wasmRtcDetected = true;
          this.accumulatedBounds = this.calculateBounds(batch, this.NORMAL_COORD_THRESHOLD);
        }
        if ((distanceFromOrigin > this.THRESHOLD || maxSize > this.THRESHOLD) && !wasmRtcLikelyApplied) {
          this.originShift = centroid;
          console.log("[CoordinateHandler] Large coordinates detected, shifting to origin:", {
            distanceFromOrigin: distanceFromOrigin.toFixed(2) + "m",
            maxSize: maxSize.toFixed(2) + "m",
            shift: this.originShift
          });
        } else if (wasmRtcLikelyApplied) {
          console.log("[CoordinateHandler] Skipping shift - WASM RTC already applied:", {
            smallCoordCount,
            largeCoordCount,
            wasmRtcDetected: true
          });
        }
      }
      this.shiftCalculated = true;
    }
    if (this.originShift.x !== 0 || this.originShift.y !== 0 || this.originShift.z !== 0) {
      for (const mesh of batch) {
        this.shiftPositions(mesh.positions, this.originShift, this.activeThreshold);
      }
    }
  }
  /**
   * Get current coordinate info (for incremental updates)
   */
  getCurrentCoordinateInfo() {
    if (!this.accumulatedBounds) {
      return null;
    }
    const hasValidBounds = this.accumulatedBounds.min.x !== Infinity && this.accumulatedBounds.max.x !== -Infinity;
    if (!hasValidBounds) {
      return null;
    }
    const shiftedBounds = this.shiftBounds(this.accumulatedBounds, this.originShift);
    const hasLargeCoordinates = this.originShift.x !== 0 || this.originShift.y !== 0 || this.originShift.z !== 0;
    return {
      originShift: { ...this.originShift },
      originalBounds: { ...this.accumulatedBounds },
      shiftedBounds,
      hasLargeCoordinates
    };
  }
  /**
   * Get final coordinate info after incremental processing
   */
  getFinalCoordinateInfo() {
    const current = this.getCurrentCoordinateInfo();
    if (current) {
      return current;
    }
    return {
      originShift: { x: 0, y: 0, z: 0 },
      originalBounds: {
        min: { x: 0, y: 0, z: 0 },
        max: { x: 0, y: 0, z: 0 }
      },
      shiftedBounds: {
        min: { x: 0, y: 0, z: 0 },
        max: { x: 0, y: 0, z: 0 }
      },
      hasLargeCoordinates: false
    };
  }
  /**
   * Reset incremental state (for new file)
   */
  reset() {
    this.accumulatedBounds = null;
    this.shiftCalculated = false;
    this.originShift = { x: 0, y: 0, z: 0 };
    this.wasmRtcDetected = false;
    this.activeThreshold = this.MAX_REASONABLE_COORD;
  }
};

// viewer/node_modules/@ifc-lite/geometry/dist/progressive-loader.js
var GeometryQuality;
(function(GeometryQuality2) {
  GeometryQuality2["Fast"] = "fast";
  GeometryQuality2["Balanced"] = "balanced";
  GeometryQuality2["High"] = "high";
})(GeometryQuality || (GeometryQuality = {}));

// viewer/node_modules/@ifc-lite/geometry/dist/lod.js
var LODGenerator = class {
  config;
  constructor(config = {}) {
    this.config = {
      minScreenSize: config.minScreenSize ?? 2,
      // 2 pixels minimum
      distanceThresholds: config.distanceThresholds ?? [50, 200, 1e3]
      // near, mid, far
    };
  }
  /**
   * Calculate screen-space size of a mesh from camera position
   */
  calculateScreenSize(meshBounds, cameraPosition, _viewProjMatrix, _viewportWidth, viewportHeight) {
    const center = {
      x: (meshBounds.min.x + meshBounds.max.x) / 2,
      y: (meshBounds.min.y + meshBounds.max.y) / 2,
      z: (meshBounds.min.z + meshBounds.max.z) / 2
    };
    const size = {
      x: meshBounds.max.x - meshBounds.min.x,
      y: meshBounds.max.y - meshBounds.min.y,
      z: meshBounds.max.z - meshBounds.min.z
    };
    const radius = Math.sqrt(size.x ** 2 + size.y ** 2 + size.z ** 2) / 2;
    const dx = center.x - cameraPosition.x;
    const dy = center.y - cameraPosition.y;
    const dz = center.z - cameraPosition.z;
    const distance = Math.sqrt(dx ** 2 + dy ** 2 + dz ** 2);
    if (distance === 0)
      return Infinity;
    const fovFactor = 0.414;
    const screenSize = radius / distance * viewportHeight * fovFactor;
    return screenSize;
  }
  /**
   * Determine if mesh should be rendered based on screen size
   */
  shouldRender(meshBounds, cameraPosition, viewProjMatrix, viewportWidth, viewportHeight) {
    const screenSize = this.calculateScreenSize(meshBounds, cameraPosition, viewProjMatrix, viewportWidth, viewportHeight);
    return screenSize >= this.config.minScreenSize;
  }
  /**
   * Get LOD level based on distance (0 = full detail, 1 = medium, 2 = low, -1 = cull)
   */
  getLODLevel(meshBounds, cameraPosition) {
    const center = {
      x: (meshBounds.min.x + meshBounds.max.x) / 2,
      y: (meshBounds.min.y + meshBounds.max.y) / 2,
      z: (meshBounds.min.z + meshBounds.max.z) / 2
    };
    const dx = center.x - cameraPosition.x;
    const dy = center.y - cameraPosition.y;
    const dz = center.z - cameraPosition.z;
    const distance = Math.sqrt(dx ** 2 + dy ** 2 + dz ** 2);
    const [near, mid, far] = this.config.distanceThresholds;
    if (distance < near) {
      return 0;
    } else if (distance < mid) {
      return 1;
    } else if (distance < far) {
      return 2;
    } else {
      return -1;
    }
  }
  /**
   * Compute bounds from mesh data
   */
  static computeBounds(mesh) {
    const positions = mesh.positions;
    if (positions.length === 0) {
      return {
        min: { x: 0, y: 0, z: 0 },
        max: { x: 0, y: 0, z: 0 }
      };
    }
    let minX = positions[0];
    let minY = positions[1];
    let minZ = positions[2];
    let maxX = positions[0];
    let maxY = positions[1];
    let maxZ = positions[2];
    for (let i = 3; i < positions.length; i += 3) {
      const x = positions[i];
      const y = positions[i + 1];
      const z = positions[i + 2];
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      minZ = Math.min(minZ, z);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
      maxZ = Math.max(maxZ, z);
    }
    return {
      min: { x: minX, y: minY, z: minZ },
      max: { x: maxX, y: maxY, z: maxZ }
    };
  }
};

// viewer/node_modules/@ifc-lite/geometry/dist/geometry-deduplicator.js
function hashGeometry(positions, indices) {
  const parts = [
    positions.length,
    indices.length
  ];
  const positionSamples = Math.min(12, positions.length);
  for (let i = 0; i < positionSamples; i++) {
    parts.push(Math.round(positions[i] * 1e3));
  }
  const indexSamples = Math.min(6, indices.length);
  for (let i = 0; i < indexSamples; i++) {
    parts.push(indices[i]);
  }
  if (positions.length > 24) {
    const mid = Math.floor(positions.length / 2);
    for (let i = 0; i < 6; i++) {
      parts.push(Math.round(positions[mid + i] * 1e3));
    }
  }
  return parts.join("_");
}
function deduplicateMeshes(meshes) {
  const geometryGroups = /* @__PURE__ */ new Map();
  for (const mesh of meshes) {
    const hash = hashGeometry(mesh.positions, mesh.indices);
    const existing = geometryGroups.get(hash);
    if (existing) {
      existing.instances.push({
        expressId: mesh.expressId,
        color: mesh.color
      });
    } else {
      geometryGroups.set(hash, {
        geometryHash: hash,
        positions: mesh.positions,
        normals: mesh.normals,
        indices: mesh.indices,
        instances: [{
          expressId: mesh.expressId,
          color: mesh.color
        }]
      });
    }
  }
  return Array.from(geometryGroups.values());
}
function getDeduplicationStats(instanced) {
  const totalInstances = instanced.reduce((sum, g) => sum + g.instances.length, 0);
  const maxInstances = Math.max(...instanced.map((g) => g.instances.length));
  return {
    inputMeshes: totalInstances,
    uniqueGeometries: instanced.length,
    deduplicationRatio: totalInstances / instanced.length,
    totalInstances,
    maxInstancesPerGeometry: maxInstances
  };
}

// viewer/node_modules/@ifc-lite/geometry/dist/default-materials.js
var DEFAULT_MATERIALS = {
  // Structural elements
  "IfcWall": {
    baseColor: [0.95, 0.93, 0.88, 1],
    // Warm white (matte plaster)
    metallic: 0,
    roughness: 0.8
  },
  "IfcSlab": {
    baseColor: [0.75, 0.75, 0.78, 1],
    // Cool gray (concrete)
    metallic: 0,
    roughness: 0.9
  },
  "IfcColumn": {
    baseColor: [0.7, 0.7, 0.7, 1],
    // Light gray (concrete/steel)
    metallic: 0,
    roughness: 0.5
  },
  "IfcBeam": {
    baseColor: [0.55, 0.55, 0.6, 1],
    // Steel blue
    metallic: 0.8,
    roughness: 0.4
  },
  // Openings
  "IfcWindow": {
    baseColor: [0.6, 0.8, 0.95, 0.3],
    // Sky blue (glass, transparent)
    metallic: 0,
    roughness: 0.1
  },
  "IfcDoor": {
    baseColor: [0.6, 0.45, 0.3, 1],
    // Warm wood
    metallic: 0,
    roughness: 0.6
  },
  "IfcOpeningElement": {
    baseColor: [1, 0.4, 0.3, 0.3],
    // Coral, 30% opacity
    metallic: 0,
    roughness: 0.5
  },
  // Spatial elements
  "IfcSpace": {
    baseColor: [0.2, 0.8, 0.9, 0.25],
    // Cyan, 25% opacity
    metallic: 0,
    roughness: 0.6
  },
  "IfcSite": {
    baseColor: [0.4, 0.6, 0.3, 1],
    // Muted green, solid
    metallic: 0,
    roughness: 0.8
  },
  // Roof and stairs
  "IfcRoof": {
    baseColor: [0.7, 0.5, 0.4, 1],
    // Terra cotta (tiles)
    metallic: 0,
    roughness: 0.7
  },
  "IfcStair": {
    baseColor: [0.8, 0.75, 0.65, 1],
    // Sandstone
    metallic: 0,
    roughness: 0.6
  },
  "IfcRailing": {
    baseColor: [0.3, 0.3, 0.35, 1],
    // Dark metal
    metallic: 0.9,
    roughness: 0.3
  },
  // Furniture and fixtures
  "IfcFurniture": {
    baseColor: [0.7, 0.6, 0.5, 1],
    // Natural wood
    metallic: 0,
    roughness: 0.5
  },
  "IfcSanitaryTerminal": {
    baseColor: [0.9, 0.9, 0.95, 1],
    // White porcelain
    metallic: 0,
    roughness: 0.3
  },
  // MEP elements
  "IfcPipeSegment": {
    baseColor: [0.4, 0.5, 0.6, 1],
    // Blue-gray (pipe)
    metallic: 0.7,
    roughness: 0.4
  },
  "IfcDuctSegment": {
    baseColor: [0.6, 0.6, 0.65, 1],
    // Light gray (duct)
    metallic: 0.3,
    roughness: 0.5
  },
  "IfcCableSegment": {
    baseColor: [0.3, 0.3, 0.3, 1],
    // Dark gray (cable)
    metallic: 0,
    roughness: 0.8
  },
  // Default fallback
  "default": {
    baseColor: [0.8, 0.8, 0.8, 1],
    // Neutral gray
    metallic: 0,
    roughness: 0.6
  }
};
function getDefaultMaterialColor(entityType) {
  if (!entityType) {
    return DEFAULT_MATERIALS["default"];
  }
  const normalizedType = entityType.replace(/^IFC/, "").replace(/^Ifc/, "");
  const ifcType = `Ifc${normalizedType}`;
  return DEFAULT_MATERIALS[ifcType] || DEFAULT_MATERIALS[entityType] || DEFAULT_MATERIALS["default"];
}
function getDefaultColor(entityType) {
  return getDefaultMaterialColor(entityType).baseColor;
}

// viewer/node_modules/@ifc-lite/geometry/dist/wasm-memory-manager.js
var WasmMemoryManager = class {
  memory;
  cachedBuffer = null;
  constructor(memory) {
    this.memory = memory;
  }
  /**
   * Get current memory buffer, detecting if it has changed (grown)
   */
  getBuffer() {
    const currentBuffer = this.memory.buffer;
    if (this.cachedBuffer !== currentBuffer) {
      this.cachedBuffer = currentBuffer;
    }
    return currentBuffer;
  }
  /**
   * Create a Float32Array view directly into WASM memory (NO COPY!)
   *
   * WARNING: View becomes invalid if WASM memory grows!
   * Use immediately and discard.
   *
   * @param byteOffset Byte offset into WASM memory (ptr value from Rust)
   * @param length Number of f32 elements (not bytes)
   */
  createFloat32View(byteOffset, length) {
    const buffer = this.getBuffer();
    return new Float32Array(buffer, byteOffset, length);
  }
  /**
   * Create a Uint32Array view directly into WASM memory (NO COPY!)
   *
   * @param byteOffset Byte offset into WASM memory
   * @param length Number of u32 elements (not bytes)
   */
  createUint32View(byteOffset, length) {
    const buffer = this.getBuffer();
    return new Uint32Array(buffer, byteOffset, length);
  }
  /**
   * Create a Float64Array view directly into WASM memory (NO COPY!)
   *
   * @param byteOffset Byte offset into WASM memory
   * @param length Number of f64 elements (not bytes)
   */
  createFloat64View(byteOffset, length) {
    const buffer = this.getBuffer();
    return new Float64Array(buffer, byteOffset, length);
  }
  /**
   * Create a Uint8Array view directly into WASM memory (NO COPY!)
   *
   * @param byteOffset Byte offset into WASM memory
   * @param length Number of bytes
   */
  createUint8View(byteOffset, length) {
    const buffer = this.getBuffer();
    return new Uint8Array(buffer, byteOffset, length);
  }
  /**
   * Check if a view is still valid (memory hasn't grown)
   */
  isViewValid(view) {
    return view.buffer === this.memory.buffer;
  }
  /**
   * Get raw ArrayBuffer (for advanced use cases)
   */
  getRawBuffer() {
    return this.getBuffer();
  }
  /**
   * Check if memory has grown since last access
   */
  hasMemoryGrown() {
    return this.cachedBuffer !== null && this.cachedBuffer !== this.memory.buffer;
  }
};

// viewer/node_modules/@ifc-lite/geometry/dist/zero-copy-collector.js
var ZeroCopyMeshCollector = class {
  ifcApi;
  content;
  memoryManager;
  constructor(ifcApi, content) {
    this.ifcApi = ifcApi;
    this.content = content;
    const wasmMemory = ifcApi.getMemory();
    this.memoryManager = new WasmMemoryManager(wasmMemory);
  }
  /**
   * Stream geometry batches with zero-copy views into WASM memory
   *
   * @param batchSize Number of meshes per batch (default: 25)
   * @yields Batches with views into WASM memory
   */
  async *streamBatches(batchSize = 25) {
    const batchQueue = [];
    let resolveWaiting = null;
    let isComplete = false;
    const processingPromise = this.ifcApi.parseToGpuGeometryAsync(this.content, {
      batchSize,
      onBatch: (gpuGeom, _progress) => {
        batchQueue.push(gpuGeom);
        if (resolveWaiting) {
          resolveWaiting();
          resolveWaiting = null;
        }
      },
      onComplete: (_stats) => {
        isComplete = true;
        if (resolveWaiting) {
          resolveWaiting();
          resolveWaiting = null;
        }
      }
    });
    while (true) {
      while (batchQueue.length > 0) {
        const gpuGeom = batchQueue.shift();
        const vertexView = this.memoryManager.createFloat32View(gpuGeom.vertexDataPtr, gpuGeom.vertexDataLen);
        const indexView = this.memoryManager.createUint32View(gpuGeom.indicesPtr, gpuGeom.indicesLen);
        const meshMetadata = [];
        for (let i = 0; i < gpuGeom.meshCount; i++) {
          const meta = gpuGeom.getMeshMetadata(i);
          if (meta) {
            meshMetadata.push({
              expressId: meta.expressId,
              vertexOffset: meta.vertexOffset,
              vertexCount: meta.vertexCount,
              indexOffset: meta.indexOffset,
              indexCount: meta.indexCount,
              color: meta.color
            });
          }
        }
        yield {
          vertexView,
          indexView,
          vertexByteLength: gpuGeom.vertexDataByteLength,
          indexByteLength: gpuGeom.indicesByteLength,
          meshMetadata,
          stats: {
            meshCount: gpuGeom.meshCount,
            vertexCount: gpuGeom.totalVertexCount,
            triangleCount: gpuGeom.totalTriangleCount
          },
          free: () => gpuGeom.free()
        };
      }
      if (isComplete && batchQueue.length === 0)
        break;
      await new Promise((resolve) => {
        resolveWaiting = resolve;
      });
    }
    await processingPromise;
  }
  /**
   * Parse all geometry at once (for smaller files)
   *
   * @returns Batch with views into WASM memory
   */
  parseAll() {
    const gpuGeom = this.ifcApi.parseToGpuGeometry(this.content);
    const vertexView = this.memoryManager.createFloat32View(gpuGeom.vertexDataPtr, gpuGeom.vertexDataLen);
    const indexView = this.memoryManager.createUint32View(gpuGeom.indicesPtr, gpuGeom.indicesLen);
    const meshMetadata = [];
    for (let i = 0; i < gpuGeom.meshCount; i++) {
      const meta = gpuGeom.getMeshMetadata(i);
      if (meta) {
        meshMetadata.push({
          expressId: meta.expressId,
          vertexOffset: meta.vertexOffset,
          vertexCount: meta.vertexCount,
          indexOffset: meta.indexOffset,
          indexCount: meta.indexCount,
          color: meta.color
        });
      }
    }
    return {
      vertexView,
      indexView,
      vertexByteLength: gpuGeom.vertexDataByteLength,
      indexByteLength: gpuGeom.indicesByteLength,
      meshMetadata,
      stats: {
        meshCount: gpuGeom.meshCount,
        vertexCount: gpuGeom.totalVertexCount,
        triangleCount: gpuGeom.totalTriangleCount
      },
      free: () => gpuGeom.free()
    };
  }
  /**
   * Get WASM memory manager for advanced use cases
   */
  getMemoryManager() {
    return this.memoryManager;
  }
};
var ZeroCopyInstancedCollector = class {
  ifcApi;
  content;
  memoryManager;
  constructor(ifcApi, content) {
    this.ifcApi = ifcApi;
    this.content = content;
    const wasmMemory = ifcApi.getMemory();
    this.memoryManager = new WasmMemoryManager(wasmMemory);
  }
  /**
   * Parse instanced geometry with zero-copy views
   *
   * @returns Array of instanced geometry batches
   */
  parseAll() {
    const collection = this.ifcApi.parseToGpuInstancedGeometry(this.content);
    const batches = [];
    let totalInstances = 0;
    for (let i = 0; i < collection.length; i++) {
      const geomRef = collection.getRef(i);
      if (!geomRef)
        continue;
      const vertexView = this.memoryManager.createFloat32View(geomRef.vertexDataPtr, geomRef.vertexDataLen);
      const indexView = this.memoryManager.createUint32View(geomRef.indicesPtr, geomRef.indicesLen);
      const instanceView = this.memoryManager.createFloat32View(geomRef.instanceDataPtr, geomRef.instanceDataLen);
      const expressIdsView = this.memoryManager.createUint32View(geomRef.instanceExpressIdsPtr, geomRef.instanceCount);
      batches.push({
        geometryId: geomRef.geometryId,
        vertexView,
        indexView,
        instanceView,
        expressIds: Array.from(expressIdsView),
        vertexByteLength: geomRef.vertexDataByteLength,
        indexByteLength: geomRef.indicesByteLength,
        instanceByteLength: geomRef.instanceDataByteLength,
        indexCount: geomRef.indicesLen,
        instanceCount: geomRef.instanceCount
      });
      totalInstances += geomRef.instanceCount;
    }
    return {
      batches,
      stats: {
        geometryCount: collection.length,
        totalInstances
      },
      free: () => {
        if (typeof collection.free === "function") {
          collection.free();
        }
      }
    };
  }
  /**
   * Get WASM memory manager for advanced use cases
   */
  getMemoryManager() {
    return this.memoryManager;
  }
};

// viewer/node_modules/@ifc-lite/geometry/dist/index.js
function calculateDynamicBatchSize(batchNumber, initialBatchSize = 50, maxBatchSize = 500) {
  if (batchNumber <= 3) {
    return initialBatchSize;
  } else if (batchNumber <= 6) {
    return Math.floor((initialBatchSize + maxBatchSize) / 2);
  } else {
    return maxBatchSize;
  }
}
var GeometryProcessor = class {
  bridge = null;
  platformBridge = null;
  bufferBuilder;
  coordinateHandler;
  isNative = false;
  constructor(options = {}) {
    this.bufferBuilder = new BufferBuilder();
    this.coordinateHandler = new CoordinateHandler();
    this.isNative = isTauri();
    void options.quality;
    if (!this.isNative) {
      this.bridge = new IfcLiteBridge();
    }
  }
  /**
   * Initialize the geometry processor
   * In Tauri: Creates platform bridge for native Rust processing
   * In browser: Loads WASM
   */
  async init() {
    if (this.isNative) {
      this.platformBridge = await createPlatformBridge();
      await this.platformBridge.init();
      console.log("[GeometryProcessor] Native bridge initialized");
    } else {
      if (this.bridge) {
        await this.bridge.init();
      }
    }
  }
  /**
   * Process IFC file and extract geometry (synchronous, use processStreaming for large files)
   * @param buffer IFC file buffer
   * @param entityIndex Optional entity index for priority-based loading
   */
  async process(buffer, entityIndex) {
    void entityIndex;
    let meshes;
    if (this.isNative && this.platformBridge) {
      console.time("[GeometryProcessor] native-processing");
      const decoder = new TextDecoder();
      const content = decoder.decode(buffer);
      const result2 = await this.platformBridge.processGeometry(content);
      meshes = result2.meshes;
      console.timeEnd("[GeometryProcessor] native-processing");
    } else {
      if (!this.bridge?.isInitialized()) {
        await this.init();
      }
      const mainThreadResult = await this.collectMeshesMainThread(buffer);
      meshes = mainThreadResult.meshes;
      const coordinateInfoFromHandler = this.coordinateHandler.processMeshes(meshes);
      const buildingRotation = mainThreadResult.buildingRotation;
      const coordinateInfo2 = {
        ...coordinateInfoFromHandler,
        buildingRotation
      };
      const bufferResult2 = this.bufferBuilder.processMeshes(meshes);
      return {
        meshes: bufferResult2.meshes,
        totalTriangles: bufferResult2.totalTriangles,
        totalVertices: bufferResult2.totalVertices,
        coordinateInfo: coordinateInfo2
      };
    }
    const coordinateInfo = this.coordinateHandler.processMeshes(meshes);
    const bufferResult = this.bufferBuilder.processMeshes(meshes);
    const result = {
      meshes: bufferResult.meshes,
      totalTriangles: bufferResult.totalTriangles,
      totalVertices: bufferResult.totalVertices,
      coordinateInfo
    };
    return result;
  }
  /**
   * Collect meshes on main thread using IFC-Lite WASM
   */
  async collectMeshesMainThread(buffer, _entityIndex) {
    if (!this.bridge) {
      throw new Error("WASM bridge not initialized");
    }
    const decoder = new TextDecoder();
    const content = decoder.decode(buffer);
    const collector = new IfcLiteMeshCollector(this.bridge.getApi(), content);
    const meshes = collector.collectMeshes();
    const buildingRotation = collector.getBuildingRotation();
    return { meshes, buildingRotation };
  }
  /**
   * Process IFC file with streaming output for progressive rendering
   * Uses native Rust in Tauri, WASM in browser
   * @param buffer IFC file buffer
   * @param entityIndex Optional entity index for priority-based loading
   * @param batchConfig Dynamic batch configuration or fixed batch size
   */
  async *processStreaming(buffer, _entityIndex, batchConfig = 25) {
    if (this.isNative) {
      if (!this.platformBridge) {
        await this.init();
      }
    } else if (!this.bridge?.isInitialized()) {
      await this.init();
    }
    this.coordinateHandler.reset();
    yield { type: "start", totalEstimate: buffer.length / 1e3 };
    await new Promise((resolve) => setTimeout(resolve, 0));
    const decoder = new TextDecoder();
    const content = decoder.decode(buffer);
    yield { type: "model-open", modelID: 0 };
    if (this.isNative && this.platformBridge) {
      console.time("[GeometryProcessor] native-streaming");
      const result = await this.platformBridge.processGeometry(content);
      const totalMeshes = result.meshes.length;
      this.coordinateHandler.processMeshesIncremental(result.meshes);
      const coordinateInfo = this.coordinateHandler.getFinalCoordinateInfo();
      yield { type: "batch", meshes: result.meshes, totalSoFar: totalMeshes, coordinateInfo: coordinateInfo || void 0 };
      yield { type: "complete", totalMeshes, coordinateInfo };
      console.timeEnd("[GeometryProcessor] native-streaming");
    } else {
      if (!this.bridge) {
        throw new Error("WASM bridge not initialized");
      }
      const collector = new IfcLiteMeshCollector(this.bridge.getApi(), content);
      let totalMeshes = 0;
      let extractedBuildingRotation = void 0;
      const fileSizeMB = typeof batchConfig !== "number" && batchConfig.fileSizeMB ? batchConfig.fileSizeMB : buffer.length / (1024 * 1024);
      const wasmBatchSize = fileSizeMB < 10 ? 100 : fileSizeMB < 50 ? 200 : fileSizeMB < 100 ? 300 : fileSizeMB < 300 ? 500 : fileSizeMB < 500 ? 1500 : 3e3;
      for await (const item of collector.collectMeshesStreaming(wasmBatchSize)) {
        if (item && typeof item === "object" && "type" in item && item.type === "colorUpdate") {
          yield { type: "colorUpdate", updates: item.updates };
          continue;
        }
        if (item && typeof item === "object" && "type" in item && item.type === "rtcOffset") {
          const rtcEvent = item;
          yield { type: "rtcOffset", rtcOffset: rtcEvent.rtcOffset, hasRtc: rtcEvent.hasRtc };
          continue;
        }
        const batch = item;
        this.coordinateHandler.processMeshesIncremental(batch);
        totalMeshes += batch.length;
        const coordinateInfo2 = this.coordinateHandler.getCurrentCoordinateInfo();
        const coordinateInfoWithRotation = coordinateInfo2 && extractedBuildingRotation !== void 0 ? { ...coordinateInfo2, buildingRotation: extractedBuildingRotation } : coordinateInfo2;
        yield { type: "batch", meshes: batch, totalSoFar: totalMeshes, coordinateInfo: coordinateInfoWithRotation || void 0 };
      }
      extractedBuildingRotation = collector.getBuildingRotation();
      const coordinateInfo = this.coordinateHandler.getFinalCoordinateInfo();
      const finalCoordinateInfo = extractedBuildingRotation !== void 0 ? { ...coordinateInfo, buildingRotation: extractedBuildingRotation } : coordinateInfo;
      yield { type: "complete", totalMeshes, coordinateInfo: finalCoordinateInfo };
    }
  }
  /**
   * Process IFC file with streaming instanced geometry output for progressive rendering
   * Groups identical geometries by hash (before transformation) for GPU instancing
   * @param buffer IFC file buffer
   * @param batchSize Number of unique geometries per batch (default: 25)
   */
  async *processInstancedStreaming(buffer, batchSize = 25) {
    if (this.isNative) {
      if (!this.platformBridge) {
        await this.init();
      }
      console.warn("[GeometryProcessor] Native instanced streaming not yet implemented, using WASM");
    }
    if (!this.bridge?.isInitialized()) {
      await this.init();
    }
    this.coordinateHandler.reset();
    yield { type: "start", totalEstimate: buffer.length / 1e3 };
    const decoder = new TextDecoder();
    const content = decoder.decode(buffer);
    yield { type: "model-open", modelID: 0 };
    const collector = new IfcLiteMeshCollector(this.bridge.getApi(), content);
    let totalGeometries = 0;
    let totalInstances = 0;
    const fileSizeMB = buffer.length / (1024 * 1024);
    const effectiveBatchSize = fileSizeMB < 50 ? batchSize : fileSizeMB < 200 ? Math.max(batchSize, 50) : fileSizeMB < 300 ? Math.max(batchSize, 100) : Math.max(batchSize, 200);
    for await (const batch of collector.collectInstancedGeometryStreaming(effectiveBatchSize)) {
      const meshDataBatch = [];
      for (const geom of batch) {
        const positions = geom.positions;
        const normals = geom.normals;
        const indices = geom.indices;
        if (geom.instance_count > 0) {
          const firstInstance = geom.get_instance(0);
          if (firstInstance) {
            const color = firstInstance.color;
            meshDataBatch.push({
              expressId: firstInstance.expressId,
              positions,
              normals,
              indices,
              color: [color[0], color[1], color[2], color[3]]
            });
          }
        }
      }
      if (meshDataBatch.length > 0) {
        this.coordinateHandler.processMeshesIncremental(meshDataBatch);
      }
      totalGeometries += batch.length;
      totalInstances += batch.reduce((sum, g) => sum + g.instance_count, 0);
      const coordinateInfo2 = this.coordinateHandler.getCurrentCoordinateInfo();
      yield {
        type: "batch",
        geometries: batch,
        totalSoFar: totalGeometries,
        coordinateInfo: coordinateInfo2 || void 0
      };
    }
    const coordinateInfo = this.coordinateHandler.getFinalCoordinateInfo();
    yield { type: "complete", totalGeometries, totalInstances, coordinateInfo };
  }
  /**
   * Process IFC file in parallel using Web Workers.
   * Each worker gets its own WASM instance and processes a disjoint slice
   * of the geometry entity list. Batches are yielded as they arrive from
   * any worker, enabling progressive rendering while utilizing multiple cores.
   *
   * @param buffer IFC file buffer
   */
  async *processParallel(buffer) {
    if (!this.bridge?.isInitialized()) {
      await this.init();
    }
    this.coordinateHandler.reset();
    yield { type: "start", totalEstimate: buffer.length / 1e3 };
    yield { type: "model-open", modelID: 0 };
    const sharedBuffer = new SharedArrayBuffer(buffer.byteLength);
    new Uint8Array(sharedBuffer).set(buffer);
    const makeWorker = () => new Worker(new URL("./geometry.worker.ts", import.meta.url), { type: "module" });
    const prePassResult = await new Promise((resolve, reject) => {
      const w = makeWorker();
      w.onmessage = (e) => {
        if (e.data.type === "prepass-result") {
          w.terminate();
          resolve(e.data.result);
        } else if (e.data.type === "error") {
          w.terminate();
          reject(new Error(e.data.message));
        }
      };
      w.onerror = (e) => {
        w.terminate();
        reject(new Error(e.message));
      };
      w.postMessage({ type: "prepass", sharedBuffer });
    });
    if (!prePassResult || !prePassResult.jobs || prePassResult.totalJobs === 0) {
      const coordinateInfo2 = this.coordinateHandler.getFinalCoordinateInfo();
      yield { type: "complete", totalMeshes: 0, coordinateInfo: coordinateInfo2 };
      return;
    }
    const { jobs: jobsFlat, totalJobs, unitScale, rtcOffset, needsShift, voidKeys, voidCounts, voidValues, styleIds, styleColors } = prePassResult;
    const rtcX = rtcOffset?.[0] ?? 0;
    const rtcY = rtcOffset?.[1] ?? 0;
    const rtcZ = rtcOffset?.[2] ?? 0;
    const cores = typeof navigator !== "undefined" ? navigator.hardwareConcurrency ?? 2 : 2;
    const deviceMemoryGB = typeof navigator !== "undefined" ? navigator.deviceMemory ?? 8 : 8;
    const fileSizeGB = buffer.byteLength / (1024 * 1024 * 1024);
    let maxWorkers;
    if (cores >= 16 && deviceMemoryGB >= 16) {
      maxWorkers = Math.min(8, Math.floor(cores / 2));
    } else if (cores >= 8 && deviceMemoryGB >= 8) {
      maxWorkers = fileSizeGB > 0.5 ? 2 : 3;
    } else {
      maxWorkers = Math.max(1, Math.min(2, Math.floor(cores / 2)));
    }
    const workerCount = Math.min(maxWorkers, totalJobs);
    const jobsPerWorker = Math.ceil(totalJobs / workerCount);
    const chunks = [];
    for (let i = 0; i < workerCount; i++) {
      const start = i * jobsPerWorker;
      const end = Math.min(start + jobsPerWorker, totalJobs);
      if (start < end)
        chunks.push([start, end]);
    }
    const batchQueue = [];
    let resolveWaiting = null;
    let workersCompleted = 0;
    let totalMeshes = 0;
    let workerError = null;
    const workers = [];
    for (let i = 0; i < chunks.length; i++) {
      const [jobStart, jobEnd] = chunks[i];
      if (jobStart >= jobEnd) {
        workersCompleted++;
        continue;
      }
      const workerJobs = jobsFlat.slice(jobStart * 3, jobEnd * 3);
      const worker = new Worker(new URL("./geometry.worker.ts", import.meta.url), { type: "module" });
      workers.push(worker);
      worker.onmessage = (e) => {
        const msg = e.data;
        if (msg.type === "batch") {
          const meshes = msg.meshes.map((m) => ({
            expressId: m.expressId,
            ifcType: m.ifcType,
            positions: m.positions instanceof Float32Array ? m.positions : new Float32Array(m.positions),
            normals: m.normals instanceof Float32Array ? m.normals : new Float32Array(m.normals),
            indices: m.indices instanceof Uint32Array ? m.indices : new Uint32Array(m.indices),
            color: m.color
          }));
          if (meshes.length > 0) {
            batchQueue.push(meshes);
            if (resolveWaiting) {
              resolveWaiting();
              resolveWaiting = null;
            }
          }
        } else if (msg.type === "complete") {
          totalMeshes += msg.totalMeshes;
          workersCompleted++;
          worker.terminate();
          if (resolveWaiting) {
            resolveWaiting();
            resolveWaiting = null;
          }
        } else if (msg.type === "error") {
          workerError = new Error(`Geometry worker error: ${msg.message}`);
          workersCompleted++;
          worker.terminate();
          if (resolveWaiting) {
            resolveWaiting();
            resolveWaiting = null;
          }
        }
      };
      worker.onerror = (e) => {
        workerError = new Error(`Geometry worker failed: ${e.message}`);
        workersCompleted++;
        worker.terminate();
        if (resolveWaiting) {
          resolveWaiting();
          resolveWaiting = null;
        }
      };
      worker.postMessage({
        type: "process",
        sharedBuffer,
        jobsFlat: workerJobs,
        unitScale,
        rtcX,
        rtcY,
        rtcZ,
        needsShift,
        voidKeys,
        voidCounts,
        voidValues,
        styleIds,
        styleColors
      });
    }
    while (true) {
      while (batchQueue.length > 0) {
        const batch = batchQueue.shift();
        this.coordinateHandler.processMeshesIncremental(batch);
        const coordinateInfo2 = this.coordinateHandler.getCurrentCoordinateInfo();
        yield {
          type: "batch",
          meshes: batch,
          totalSoFar: totalMeshes,
          coordinateInfo: coordinateInfo2 || void 0
        };
      }
      if (workerError) {
        for (const w of workers) {
          try {
            w.terminate();
          } catch {
          }
        }
        throw workerError;
      }
      if (workersCompleted >= chunks.length && batchQueue.length === 0) {
        break;
      }
      await new Promise((resolve) => {
        resolveWaiting = resolve;
      });
    }
    const coordinateInfo = this.coordinateHandler.getFinalCoordinateInfo();
    yield { type: "complete", totalMeshes, coordinateInfo };
  }
  /**
   * Adaptive processing: Choose sync or streaming based on file size
   * Small files (< threshold): Load all at once for instant display
   * Large files (>= threshold): Stream for fast first frame
   * @param buffer IFC file buffer
   * @param options Configuration options
   * @param options.sizeThreshold File size threshold in bytes (default: 2MB)
   * @param options.batchSize Number of meshes per batch for streaming (default: 25)
   * @param options.entityIndex Optional entity index for priority-based loading
   */
  async *processAdaptive(buffer, options = {}) {
    const sizeThreshold = options.sizeThreshold ?? 2 * 1024 * 1024;
    const batchConfig = options.batchSize ?? 25;
    if (this.isNative) {
      if (!this.platformBridge) {
        await this.init();
      }
    } else if (!this.bridge?.isInitialized()) {
      await this.init();
    }
    this.coordinateHandler.reset();
    if (buffer.length < sizeThreshold) {
      yield { type: "start", totalEstimate: buffer.length / 1e3 };
      const decoder = new TextDecoder();
      const content = decoder.decode(buffer);
      yield { type: "model-open", modelID: 0 };
      let allMeshes;
      if (this.isNative && this.platformBridge) {
        console.time("[GeometryProcessor] native-adaptive-sync");
        const result = await this.platformBridge.processGeometry(content);
        allMeshes = result.meshes;
        console.timeEnd("[GeometryProcessor] native-adaptive-sync");
      } else {
        const collector = new IfcLiteMeshCollector(this.bridge.getApi(), content);
        allMeshes = collector.collectMeshes();
      }
      this.coordinateHandler.processMeshesIncremental(allMeshes);
      const coordinateInfo = this.coordinateHandler.getFinalCoordinateInfo();
      yield {
        type: "batch",
        meshes: allMeshes,
        totalSoFar: allMeshes.length,
        coordinateInfo: coordinateInfo || void 0
      };
      yield { type: "complete", totalMeshes: allMeshes.length, coordinateInfo };
    } else {
      const useParallel = typeof SharedArrayBuffer !== "undefined" && typeof Worker !== "undefined" && typeof navigator !== "undefined" && (navigator.hardwareConcurrency ?? 1) > 1;
      if (useParallel) {
        yield* this.processParallel(buffer);
      } else {
        yield* this.processStreaming(buffer, options.entityIndex, batchConfig);
      }
    }
  }
  /**
   * Get the WASM API instance for advanced operations (e.g., entity scanning)
   */
  getApi() {
    if (!this.bridge || !this.bridge.isInitialized()) {
      return null;
    }
    return this.bridge.getApi();
  }
  /**
   * Parse symbolic representations (Plan, Annotation, FootPrint) from IFC content
   * These are pre-authored 2D curves for architectural drawings (door swings, window cuts, etc.)
   * @param buffer IFC file buffer
   * @returns Collection of symbolic polylines and circles
   */
  parseSymbolicRepresentations(buffer) {
    if (!this.bridge || !this.bridge.isInitialized()) {
      return null;
    }
    const decoder = new TextDecoder();
    const content = decoder.decode(buffer);
    return this.bridge.parseSymbolicRepresentations(content);
  }
  /**
   * Extract raw profile polygons from IfcExtrudedAreaSolid building elements.
   * Returns clean per-element profile outlines + 3D placement transforms.
   * Used by Drawing2DGenerator for artifact-free 2D projection.
   * @param buffer IFC file buffer
   * @param modelIndex Federation model index (0 for single-model files)
   * @returns Collection of ProfileEntryJs items, or null if not initialized
   */
  extractProfiles(buffer, modelIndex = 0) {
    if (!this.bridge || !this.bridge.isInitialized()) {
      return null;
    }
    const decoder = new TextDecoder();
    const content = decoder.decode(buffer);
    return this.bridge.extractProfiles(content, modelIndex);
  }
  /**
   * Cleanup resources
   */
  dispose() {
  }
};
export {
  BufferBuilder,
  CoordinateHandler,
  DEFAULT_MATERIALS,
  GeometryProcessor,
  GeometryQuality,
  IfcLiteBridge,
  IfcLiteMeshCollector,
  LODGenerator,
  WasmMemoryManager,
  IfcLiteBridge as WebIfcBridge,
  ZeroCopyInstancedCollector,
  ZeroCopyMeshCollector,
  calculateDynamicBatchSize,
  createPlatformBridge,
  deduplicateMeshes,
  getDeduplicationStats,
  getDefaultColor,
  getDefaultMaterialColor,
  isTauri
};
//# sourceMappingURL=@ifc-lite_geometry.js.map
