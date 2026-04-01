// IFC 3D Viewer using web-ifc directly + Three.js
// Parses IFC geometry using web-ifc WASM and renders with Three.js
// This approach is more reliable than @thatopen/components for initial setup

import * as THREE from "three";
import * as WebIFC from "web-ifc";
import { friendlyType } from "./app.js";

// OrbitControls from Three.js examples
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

let renderer = null;
let scene = null;
let camera = null;
let controls = null;
let rootEl = null;
let state = null;
let bus = null;
let ifcAPI = null;
let modelID = null;

// IFC mesh data
const meshes = new Map(); // expressID -> THREE.Mesh
const elementIndex = new Map(); // expressID -> element info

// Selection
let selectedMesh = null;
const selectionMaterial = new THREE.MeshStandardMaterial({
  color: 0x74dbff,
  transparent: true,
  opacity: 0.7,
  depthTest: true,
});

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

  // Three.js scene
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0e14);

  // Camera
  const aspect = container.clientWidth / container.clientHeight;
  camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 1000);
  camera.position.set(20, 15, 20);

  // Renderer
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);

  // Orbit controls
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

  // Ground plane (visible green site + shadow-receiving)
  {
    const groundGeo = new THREE.PlaneGeometry(400, 400);
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0x2d5a27,  // dark green grass
      roughness: 0.9,
      metalness: 0.0,
    });
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.01;
    ground.receiveShadow = true;
    ground.userData.isGroundPlane = true;
    scene.add(ground);
  }

  // Grid
  const grid = new THREE.GridHelper(100, 100, 0x1a2a3a, 0x0d1a28);
  scene.add(grid);

  // Resize handler
  const onResize = () => {
    const w = container.clientWidth;
    const h = container.clientHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  };
  window.addEventListener("resize", onResize);

  // Click-to-select via raycasting
  setupPicking(container);

  // Animation loop
  const animate = () => {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  };
  animate();

  // Initialize web-ifc (single-threaded — multi-threaded has ES module compatibility issues with Vite)
  ifcAPI = new WebIFC.IfcAPI();
  ifcAPI.SetWasmPath("/");
  await ifcAPI.Init(null, true);

  console.log("[viewer] Scene and web-ifc initialized");
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
    // Only count as click if mouse didn't move (not orbit drag)
    if (Math.abs(e.clientX - startX) > 5 || Math.abs(e.clientY - startY) > 5) return;

    const rect = container.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    // Get all meshes from the model group
    const modelMeshes = [];
    scene.traverse((child) => {
      if (child.isMesh && child.userData.expressID !== undefined) {
        modelMeshes.push(child);
      }
    });

    const intersects = raycaster.intersectObjects(modelMeshes, false);

    if (intersects.length > 0) {
      const hit = intersects[0].object;
      const expressID = hit.userData.expressID;
      if (expressID !== undefined) {
        selectElement(expressID, hit);
        return;
      }
    }

    // Empty click — deselect
    if (state.selectedElement) {
      bus.emit("element:deselect");
    }
  });
}

function selectElement(expressID, mesh) {
  // Restore previous selection
  clearSelection();

  // Highlight new selection
  if (mesh) {
    mesh.userData.originalMaterial = mesh.material;
    mesh.material = selectionMaterial;
    selectedMesh = mesh;
  }

  const info = elementIndex.get(expressID) || {
    expressID,
    type: "Unknown",
    name: `Element #${expressID}`,
    storey: null,
    properties: {},
  };

  bus.emit("element:select", info);
}

export function clearSelection() {
  if (selectedMesh && selectedMesh.userData.originalMaterial) {
    selectedMesh.material = selectedMesh.userData.originalMaterial;
    delete selectedMesh.userData.originalMaterial;
    selectedMesh = null;
  }
}

