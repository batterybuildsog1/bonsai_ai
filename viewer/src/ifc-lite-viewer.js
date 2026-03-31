// IFC-Lite Viewer — replaces web-ifc with @ifc-lite/geometry + @ifc-lite/query
// Keeps Three.js for rendering, uses IFC-Lite for parsing + geometry extraction
// Drop-in replacement for viewer.js — same exports and event interface

import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GeometryProcessor } from "@ifc-lite/geometry";
import { IfcParser } from "@ifc-lite/parser";
import {
  extractPropertiesOnDemand,
  extractEntityAttributesOnDemand,
} from "@ifc-lite/parser";
import { IfcQuery } from "@ifc-lite/query";
import { friendlyType } from "./app.js";

// --- Three.js state ---
let renderer = null;
let scene = null;
let camera = null;
let controls = null;
let rootEl = null;
let state = null;
let bus = null;

// --- IFC-Lite state ---
let geometryProcessor = null;
let dataStore = null; // IfcDataStore from parseColumnar
let ifcBuffer = null; // Original buffer (needed for geometry processing)

// --- Mesh data ---
const meshes = new Map(); // expressID -> THREE.Mesh
const elementIndex = new Map(); // expressID -> element info

// --- Selection ---
let selectedMesh = null;
const selectionMaterial = new THREE.MeshStandardMaterial({
  color: 0x74dbff,
  transparent: true,
  opacity: 0.7,
  depthTest: true,
});

// --- Performance timings ---
const timings = {};

export function init(root, appState, appBus) {
  rootEl = root;
  state = appState;
  bus = appBus;

  root.querySelector('[data-tool="fit"]')?.addEventListener("click", () => bus.emit("viewer:fit"));
  root.querySelector('[data-tool="wireframe"]')?.addEventListener("click", () => bus.emit("viewer:wireframe"));
  root.querySelector('[data-tool="section"]')?.addEventListener("click", () => {});

  bus.on("viewer:fit", () => fitAll());
  bus.on("viewer:wireframe", () => toggleWireframe());
}

export async function setupScene() {
  const container = rootEl.querySelector("[data-viewport]");
  if (!container) throw new Error("No viewport container found");

  // --- Three.js scene (identical to legacy viewer) ---
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0e14);

  const aspect = container.clientWidth / container.clientHeight;
  camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 1000);
  camera.position.set(20, 15, 20);

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.1;
  controls.screenSpacePanning = true;
  controls.minDistance = 1;
  controls.maxDistance = 500;

  // Lighting
  scene.add(new THREE.AmbientLight(0xffffff, 0.5));

  const dir1 = new THREE.DirectionalLight(0xffffff, 1.0);
  dir1.position.set(50, 80, 50);
  dir1.castShadow = true;
  scene.add(dir1);

  const dir2 = new THREE.DirectionalLight(0xffffff, 0.3);
  dir2.position.set(-30, 40, -30);
  scene.add(dir2);

  scene.add(new THREE.HemisphereLight(0xb1e1ff, 0x444444, 0.4));

  // Grid
  const grid = new THREE.GridHelper(100, 100, 0x1a2a3a, 0x0d1a28);
  scene.add(grid);

  // Resize
  const onResize = () => {
    const w = container.clientWidth;
    const h = container.clientHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  };
  window.addEventListener("resize", onResize);

  // Click-to-select
  setupPicking(container);

  // Animation loop
  const animate = () => {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  };
  animate();

  // --- Initialize IFC-Lite geometry processor ---
  const t0 = performance.now();
  geometryProcessor = new GeometryProcessor();
  await geometryProcessor.init();
  timings.initMs = performance.now() - t0;

  console.log(`[ifc-lite-viewer] Geometry processor initialized in ${timings.initMs.toFixed(0)}ms`);
}

function setupPicking(container) {
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  let startX = 0, startY = 0;

  container.addEventListener("pointerdown", (e) => {
    startX = e.clientX;
    startY = e.clientY;
  });

  container.addEventListener("pointerup", (e) => {
    if (Math.abs(e.clientX - startX) > 5 || Math.abs(e.clientY - startY) > 5) return;

    const rect = container.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    const modelMeshes = [];
    scene.traverse((child) => {
      if (child.isMesh && child.userData.expressId !== undefined) {
        modelMeshes.push(child);
      }
    });

    const intersects = raycaster.intersectObjects(modelMeshes, false);

    if (intersects.length > 0) {
      const hit = intersects[0].object;
      const expressId = hit.userData.expressId;
      if (expressId !== undefined) {
        selectElement(expressId, hit);
        return;
      }
    }

    // Empty click — deselect
    if (state.selectedElement) {
      bus.emit("element:deselect");
    }
  });
}

