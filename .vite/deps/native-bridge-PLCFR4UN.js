// viewer/node_modules/@ifc-lite/geometry/dist/native-bridge.js
var NativeBridge = class {
  initialized = false;
  invoke = null;
  listen = null;
  async init() {
    if (this.initialized)
      return;
    const win = globalThis;
    if (!win.__TAURI_INTERNALS__?.invoke) {
      throw new Error("Tauri API not available - this bridge should only be used in Tauri apps");
    }
    this.invoke = win.__TAURI_INTERNALS__.invoke;
    try {
      const event = await import("./event-G4MX2ISL.js");
      this.listen = event.listen;
    } catch {
      console.warn("[NativeBridge] Event API not available, streaming will be limited");
    }
    this.initialized = true;
  }
  isInitialized() {
    return this.initialized;
  }
  async processGeometry(content) {
    if (!this.initialized || !this.invoke) {
      await this.init();
    }
    const encoder = new TextEncoder();
    const buffer = Array.from(encoder.encode(content));
    const result = await this.invoke("get_geometry", { buffer });
    const meshes = result.meshes.map(convertNativeMesh);
    const coordinateInfo = convertNativeCoordinateInfo(result.coordinateInfo);
    return {
      meshes,
      totalVertices: result.totalVertices,
      totalTriangles: result.totalTriangles,
      coordinateInfo
    };
  }
  async processGeometryStreaming(content, options) {
    if (!this.initialized || !this.invoke) {
      await this.init();
    }
    if (!this.listen) {
      console.warn("[NativeBridge] Event API unavailable, falling back to non-streaming mode");
      const result = await this.processGeometry(content);
      const stats = {
        totalMeshes: result.meshes.length,
        totalVertices: result.totalVertices,
        totalTriangles: result.totalTriangles,
        parseTimeMs: 0,
        geometryTimeMs: 0
      };
      options.onBatch?.({
        meshes: result.meshes,
        progress: { processed: result.meshes.length, total: result.meshes.length, currentType: "complete" }
      });
      options.onComplete?.(stats);
      return stats;
    }
    const encoder = new TextEncoder();
    const buffer = Array.from(encoder.encode(content));
    const unlisten = await this.listen("geometry-batch", (event) => {
      const batch = {
        meshes: event.payload.meshes.map(convertNativeMesh),
        progress: {
          processed: event.payload.progress.processed,
          total: event.payload.progress.total,
          currentType: event.payload.progress.currentType
        }
      };
      options.onBatch?.(batch);
    });
    try {
      const stats = await this.invoke("get_geometry_streaming", { buffer });
      const result = {
        totalMeshes: stats.totalMeshes,
        totalVertices: stats.totalVertices,
        totalTriangles: stats.totalTriangles,
        parseTimeMs: stats.parseTimeMs,
        geometryTimeMs: stats.geometryTimeMs
      };
      options.onComplete?.(result);
      return result;
    } catch (error) {
      options.onError?.(error instanceof Error ? error : new Error(String(error)));
      throw error;
    } finally {
      unlisten();
    }
  }
  getApi() {
    return null;
  }
};
function convertNativeMesh(native) {
  return {
    expressId: native.expressId,
    positions: new Float32Array(native.positions),
    normals: new Float32Array(native.normals),
    indices: new Uint32Array(native.indices),
    color: native.color
  };
}
function convertNativeCoordinateInfo(native) {
  return {
    originShift: native.originShift,
    originalBounds: native.originalBounds,
    shiftedBounds: native.shiftedBounds,
    hasLargeCoordinates: native.hasLargeCoordinates
  };
}
export {
  NativeBridge
};
//# sourceMappingURL=native-bridge-PLCFR4UN.js.map
