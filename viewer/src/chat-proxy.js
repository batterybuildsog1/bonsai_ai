// Chat proxy for the Bonsai BIM viewer.
// POST /ask      — quick BIM-grounded answer via bim_operator agent
// POST /research — queue a deep research/tool job for the maintainer

import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { resolve } from "node:path";

const PORT = 5174;
const WORKSPACE = resolve(import.meta.dirname, "../../");

function cors(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
}

function readBody(req) {
  return new Promise((resolve) => {
    let body = "";
    req.on("data", (chunk) => { body += chunk; });
    req.on("end", () => resolve(body));
  });
}

// POST /ask — fast agent answer with bim_operator
async function handleAsk(req, res) {
  const raw = await readBody(req);
  cors(res);

  let message;
  try { message = JSON.parse(raw).message; } catch (_) {}
  if (!message) {
    res.writeHead(400, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "message required" }));
    return;
  }

  console.log(`[chat-proxy] /ask: ${message.slice(0, 80)}...`);

  const proc = spawn("openclaw", [
    "agent", "--agent", "bim_operator",
    "--message", message,
    "--thinking", "low",
  ], { env: { ...process.env }, timeout: 120000, cwd: WORKSPACE });

  let stdout = "";
  let stderr = "";
  proc.stdout.on("data", (d) => { stdout += d; });
  proc.stderr.on("data", (d) => { stderr += d; });

  proc.on("close", () => {
    const answer = stdout.trim() || stderr.trim() || "No response from agent.";

    // Detect if the agent flagged a knowledge gap or needs tool access
    const hasGap = /don't have|not (yet )?(documented|available)|cannot access|outside.*current|unable to/i.test(answer);

    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ response: answer, hasGap }));
  });

  proc.on("error", (err) => {
    console.error(`[chat-proxy] spawn error:`, err.message);
    res.writeHead(500, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: err.message }));
  });
}

// POST /research — delegate to maintainer for tool-based work
async function handleResearch(req, res) {
  const raw = await readBody(req);
  cors(res);

  let question, context;
  try {
    const parsed = JSON.parse(raw);
    question = parsed.question;
    context = parsed.context || "";
  } catch (_) {}

  if (!question) {
    res.writeHead(400, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "question required" }));
    return;
  }

  console.log(`[chat-proxy] /research: ${question.slice(0, 80)}...`);

  // Fire the maintainer agent for deeper work
  const proc = spawn("openclaw", [
    "agent", "--agent", "bim_maintainer",
    "--message", `${question}${context ? ` Context: ${context}` : ""}`,
    "--thinking", "medium",
  ], { env: { ...process.env }, timeout: 300000, cwd: WORKSPACE });

  let stdout = "";
  proc.stdout.on("data", (d) => { stdout += d; });

  proc.on("close", () => {
    console.log(`[chat-proxy] research complete: ${question.slice(0, 60)}`);
  });

  // Return immediately — research runs in background
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ queued: true, message: "Research task started in background. The maintainer agent is working on it." }));
}

// GET /models — list available IFC files
async function handleModels(req, res) {
  cors(res);

  const { readdirSync, statSync } = await import("node:fs");
  const outDir = resolve(WORKSPACE, "out");
  const models = [];

  try {
    for (const entry of readdirSync(outDir)) {
      const entryPath = resolve(outDir, entry);
      if (statSync(entryPath).isDirectory()) {
        try {
          const files = readdirSync(entryPath);
          const ifcFile = files.find((f) => f.endsWith(".ifc"));
          if (ifcFile) {
            models.push({ name: entry, path: `/out/${entry}/${ifcFile}` });
          }
        } catch (_) {}
      }
    }
    // Also check for IFC files in root out/
    for (const entry of readdirSync(outDir)) {
      if (entry.endsWith(".ifc")) {
        models.push({ name: entry.replace(".ifc", ""), path: `/out/${entry}` });
      }
    }
  } catch (_) {}

  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ models }));
}

const server = createServer((req, res) => {
  if (req.method === "OPTIONS") {
    cors(res);
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.method === "POST" && req.url === "/ask") return handleAsk(req, res);
  if (req.method === "POST" && req.url === "/research") return handleResearch(req, res);
  if (req.method === "GET" && req.url === "/models") return handleModels(req, res);

  res.writeHead(404);
  res.end("Not found");
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[chat-proxy] listening on http://127.0.0.1:${PORT}`);
  console.log(`[chat-proxy]   POST /ask      -- quick BIM answer via bim_operator`);
  console.log(`[chat-proxy]   POST /research -- delegate to bim_maintainer`);
  console.log(`[chat-proxy]   GET  /models   -- list available IFC files`);
});