function selectElement(expressId, mesh) {
  clearSelection();

  if (mesh) {
    mesh.userData.originalMaterial = mesh.material;
    mesh.material = selectionMaterial;
    selectedMesh = mesh;
  }

  // Build element info — use on-demand property extraction from IFC-Lite
  let info = elementIndex.get(expressId);

  if (!info) {
    // Fallback: try to extract on demand
    info = extractElementInfo(expressId);
    if (info) elementIndex.set(expressId, info);
  }

  if (!info) {
    info = {
      expressID: expressId,
      type: "Unknown",
      name: `Element #${expressId}`,
      storey: null,
      properties: {},
    };
  }

  bus.emit("element:select", info);
}

/**
 * Extract element info on demand using IFC-Lite parser extraction functions.
 * The dataStore carries the source buffer internally, so we only need (store, id).
 * Falls back gracefully if dataStore is not available.
 */
function extractElementInfo(expressId) {
  if (!dataStore) return null;

  try {
    // extractEntityAttributesOnDemand returns { globalId, name, description, objectType, tag }
    const attrs = extractEntityAttributesOnDemand(dataStore, expressId);

    // Get entity type from the data store index
    const entityRef = dataStore.entityIndex?.byId?.get(expressId);
    const ifcType = entityRef?.type || "IfcBuildingElement";

    // Flatten property sets into a single properties object
    const properties = {};
    try {
      const psets = extractPropertiesOnDemand(dataStore, expressId);
      if (psets && Array.isArray(psets)) {
        // psets is an array of { name: string, properties: [...] }
        for (const pset of psets) {
          if (pset.properties) {
            for (const prop of pset.properties) {
              if (prop.name && prop.value !== undefined) {
                properties[prop.name] = prop.value;
              }
            }
          }
        }
      } else if (psets && typeof psets === "object") {
        // Might be a plain object of { psetName: { propName: propValue } }
        for (const [psetName, props] of Object.entries(psets)) {
          if (props && typeof props === "object") {
            for (const [propName, propValue] of Object.entries(props)) {
              properties[propName] = propValue;
            }
          }
        }
      }
    } catch (_) {
      // Property extraction may fail for some entities — not critical
    }

    // Add standard attributes to properties
    if (attrs) {
      if (attrs.globalId) properties.GlobalId = attrs.globalId;
      if (attrs.description) properties.Description = attrs.description;
      if (attrs.objectType) properties.ObjectType = attrs.objectType;
      if (attrs.tag) properties.Tag = attrs.tag;
    }

    // Look up storey via spatial hierarchy
    let storey = null;
    try {
      if (dataStore.spatialHierarchy && dataStore.spatialHierarchy.byStorey) {
        // Check each storey to see if this element is contained
        for (const [storeyId, elementIds] of dataStore.spatialHierarchy.byStorey) {
          if (elementIds && (elementIds.has?.(expressId) || (Array.isArray(elementIds) && elementIds.includes(expressId)))) {
            const storeyAttrs = extractEntityAttributesOnDemand(dataStore, storeyId);
            storey = storeyAttrs?.name || `Storey #${storeyId}`;
            break;
          }
        }
      }
    } catch (_) {}

    const name = attrs?.name || `${friendlyType(ifcType)} #${expressId}`;

    return {
      expressID: expressId,
      type: ifcType.replace(/^IFC/, "Ifc"),
      name,
      storey,
      properties,
    };
  } catch (err) {
    console.warn(`[ifc-lite-viewer] Failed to extract info for expressId ${expressId}:`, err);
    return null;
  }
}

export function clearSelection() {
  if (selectedMesh && selectedMesh.userData.originalMaterial) {
    selectedMesh.material = selectedMesh.userData.originalMaterial;
    delete selectedMesh.userData.originalMaterial;
    selectedMesh = null;
  }
}

