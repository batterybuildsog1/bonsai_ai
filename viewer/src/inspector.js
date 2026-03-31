// Element Inspector Panel — shows selected element properties, geometry, relations
// Glassmorphism styling, tabs: Properties | Geometry | Relations

import { escapeHtml, friendlyType, getTypeColor } from "./app.js";

let rootEl = null;
let state = null;
let bus = null;

let panelEl = null;
let titleEl = null;
let typeEl = null;
let storeyEl = null;
let closeBtn = null;
let tabsEl = null;
let bodyEl = null;

export function init(root, appState, appBus) {
  rootEl = root;
  state = appState;
  bus = appBus;

  panelEl = root.querySelector("[data-inspector-panel]");
  titleEl = root.querySelector("[data-inspector-title]");
  typeEl = root.querySelector("[data-inspector-type]");
  storeyEl = root.querySelector("[data-inspector-storey]");
  closeBtn = root.querySelector("[data-inspector-close]");
  tabsEl = root.querySelector("[data-inspector-tabs]");
  bodyEl = root.querySelector("[data-inspector-body]");

  closeBtn?.addEventListener("click", () => bus.emit("element:deselect"));

  tabsEl?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-tab]");
    if (btn) bus.emit("tab:switch", btn.dataset.tab);
  });
}

export function render() {
  const el = state.selectedElement;
  if (!el) return;

  panelEl.classList.add("is-open");

  // Header
  const color = getTypeColor(el.type);
  typeEl.textContent = friendlyType(el.type);
  typeEl.style.setProperty("--badge-color", color);
  titleEl.textContent = el.name || `Element #${el.expressID}`;
  storeyEl.textContent = el.storey ? `Storey: ${el.storey}` : `Express ID: ${el.expressID}`;

  // Tabs
  renderTabs();
  renderBody();
}

function renderTabs() {
  const tabs = tabsEl.querySelectorAll("[data-tab]");
  tabs.forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.tab === state.activeTab);
  });
}

export function renderBody() {
  const el = state.selectedElement;
  if (!el || !bodyEl) return;

  renderTabs();

  switch (state.activeTab) {
    case "properties":
      bodyEl.innerHTML = renderProperties(el);
      break;
    case "geometry":
      bodyEl.innerHTML = renderGeometry(el);
      break;
    case "relations":
      bodyEl.innerHTML = renderRelations(el);
      break;
    default:
      bodyEl.innerHTML = renderProperties(el);
  }
}

function renderProperties(el) {
  const props = el.properties || {};
  const keys = Object.keys(props).filter((k) => props[k] !== undefined && props[k] !== null && props[k] !== "");

  if (keys.length === 0) {
    return `
      <div class="prop-group">
        <div class="prop-group__title">Identity</div>
        <div class="prop-row">
          <span class="prop-row__key">Express ID</span>
          <span class="prop-row__value">${el.expressID}</span>
        </div>
        <div class="prop-row">
          <span class="prop-row__key">IFC Type</span>
          <span class="prop-row__value">${escapeHtml(el.type)}</span>
        </div>
        <div class="prop-row">
          <span class="prop-row__key">Name</span>
          <span class="prop-row__value">${escapeHtml(el.name)}</span>
        </div>
        ${el.storey ? `<div class="prop-row">
          <span class="prop-row__key">Storey</span>
          <span class="prop-row__value">${escapeHtml(el.storey)}</span>
        </div>` : ""}
      </div>
      <p style="color: var(--text-faint); font-size: 12px; margin-top: 16px;">
        No additional properties found for this element.
      </p>
    `;
  }

  // Group properties: identity first, then alphabetical
  const identity = ["Name", "GlobalId", "ObjectType", "Tag", "Description", "LongName"];
  const identityProps = identity.filter((k) => keys.includes(k));
  const otherProps = keys.filter((k) => !identity.includes(k)).sort();

  let html = `
    <div class="prop-group">
      <div class="prop-group__title">Identity</div>
      <div class="prop-row">
        <span class="prop-row__key">Express ID</span>
        <span class="prop-row__value">${el.expressID}</span>
      </div>
      <div class="prop-row">
        <span class="prop-row__key">IFC Type</span>
        <span class="prop-row__value">${escapeHtml(el.type)}</span>
      </div>
      ${identityProps.map((k) => `
        <div class="prop-row">
          <span class="prop-row__key">${escapeHtml(k)}</span>
          <span class="prop-row__value">${escapeHtml(String(props[k]))}</span>
        </div>
      `).join("")}
    </div>
  `;

  if (el.storey) {
    html += `
      <div class="prop-group">
        <div class="prop-group__title">Spatial</div>
        <div class="prop-row">
          <span class="prop-row__key">Storey</span>
          <span class="prop-row__value">${escapeHtml(el.storey)}</span>
        </div>
      </div>
    `;
  }

  if (otherProps.length > 0) {
    html += `
      <div class="prop-group">
        <div class="prop-group__title">Attributes</div>
        ${otherProps.map((k) => `
          <div class="prop-row">
            <span class="prop-row__key">${escapeHtml(k)}</span>
            <span class="prop-row__value">${escapeHtml(String(props[k]))}</span>
          </div>
        `).join("")}
      </div>
    `;
  }

  return html;
}

