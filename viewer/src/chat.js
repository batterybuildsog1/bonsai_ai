// Chat Panel — adapted from mortgage viewer chat.js
// Talks to the bim_operator agent via chat-proxy.js
// Element-aware context: includes selected element info in messages

import { marked } from "marked";
import { escapeHtml, friendlyType } from "./app.js";

const PROXY_URL = "http://127.0.0.1:5174/ask";

let rootEl = null;
let state = null;
let bus = null;

let panelEl = null;
let toggleEl = null;
let closeBtn = null;
let messagesEl = null;
let typingEl = null;
let phaseEl = null;
let formEl = null;
let inputEl = null;
let dotEl = null;

const messages = [];
let sending = false;

// Phase indicator — shows what the agent is doing
const PHASES = ["Reading model", "Planning", "Generating response"];
let phaseInterval = null;

export function init(root, appState, appBus) {
  rootEl = root;
  state = appState;
  bus = appBus;

  panelEl = root.querySelector("[data-chat-panel]");
  toggleEl = root.querySelector("[data-chat-toggle]");
  closeBtn = root.querySelector("[data-chat-close]");
  messagesEl = root.querySelector("[data-chat-messages]");
  typingEl = root.querySelector("[data-chat-typing]");
  phaseEl = root.querySelector("[data-typing-phase]");
  formEl = root.querySelector("[data-chat-form]");
  inputEl = root.querySelector("[data-chat-input]");
  dotEl = root.querySelector("[data-chat-dot]");

  toggleEl?.addEventListener("click", () => open());
  closeBtn?.addEventListener("click", () => close());

  formEl?.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (!text || sending) return;
    inputEl.value = "";
    autoResize();
    sendMessage(text);
  });

  inputEl?.addEventListener("input", () => autoResize());
  inputEl?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      formEl.dispatchEvent(new Event("submit"));
    }
  });

  checkProxy();
}

function autoResize() {
  if (!inputEl) return;
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 100) + "px";
}

function open() {
  panelEl?.classList.add("is-open");
  if (toggleEl) toggleEl.style.display = "none";
  inputEl?.focus();
}

function close() {
  panelEl?.classList.remove("is-open");
  if (toggleEl) toggleEl.style.display = "";
}

async function checkProxy() {
  try {
    const res = await fetch(PROXY_URL, { method: "OPTIONS" });
    if (res.ok || res.status === 204) {
      dotEl?.classList.add("is-connected");
    }
  } catch (_) {
    // Proxy not running — dot stays gray
  }
}

async function sendMessage(text) {
  messages.push({ role: "user", text, ts: Date.now() });
  sending = true;
  renderMessages();
  showTyping();

  const context = buildContext();
  const fullMessage = context ? `${context}\n\n${text}` : text;

  try {
    const res = await fetch(PROXY_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: fullMessage }),
    });

    const data = await res.json();

    if (data.error) {
      addSystemMessage(`Error: ${data.error}`);
    } else {
      messages.push({ role: "assistant", text: data.response, ts: Date.now() });
      renderMessages();

      // If the agent detected a gap, offer to research it
      if (data.hasGap) {
        messages.push({
          role: "system",
          text: "The agent may need additional information or tool access.",
          ts: Date.now(),
          action: { type: "research", question: text, context: buildContext() },
        });
        renderMessages();
      }
    }
  } catch (err) {
    addSystemMessage(
      `Could not reach chat proxy at ${PROXY_URL}. Start it with: node viewer/src/chat-proxy.js`
    );
  }

  sending = false;
  hideTyping();
}

function buildContext() {
  const parts = [];

  // Include model context
  if (state.modelData) {
    parts.push(`Model: ${state.modelData.fileName} (${state.modelData.elementCount} elements, ${state.modelData.storeys?.length || 0} storeys)`);
  }

  // Include selected element context
  if (state.selectedElement) {
    const el = state.selectedElement;
    const type = friendlyType(el.type);
    parts.push(`Selected element: "${el.name}" (${type}, Express ID ${el.expressID})`);
    if (el.storey) parts.push(`Storey: ${el.storey}`);

    // Include key properties
    if (el.properties) {
      const propSummary = Object.entries(el.properties)
        .slice(0, 6)
        .map(([k, v]) => `${k}: ${v}`)
        .join(", ");
      if (propSummary) parts.push(`Properties: ${propSummary}`);
    }
  }

  return parts.length > 0 ? `[BIM Context: ${parts.join(". ")}]` : "";
}

function addSystemMessage(text) {
  messages.push({ role: "system", text, ts: Date.now() });
  renderMessages();
}

async function triggerResearch(action) {
  try {
    const res = await fetch(PROXY_URL.replace("/ask", "/research"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: action.question, context: action.context }),
    });
    const data = await res.json();
    addSystemMessage(data.message || "Research task queued.");
  } catch (_) {
    addSystemMessage("Could not queue research task.");
  }
}

function showTyping() {
  typingEl?.classList.remove("is-hidden");
  startPhaseRotation();
}

function hideTyping() {
  typingEl?.classList.add("is-hidden");
  stopPhaseRotation();
}

function startPhaseRotation() {
  let idx = 0;
  if (phaseEl) phaseEl.textContent = PHASES[0];
  phaseInterval = setInterval(() => {
    idx = Math.min(idx + 1, PHASES.length - 1);
    if (phaseEl) phaseEl.textContent = PHASES[idx];
  }, 4000);
}

function stopPhaseRotation() {
  if (phaseInterval) {
    clearInterval(phaseInterval);
    phaseInterval = null;
  }
}

function renderMessages() {
  hideTyping();
  if (!messagesEl) return;

  messagesEl.innerHTML = messages.map((msg) => {
    if (msg.role === "user") {
      return `<div class="chat-message chat-message--user"><p>${escapeHtml(msg.text)}</p></div>`;
    }
    if (msg.role === "assistant") {
      return `<div class="chat-message chat-message--assistant">${marked.parse(msg.text)}</div>`;
    }
    if (msg.action?.type === "research") {
      return `<div class="chat-message chat-message--system">
        <p>${escapeHtml(msg.text)}</p>
        <button class="research-btn" data-research='${JSON.stringify(msg.action).replace(/'/g, "&#39;")}'>Run research task</button>
      </div>`;
    }
    return `<div class="chat-message chat-message--system"><p>${escapeHtml(msg.text)}</p></div>`;
  }).join("");

  // Bind research buttons
  messagesEl.querySelectorAll(".research-btn").forEach((btn) => {
    btn.addEventListener("click", () => triggerResearch(JSON.parse(btn.dataset.research)));
  });

  messagesEl.scrollTop = messagesEl.scrollHeight;

  // Re-show typing if still sending
  if (sending) showTyping();
}
