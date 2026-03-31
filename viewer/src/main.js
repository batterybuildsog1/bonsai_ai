// Boot sequence for the Bonsai BIM Viewer
// Loads IFC file, initializes all views, sets up keyboard shortcuts

import "./styles.css";
import { App } from "./app.js";
import * as viewer from "./viewer.js";
import * as inspector from "./inspector.js";
import * as chat from "./chat.js";

// Default IFC file path — relative to the project root served by Vite
const DEFAULT_IFC_PATH = "/out/retail_terrace_concept/retail_terrace_concept.ifc";

function getIfcUrl() {
  // Check URL params first
  const params = new URLSearchParams(window.location.search);
  return params.get("model") || params.get("ifc") || DEFAULT_IFC_PATH;
}

async function boot() {
  const root = document.querySelector("#app");
  const loadingEl = root.querySelector("[data-loading]");
  const loadingText = root.querySelector("[data-loading-text]");

  const app = new App(root);
  await app.boot(viewer, inspector, chat);

  // Set up search
  setupSearch(root, app);

  // Initialize the 3D scene
  if (loadingText) loadingText.textContent = "Initializing 3D engine...";
  await viewer.setupScene();

  // Load IFC file
  const ifcUrl = getIfcUrl();
  if (loadingText) loadingText.textContent = `Loading ${ifcUrl.split("/").pop()}...`;

  try {
    await viewer.loadIFC(ifcUrl);
  } catch (err) {
    console.error("[boot] IFC load failed:", err);

    // Show a helpful error instead of crashing
    if (loadingEl) {
      loadingEl.innerHTML = `
        <div class="boot-error">
          <h1>Could not load IFC model</h1>
          <p>${err.message || String(err)}</p>
          <p style="margin-top: 12px; font-size: 12px; color: var(--text-faint);">
            Expected file at: <code>${ifcUrl}</code>
          </p>
          <p style="margin-top: 8px; font-size: 12px; color: var(--text-faint);">
            Generate a model with Bonsai AI, or specify a path: <code>?model=/path/to/file.ifc</code>
          </p>
        </div>
      `;
      return;
    }
  }

  // Hide loading overlay
  if (loadingEl) {
    loadingEl.classList.add("is-done");
    setTimeout(() => loadingEl.remove(), 700);
  }
}

function setupSearch(root, app) {
  const inputEl = root.querySelector("[data-search-input]");
  const resultsEl = root.querySelector("[data-search-results]");
  if (!inputEl || !resultsEl) return;

  app.bus.on("search:focus", () => inputEl.focus());

  inputEl.addEventListener("input", () => {
    const query = inputEl.value.trim().toLowerCase();
    if (query.length < 2) {
      resultsEl.classList.add("is-hidden");
      return;
    }

    const elements = app.state.elements || [];
    const matches = elements.filter((el) =>
      (el.name || "").toLowerCase().includes(query) ||
      (el.type || "").toLowerCase().includes(query) ||
      (el.storey || "").toLowerCase().includes(query)
    ).slice(0, 30);

    if (matches.length === 0) {
      resultsEl.innerHTML = '<div class="search-results__empty">No elements found</div>';
      resultsEl.classList.remove("is-hidden");
      return;
    }

    resultsEl.innerHTML = matches.map((el) => {
      const typeName = el.type?.replace(/^Ifc/, "").replace(/StandardCase$/, "").replace(/([A-Z])/g, " $1").trim() || "Element";
      return `
        <button class="search-result" data-express-id="${el.expressID}">
          <span class="search-result__color" style="background: var(--accent);"></span>
          <div class="search-result__text">
            <span class="search-result__title">${escapeHtmlSafe(el.name)}</span>
            <span class="search-result__subtitle">${escapeHtmlSafe(typeName)}${el.storey ? ` &middot; ${escapeHtmlSafe(el.storey)}` : ""}</span>
          </div>
          <span class="search-result__badge">${escapeHtmlSafe(el.type?.replace("Ifc", "") || "")}</span>
        </button>
      `;
    }).join("");

    resultsEl.classList.remove("is-hidden");

    // Bind click
    resultsEl.querySelectorAll(".search-result").forEach((btn) => {
      btn.addEventListener("click", () => {
        const eid = Number(btn.dataset.expressId);
        const target = elements.find((e) => e.expressID === eid);
        if (target) {
          app.bus.emit("element:select", target);
          inputEl.value = "";
          resultsEl.classList.add("is-hidden");
          inputEl.blur();
        }
      });
    });
  });

  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      resultsEl.classList.add("is-hidden");
      inputEl.blur();
    }
  });

  // Close results on outside click
  document.addEventListener("click", (e) => {
    if (!e.target.closest("[data-search-bar]")) {
      resultsEl.classList.add("is-hidden");
    }
  });
}

function escapeHtmlSafe(str) {
  if (!str) return "";
  const el = document.createElement("span");
  el.textContent = str;
  return el.innerHTML;
}

boot().catch((error) => {
  console.error("Boot failed:", error);
  document.querySelector("#app").innerHTML = `
    <div class="boot-error">
      <h1>BIM Viewer failed to load</h1>
      <p>${String(error.message || error)}</p>
      <p style="margin-top: 8px">Check the console for details.</p>
    </div>
  `;
});