export async function loadIFC(url) {
  if (!ifcAPI) throw new Error("Scene not initialized. Call setupScene() first.");

  const updateLoading = (text) => {
    const el = rootEl.querySelector("[data-loading-text]");
    if (el) el.textContent = text;
  };

  updateLoading("Fetching IFC file...");

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load IFC file: ${response.status} ${response.statusText} (${url})`);
  }

  const data = await response.arrayBuffer();
  const buffer = new Uint8Array(data);
  const fileName = url.split("/").pop()?.replace(".ifc", "") || "model";

  updateLoading("Parsing IFC structure...");

  // Open the IFC model
  modelID = ifcAPI.OpenModel(buffer);
  console.log("[viewer] IFC model opened, modelID:", modelID);

  updateLoading("Extracting geometry...");

  // Extract geometry and build Three.js meshes
  const modelGroup = new THREE.Group();
  modelGroup.name = fileName;

  // Get all geometry
  ifcAPI.StreamAllMeshes(modelID, (flatMesh) => {
    const expressID = flatMesh.expressID;
    const placedGeometries = flatMesh.geometries;

    for (let i = 0; i < placedGeometries.size(); i++) {
      const pg = placedGeometries.get(i);
      const geomData = ifcAPI.GetGeometry(modelID, pg.geometryExpressID);

      const verts = ifcAPI.GetVertexArray(geomData.GetVertexData(), geomData.GetVertexDataSize());
      const indices = ifcAPI.GetIndexArray(geomData.GetIndexData(), geomData.GetIndexDataSize());

      if (verts.length === 0 || indices.length === 0) {
        geomData.delete();
        continue;
      }

      // Build Three.js geometry
      const geometry = new THREE.BufferGeometry();

      // Vertices are interleaved: x,y,z, nx,ny,nz per vertex
      const posArray = new Float32Array(verts.length / 2);
      const normArray = new Float32Array(verts.length / 2);

      for (let j = 0; j < verts.length; j += 6) {
        const idx = j / 2;
        posArray[idx] = verts[j];
        posArray[idx + 1] = verts[j + 1];
        posArray[idx + 2] = verts[j + 2];
        normArray[idx] = verts[j + 3];
        normArray[idx + 1] = verts[j + 4];
        normArray[idx + 2] = verts[j + 5];
      }

      geometry.setAttribute("position", new THREE.BufferAttribute(posArray, 3));
      geometry.setAttribute("normal", new THREE.BufferAttribute(normArray, 3));
      geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(indices), 1));

      // Material from IFC color
      const color = new THREE.Color(pg.color.x, pg.color.y, pg.color.z);
      const alpha = pg.color.w;
      const material = new THREE.MeshStandardMaterial({
        color,
        transparent: alpha < 1.0,
        opacity: alpha,
        side: THREE.DoubleSide,
        roughness: 0.6,
        metalness: 0.1,
      });

      const mesh = new THREE.Mesh(geometry, material);

      // Apply placement matrix
      const matrix = new THREE.Matrix4();
      matrix.fromArray(pg.flatTransformation);
      mesh.applyMatrix4(matrix);

      mesh.userData.expressID = expressID;
      mesh.receiveShadow = true;
      mesh.castShadow = true;

      modelGroup.add(mesh);
      meshes.set(expressID, mesh);

      geomData.delete();
    }
  });

  scene.add(modelGroup);

  updateLoading("Indexing elements...");

  // Index elements by reading IFC properties
  await indexElements();

  // Window depth-buffer fix: now that we know IFC types from the index,
  // apply depthWrite + polygonOffset to IfcWindow meshes so they render
  // as translucent glass instead of dark voids.
  for (const [eid, mesh] of meshes) {
    const info = elementIndex.get(eid);
    if (info && (info.type === 'IfcWindow' || info.type === 'IfcWindowStandardCase')) {
      const mat = mesh.material.clone();
      mat.transparent = true;
      mat.opacity = 0.5;
      mat.color.setHex(0xa8d8ea); // translucent blue glass
      mat.depthWrite = true;
      mat.polygonOffset = true;
      mat.polygonOffsetFactor = -1;
      mat.polygonOffsetUnits = -1;
      mat.side = THREE.DoubleSide;
      mesh.material = mat;
      mesh.renderOrder = 1;
    }
  }

  // Fit camera to model
  fitAll();

  // Gather metadata
  const storeys = [...new Set([...elementIndex.values()].map((e) => e.storey).filter(Boolean))];
  const modelData = {
    fileName,
    elementCount: elementIndex.size,
    storeys,
    elements: [...elementIndex.values()],
  };

  bus.emit("model:loaded", modelData);
  console.log(`[viewer] Model loaded: ${modelData.elementCount} elements, ${storeys.length} storeys`);
  return modelData;
}

async function indexElements() {
  if (modelID === null) return;

  // Get all IFC lines to find building elements
  const allTypes = [
    WebIFC.IFCWALL, WebIFC.IFCWALLSTANDARDCASE,
    WebIFC.IFCSLAB, WebIFC.IFCBEAM, WebIFC.IFCCOLUMN,
    WebIFC.IFCDOOR, WebIFC.IFCWINDOW, WebIFC.IFCROOF,
    WebIFC.IFCSTAIR, WebIFC.IFCSTAIRFLIGHT,
    WebIFC.IFCRAILING, WebIFC.IFCPLATE, WebIFC.IFCMEMBER,
    WebIFC.IFCCURTAINWALL, WebIFC.IFCCOVERING,
    WebIFC.IFCFURNISHINGELEMENT, WebIFC.IFCBUILDINGELEMENTPROXY,
    WebIFC.IFCBUILDINGSTOREY, WebIFC.IFCSPACE,
    WebIFC.IFCFOOTING, WebIFC.IFCPILE,
  ].filter(Boolean); // filter out undefined constants

  const storeyMap = new Map(); // expressID -> storey name

  // First pass: find storeys
  try {
    const storeyLines = ifcAPI.GetLineIDsWithType(modelID, WebIFC.IFCBUILDINGSTOREY);
    for (let i = 0; i < storeyLines.size(); i++) {
      const id = storeyLines.get(i);
      try {
        const props = ifcAPI.GetLine(modelID, id);
        const name = props?.Name?.value || props?.LongName?.value || `Storey #${id}`;
        storeyMap.set(id, name);
      } catch (_) {}
    }
  } catch (_) {}

  // Second pass: index building elements
  for (const ifcType of allTypes) {
    if (ifcType === WebIFC.IFCBUILDINGSTOREY) continue; // already handled
    try {
      const lines = ifcAPI.GetLineIDsWithType(modelID, ifcType);
      for (let i = 0; i < lines.size(); i++) {
        const expressID = lines.get(i);
        try {
          const props = ifcAPI.GetLine(modelID, expressID);
          const typeName = getIfcTypeName(ifcType);
          const name = props?.Name?.value || props?.LongName?.value || `${friendlyType(typeName)} #${expressID}`;

          // Extract properties
          const properties = {};
          for (const [key, val] of Object.entries(props || {})) {
            if (key === "expressID" || key === "type") continue;
            if (val && typeof val === "object" && "value" in val) {
              properties[key] = val.value;
            } else if (typeof val === "string" || typeof val === "number") {
              properties[key] = val;
            }
          }

          // Find storey (simplified — check ContainedInStructure relations later)
          const storey = storeyMap.size > 0 ? [...storeyMap.values()][0] : null;

          elementIndex.set(expressID, {
            expressID,
            type: typeName,
            name,
            storey,
            properties,
          });
        } catch (_) {}
      }
    } catch (_) {}
  }

  // For elements with meshes but no index entry, add basic entries
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

  console.log(`[viewer] Indexed ${elementIndex.size} elements, ${storeyMap.size} storeys`);
}