export async function loadIFC(url) {
  if (!geometryProcessor) throw new Error("Scene not initialized. Call setupScene() first.");

  const updateLoading = (text) => {
    const el = rootEl.querySelector("[data-loading-text]");
    if (el) el.textContent = text;
  };

  // ---- Fetch the IFC file ----
  updateLoading("Fetching IFC file...");
  const t0 = performance.now();

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load IFC file: ${response.status} ${response.statusText} (${url})`);
  }

  const data = await response.arrayBuffer();
  ifcBuffer = new Uint8Array(data);
  const fileName = url.split("/").pop()?.replace(".ifc", "") || "model";

  timings.fetchMs = performance.now() - t0;

  // ---- Parse IFC structure (columnar for memory efficiency) ----
  updateLoading("Parsing IFC structure (IFC-Lite)...");
  const t1 = performance.now();

  const parser = new IfcParser();
  dataStore = await parser.parseColumnar(data);

  timings.parseMs = performance.now() - t1;
  console.log(`[ifc-lite-viewer] Parsed in ${timings.parseMs.toFixed(0)}ms — ${dataStore.entityCount} entities, schema: ${dataStore.schemaVersion}`);

  // ---- Extract geometry via streaming ----
  updateLoading("Extracting geometry (IFC-Lite)...");
  const t2 = performance.now();

  const modelGroup = new THREE.Group();
  modelGroup.name = fileName;
  let meshCount = 0;

  // Use streaming for progressive geometry extraction
  try {
    for await (const event of geometryProcessor.processStreaming(ifcBuffer)) {
      if (event.type === "batch") {
        for (const meshData of event.meshes) {
          const threeMesh = meshDataToThreeMesh(meshData);
          modelGroup.add(threeMesh);
          meshes.set(meshData.expressId, threeMesh);
          meshCount++;
        }
        // Render progress
        if (renderer && scene && camera) {
          renderer.render(scene, camera);
        }
      } else if (event.type === "complete") {
        console.log(`[ifc-lite-viewer] Streaming complete: ${event.totalMeshes} meshes`);
      }
    }
  } catch (streamErr) {
    // Fall back to non-streaming process if streaming fails
    console.warn("[ifc-lite-viewer] Streaming failed, falling back to batch process:", streamErr);
    const result = await geometryProcessor.process(ifcBuffer);
    for (const meshData of result.meshes) {
      const threeMesh = meshDataToThreeMesh(meshData);
      modelGroup.add(threeMesh);
      meshes.set(meshData.expressId, threeMesh);
      meshCount++;
    }
  }

  timings.geometryMs = performance.now() - t2;
  console.log(`[ifc-lite-viewer] Geometry extracted in ${timings.geometryMs.toFixed(0)}ms — ${meshCount} meshes`);

  scene.add(modelGroup);

  // ---- Index elements ----
  updateLoading("Indexing elements...");
  const t3 = performance.now();
  await indexElements();
  timings.indexMs = performance.now() - t3;

  // ---- Fit camera ----
  fitAll();

  timings.totalMs = performance.now() - t0;

  // ---- Emit model:loaded ----
  const storeys = [...new Set([...elementIndex.values()].map((e) => e.storey).filter(Boolean))];
  const modelData = {
    fileName,
    elementCount: elementIndex.size,
    storeys,
    elements: [...elementIndex.values()],
    timings: { ...timings },
    engine: "ifc-lite",
  };

  bus.emit("model:loaded", modelData);

  console.log(
    `[ifc-lite-viewer] Model loaded: ${modelData.elementCount} elements, ${storeys.length} storeys\n` +
    `  Timings: fetch=${timings.fetchMs.toFixed(0)}ms, parse=${timings.parseMs.toFixed(0)}ms, ` +
    `geometry=${timings.geometryMs.toFixed(0)}ms, index=${timings.indexMs.toFixed(0)}ms, ` +
    `total=${timings.totalMs.toFixed(0)}ms`
  );

  return modelData;
}

/**
 * Convert IFC-Lite MeshData to a Three.js Mesh.
 * MeshData: { expressId, positions: Float32Array, normals: Float32Array, indices: Uint32Array, color: [r,g,b,a] }
 */
function meshDataToThreeMesh(meshData) {
  const geometry = new THREE.BufferGeometry();

  geometry.setAttribute("position", new THREE.BufferAttribute(meshData.positions, 3));
  geometry.setAttribute("normal", new THREE.BufferAttribute(meshData.normals, 3));
  geometry.setIndex(new THREE.BufferAttribute(meshData.indices, 1));

  const [r, g, b, a] = meshData.color;
  const material = new THREE.MeshStandardMaterial({
    color: new THREE.Color(r, g, b),
    transparent: a < 1.0,
    opacity: a,
    side: a < 1.0 ? THREE.DoubleSide : THREE.FrontSide,
    depthWrite: a >= 1.0,
    roughness: 0.6,
    metalness: 0.1,
  });

  const mesh = new THREE.Mesh(geometry, material);
  mesh.userData.expressId = meshData.expressId;
  // Also set expressID for backward compat with legacy inspector/app code
  mesh.userData.expressID = meshData.expressId;
  mesh.receiveShadow = true;
  mesh.castShadow = true;

  return mesh;
}

/**
 * Index all building elements using the IFC-Lite query API.
 * This populates the elementIndex map used for inspector panels and search.
 */
async function indexElements() {
  if (!dataStore) return;

  // Get storeys first for spatial context
  const storeyMap = new Map(); // expressId -> storey name
  try {
    const query = new IfcQuery(dataStore);
    // storeys is a getter that returns EntityNode[]
    const storeys = query.storeys;
    if (Array.isArray(storeys)) {
      for (const storey of storeys) {
        const name = storey.name || `Storey #${storey.expressId}`;
        storeyMap.set(storey.expressId, name);
      }
    }
  } catch (err) {
    console.warn("[ifc-lite-viewer] Could not query storeys:", err);
    // Fallback: try to find storeys from the entity index directly
    try {
      const storeyIds = dataStore.entityIndex?.byType?.get("IFCBUILDINGSTOREY") || [];
      for (const sid of storeyIds) {
        const attrs = extractEntityAttributesOnDemand(dataStore, sid);
        storeyMap.set(sid, attrs?.name || `Storey #${sid}`);
      }
    } catch (_) {}
  }

  // Index all entities that have geometry (meshes we rendered)
  for (const [expressId] of meshes) {
    if (elementIndex.has(expressId)) continue;

    try {
      const info = extractElementInfo(expressId);
      if (info) {
        // If storey was not resolved by extractElementInfo, try fallback
        if (!info.storey && storeyMap.size > 0) {
          // Try spatial hierarchy byStorey map
          try {
            if (dataStore.spatialHierarchy && dataStore.spatialHierarchy.byStorey) {
              for (const [storeyId, elementIds] of dataStore.spatialHierarchy.byStorey) {
                if (elementIds && (elementIds.has?.(expressId) || (Array.isArray(elementIds) && elementIds.includes(expressId)))) {
                  info.storey = storeyMap.get(storeyId) || `Storey #${storeyId}`;
                  break;
                }
              }
            }
          } catch (_) {}

          // Fallback: assign first storey (same behavior as legacy viewer)
          if (!info.storey && storeyMap.size > 0) {
            info.storey = [...storeyMap.values()][0];
          }
        }
        elementIndex.set(expressId, info);
      }
    } catch (_) {}
  }

  // For meshes with no index entry, add basic entries
  for (const [eid] of meshes) {
    if (!elementIndex.has(eid)) {
      elementIndex.set(eid, {
        expressID: eid,
        type: "IfcBuildingElement",
        name: `Element #${eid}`,
        storey: null,
        properties: {},
      });
    }
  }

  console.log(`[ifc-lite-viewer] Indexed ${elementIndex.size} elements, ${storeyMap.size} storeys`);
}

