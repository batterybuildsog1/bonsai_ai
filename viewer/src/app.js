// App controller with EventBus — adapted from mortgage knowledge viewer

function escapeHtml(str) {
  const el = document.createElement("span");
  el.textContent = str;
  return el.innerHTML;
}

class EventBus {
  constructor() { this.listeners = new Map(); }
  on(event, fn) {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event).add(fn);
  }
  off(event, fn) { this.listeners.get(event)?.delete(fn); }
  emit(event, data) { this.listeners.get(event)?.forEach((fn) => fn(data)); }
}

// Map IFC class names to human-friendly color tokens
const IFC_TYPE_COLORS = {
  IfcWall: "var(--color-wall)",
  IfcWallStandardCase: "var(--color-wall)",
  IfcSlab: "var(--color-slab)",
  IfcBeam: "var(--color-beam)",
  IfcColumn: "var(--color-column)",
  IfcDoor: "var(--color-door)",
  IfcWindow: "var(--color-window)",
  IfcRoof: "var(--color-roof)",
  IfcStairFlight: "var(--color-stair)",
  IfcStair: "var(--color-stair)",
  IfcRailing: "var(--color-railing)",
  IfcSpace: "var(--color-space)",
};

function getTypeColor(ifcType) {
  return IFC_TYPE_COLORS[ifcType] || "var(--accent)";
}

function friendlyType(ifcType) {
  if (!ifcType) return "Element";
  return ifcType.replace(/^Ifc/, "").replace(/StandardCase$/, "").replace(/([A-Z])/g, " $1").trim();
}

class App {
  constructor(rootEl) {
    this.root = rootEl;
    this.bus = new EventBus();
    this.state = {
      modelData: null, // metadata about loaded model
      selectedElement: null, // { expressID, type, name, storey, properties, ... }
      activeTab: "properties",
      elements: [], // flat list for search
      storeys: [],
    };
  }

  async boot(viewerModule, inspectorModule, chatModule) {
    // Modules are passed in from main.js to avoid circular deps
    this.viewer = viewerModule;
    this.inspector = inspectorModule;
    this.chat = chatModule;

    this.viewer.init(this.root, this.state, this.bus);
    this.inspector.init(this.root, this.state, this.bus);
    this.chat.init(this.root, this.state, this.bus);

    this.bindGlobalKeys();
    this.bindBusEvents();
  }

  bindGlobalKeys() {
    document.addEventListener("keydown", (e) => {
      const active = document.activeElement;
      const isInput = active?.tagName === "INPUT" || active?.tagName === "TEXTAREA";
      if (e.key === "/" && !isInput) {
        e.preventDefault();
        this.bus.emit("search:focus");
      }
      if (e.key === "Escape") {
        if (isInput) { active.blur(); return; }
        if (this.state.selectedElement) this.bus.emit("element:deselect");
      }
      if (e.key === "f" && !isInput) {
        e.preventDefault();
        this.bus.emit("viewer:fit");
      }
      if (e.key === "w" && !isInput) {
        e.preventDefault();
        this.bus.emit("viewer:wireframe");
      }
    });
  }

  bindBusEvents() {
    this.bus.on("element:select", (element) => {
      this.state.selectedElement = element;
      this.state.activeTab = "properties";
      this.inspector.render();
    });

    this.bus.on("element:deselect", () => {
      this.state.selectedElement = null;
      this.inspector.close();
      this.viewer.clearSelection();
    });

    this.bus.on("tab:switch", (tab) => {
      this.state.activeTab = tab;
      this.inspector.renderBody();
    });

    this.bus.on("model:loaded", (data) => {
      this.state.modelData = data;
      this.state.elements = data.elements || [];
      this.state.storeys = data.storeys || [];
      this.updateStatus();
    });

    this.bus.on("search:focus", () => {
      const input = this.root.querySelector("[data-search-input]");
      input?.focus();
    });
  }

  updateStatus() {
    const el = this.root.querySelector("[data-status-text]");
    if (el && this.state.modelData) {
      const d = this.state.modelData;
      el.textContent = `${d.elementCount || 0} elements \u00b7 ${d.storeys?.length || 0} storeys \u00b7 ${d.fileName || "model"}`;
    }
  }
}

export { App, EventBus, escapeHtml, getTypeColor, friendlyType, IFC_TYPE_COLORS };