function renderGeometry(el) {
  const props = el.properties || {};
  // Extract any geometry-related properties
  const geomKeys = Object.keys(props).filter((k) =>
    /width|height|length|area|volume|thickness|radius|depth|elevation/i.test(k)
  );

  let html = `
    <div class="geometry-preview">
      <p>3D geometry visualization</p>
      <p style="margin-top: 4px; font-size: 11px;">Element #${el.expressID} &middot; ${escapeHtml(friendlyType(el.type))}</p>
    </div>
  `;

  if (geomKeys.length > 0) {
    html += `
      <div class="prop-group">
        <div class="prop-group__title">Dimensions</div>
        ${geomKeys.map((k) => `
          <div class="prop-row">
            <span class="prop-row__key">${escapeHtml(k)}</span>
            <span class="prop-row__value prop-row__value--accent">${escapeHtml(String(props[k]))}</span>
          </div>
        `).join("")}
      </div>
    `;
  } else {
    html += `
      <div class="prop-group">
        <div class="prop-group__title">Dimensions</div>
        <p style="color: var(--text-faint); font-size: 12px;">
          No dimension properties available. Geometry data is embedded in the IFC mesh.
        </p>
      </div>
    `;
  }

  return html;
}

function renderRelations(el) {
  // Find elements on the same storey or related elements
  const related = [];
  if (el.storey && state.elements) {
    for (const other of state.elements) {
      if (other.expressID !== el.expressID && other.storey === el.storey) {
        related.push(other);
      }
      if (related.length >= 20) break; // cap for performance
    }
  }

  if (related.length === 0) {
    return `
      <p style="color: var(--text-faint); font-size: 12px; text-align: center; margin-top: 20px;">
        No relations indexed for this element yet.
      </p>
      <p style="color: var(--text-faint); font-size: 11px; text-align: center; margin-top: 8px;">
        Relation parsing requires IfcRelation entities in the model.
      </p>
    `;
  }

  const items = related.map((r) => {
    const color = getTypeColor(r.type);
    return `
      <div class="relation-item" data-express-id="${r.expressID}">
        <span class="relation-item__dot" style="background: ${color};"></span>
        <div class="relation-item__info">
          <span class="relation-item__name">${escapeHtml(r.name)}</span>
          <span class="relation-item__type">${escapeHtml(friendlyType(r.type))}</span>
        </div>
      </div>
    `;
  }).join("");

  // Bind click events after render
  setTimeout(() => {
    bodyEl?.querySelectorAll(".relation-item").forEach((item) => {
      item.addEventListener("click", () => {
        const eid = Number(item.dataset.expressId);
        const target = state.elements.find((e) => e.expressID === eid);
        if (target) bus.emit("element:select", target);
      });
    });
  }, 0);

  return `
    <div class="prop-group">
      <div class="prop-group__title">Same Storey (${related.length})</div>
      ${items}
    </div>
  `;
}

export function close() {
  panelEl?.classList.remove("is-open");
}