function fitAll() {
  if (!scene || !camera || !controls) return;

  const box = new THREE.Box3();
  scene.traverse((child) => {
    if (child.isMesh && child.userData.expressId !== undefined) {
      box.expandByObject(child);
    }
  });

  if (box.isEmpty()) {
    camera.position.set(20, 15, 20);
    camera.lookAt(0, 0, 0);
    controls.target.set(0, 0, 0);
    return;
  }

  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z);
  const fov = camera.fov * (Math.PI / 180);
  const dist = maxDim / (2 * Math.tan(fov / 2)) * 1.5;

  camera.position.copy(center);
  camera.position.x += dist * 0.6;
  camera.position.y += dist * 0.5;
  camera.position.z += dist * 0.6;

  controls.target.copy(center);
  controls.update();
}

let wireframeMode = false;

function toggleWireframe() {
  wireframeMode = !wireframeMode;
  const btn = rootEl.querySelector('[data-tool="wireframe"]');
  btn?.classList.toggle("is-active", wireframeMode);

  scene.traverse((child) => {
    if (child.isMesh && child.userData.expressId !== undefined) {
      if (child.material && !child.userData.originalMaterial) {
        child.material.wireframe = wireframeMode;
      }
    }
  });
}

export function getElementIndex() { return elementIndex; }

export function getTimings() { return { ...timings }; }