function getIfcTypeName(typeCode) {
  const map = {
    [WebIFC.IFCWALL]: "IfcWall",
    [WebIFC.IFCWALLSTANDARDCASE]: "IfcWallStandardCase",
    [WebIFC.IFCSLAB]: "IfcSlab",
    [WebIFC.IFCBEAM]: "IfcBeam",
    [WebIFC.IFCCOLUMN]: "IfcColumn",
    [WebIFC.IFCDOOR]: "IfcDoor",
    [WebIFC.IFCWINDOW]: "IfcWindow",
    [WebIFC.IFCROOF]: "IfcRoof",
    [WebIFC.IFCSTAIR]: "IfcStair",
    [WebIFC.IFCSTAIRFLIGHT]: "IfcStairFlight",
    [WebIFC.IFCRAILING]: "IfcRailing",
    [WebIFC.IFCPLATE]: "IfcPlate",
    [WebIFC.IFCMEMBER]: "IfcMember",
    [WebIFC.IFCCURTAINWALL]: "IfcCurtainWall",
    [WebIFC.IFCCOVERING]: "IfcCovering",
    [WebIFC.IFCFURNISHINGELEMENT]: "IfcFurnishingElement",
    [WebIFC.IFCBUILDINGELEMENTPROXY]: "IfcBuildingElementProxy",
    [WebIFC.IFCBUILDINGSTOREY]: "IfcBuildingStorey",
    [WebIFC.IFCSPACE]: "IfcSpace",
    [WebIFC.IFCFOOTING]: "IfcFooting",
    [WebIFC.IFCPILE]: "IfcPile",
  };
  return map[typeCode] || `IfcType_${typeCode}`;
}

function fitAll() {
  if (!scene || !camera || !controls) return;

  const box = new THREE.Box3();
  scene.traverse((child) => {
    if (child.isMesh && child.userData.expressID !== undefined) {
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

  // Move ground plane and grid to the model's base
  const baseY = box.min.y - 0.01;
  scene.traverse((child) => {
    if (child.isMesh && child.userData.isGroundPlane) {
      child.position.y = baseY;
      child.position.x = center.x;
      child.position.z = center.z;
    }
    if (child.isGridHelper) {
      child.position.y = baseY;
      child.position.x = center.x;
      child.position.z = center.z;
    }
  });
}

let wireframeMode = false;

function toggleWireframe() {
  wireframeMode = !wireframeMode;
  const btn = rootEl.querySelector('[data-tool="wireframe"]');
  btn?.classList.toggle("is-active", wireframeMode);

  scene.traverse((child) => {
    if (child.isMesh && child.userData.expressID !== undefined) {
      if (child.material && !child.userData.originalMaterial) {
        child.material.wireframe = wireframeMode;
      }
    }
  });
}

export function getElementIndex() { return elementIndex; }
