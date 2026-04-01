import {
  IfcLiteBridge,
  IfcLiteMeshCollector
} from "./chunk-3MADGB7W.js";
import "./chunk-ALD7NFWX.js";

// viewer/node_modules/@ifc-lite/geometry/dist/wasm-bridge.js
var WasmBridge = class {
  bridge;
  initialized = false;
  constructor() {
    this.bridge = new IfcLiteBridge();
  }
  async init() {
    if (this.initialized)
      return;
    await this.bridge.init();
    this.initialized = true;
  }
  isInitialized() {
    return this.initialized;
  }
  async processGeometry(content) {
    if (!this.initialized) {
      await this.init();
    }
    const startTime = performance.now();
    const collector = new IfcLiteMeshCollector(this.bridge.getApi(), content);
    const meshes = collector.collectMeshes();
    const buildingRotation = collector.getBuildingRotation();
    const endTime = performance.now();
    let totalVertices = 0;
    let totalTriangles = 0;
    for (const mesh of meshes) {
      totalVertices += mesh.positions.length / 3;
      totalTriangles += mesh.indices.length / 3;
    }
    const coordinateInfo = {
      originShift: { x: 0, y: 0, z: 0 },
      originalBounds: {
        min: { x: 0, y: 0, z: 0 },
        max: { x: 0, y: 0, z: 0 }
      },
      shiftedBounds: {
        min: { x: 0, y: 0, z: 0 },
        max: { x: 0, y: 0, z: 0 }
      },
      hasLargeCoordinates: false,
      buildingRotation
    };
    return {
      meshes,
      totalVertices,
      totalTriangles,
      coordinateInfo
    };
  }
  async processGeometryStreaming(content, options) {
    if (!this.initialized) {
      await this.init();
    }
    const startTime = performance.now();
    const collector = new IfcLiteMeshCollector(this.bridge.getApi(), content);
    let totalMeshes = 0;
    let totalVertices = 0;
    let totalTriangles = 0;
    try {
      for await (const item of collector.collectMeshesStreaming(50)) {
        if (item && typeof item === "object" && "type" in item && item.type === "colorUpdate") {
          continue;
        }
        const batch = item;
        totalMeshes += batch.length;
        for (const mesh of batch) {
          totalVertices += mesh.positions.length / 3;
          totalTriangles += mesh.indices.length / 3;
        }
        options.onBatch?.({
          meshes: batch,
          progress: {
            processed: totalMeshes,
            total: totalMeshes,
            // We don't know total upfront with WASM
            currentType: "processing"
          }
        });
      }
    } catch (error) {
      options.onError?.(error instanceof Error ? error : new Error(String(error)));
      throw error;
    }
    const endTime = performance.now();
    const totalTime = endTime - startTime;
    const stats = {
      totalMeshes,
      totalVertices,
      totalTriangles,
      parseTimeMs: totalTime * 0.3,
      // Estimate
      geometryTimeMs: totalTime * 0.7
      // Estimate
    };
    options.onComplete?.(stats);
    return stats;
  }
  getApi() {
    return this.bridge.getApi();
  }
};
export {
  WasmBridge
};
//# sourceMappingURL=wasm-bridge-BCZOTWF3.js.map
