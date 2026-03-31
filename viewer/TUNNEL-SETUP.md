# Bonsai BIM Viewer -- Cloudflare Tunnel Setup

Share IFC models with your team over a browser URL. Heavy compute (Blender,
AI agents, IFC parsing) stays on your MacBook. Teammates only need a browser.

---

## Architecture

```
Teammate's browser                  Your MacBook
  |                                   |
  |  https://viewer.yourdomain.com    |
  |  ---- Cloudflare Tunnel ------->  |  localhost:5173  Vite dev server
  |                                   |    (index.html + Three.js + web-ifc WASM)
  |  https://chat.yourdomain.com      |
  |  ---- Cloudflare Tunnel ------->  |  localhost:5174  Chat proxy (Node.js)
  |                                   |    (POST /ask -> openclaw bim_operator)
  |                                   |    (POST /research -> openclaw bim_maintainer)
  |                                   |    (GET  /models -> list IFC files)
```

### What runs on your MacBook (never exposed directly)

| Component | Port | Purpose |
|-----------|------|---------|
| Vite dev server | 5173 | Serves the viewer HTML/JS/WASM and IFC files from `out/` |
| Chat proxy | 5174 | Node.js HTTP server that shells out to `openclaw` agents |
| Blender + BlenderBIM | -- | Generates IFC files, renders, runs build scripts |
| openclaw agents | -- | bim_operator (fast Q&A), bim_maintainer (deep research) |
| Cloudflare tunnel | -- | `cloudflared` daemon forwarding traffic |

### What teammates see

- A browser-based 3D viewer (Three.js + web-ifc) with pan/orbit/zoom
- A chat panel to ask questions about the loaded model
- HTTPS with valid certs (automatic via Cloudflare)
- Cloudflare Access login (email OTP, no passwords)

### What teammates do NOT have access to

- Your filesystem, terminal, or local network
- Blender or any local tools
- The `openclaw` CLI directly (chat proxy mediates all requests)
- Any port other than 5173/5174 through the tunnel

---

## Prerequisites

1. **cloudflared** installed:

   ```bash
   brew install cloudflare/cloudflare/cloudflared
   ```

   Verify: `cloudflared --version`

2. **A domain on Cloudflare** with DNS managed by Cloudflare. If you
   do not have one, you can register a new domain directly through the
   Cloudflare dashboard (Registrar section) for ~$10/year.

---

## Quick Start

### Step 1: Run the one-time setup

```bash
cd ~/Applications/Bonsai_ai
chmod +x scripts/setup-cloudflare-tunnel.sh scripts/start-tunnel.sh
./scripts/setup-cloudflare-tunnel.sh yourdomain.com
```

This will:
- Open a browser to authenticate with Cloudflare (first time only)
- Create a named tunnel called `bonsai-viewer`
- Write the tunnel config to `~/.cloudflared/config.yml`
- Create DNS CNAME records: `viewer.yourdomain.com` and `chat.yourdomain.com`

### Step 2: Start the viewer (Terminal 1)

```bash
./scripts/serve-bonsai-viewer.sh
```

This starts both the Vite dev server (:5173) and the chat proxy (:5174).

### Step 3: Start the tunnel (Terminal 2)

```bash
./scripts/start-tunnel.sh
```

Or in the background:

```bash
./scripts/start-tunnel.sh --background
```

### Step 4: Share the URL

Send teammates: `https://viewer.yourdomain.com`

---

## Cloudflare Access (Team Authentication)

Cloudflare Access is free for up to 50 users. It adds an email-based
one-time-password (OTP) login screen in front of your tunnel -- no
passwords, no account creation needed for teammates.

### Setup (5 minutes, done in the Cloudflare dashboard)

1. Go to **Cloudflare Zero Trust** dashboard:
   https://one.dash.cloudflare.com/

2. Navigate to **Access > Applications > Add an application**

3. Choose **Self-hosted** and configure:
   - **Application name**: Bonsai BIM Viewer
   - **Session duration**: 24 hours (or whatever suits your team)
   - **Application domain**: `viewer.yourdomain.com`
   - Click **+ Add another** and add: `chat.yourdomain.com`

4. Create an **Access Policy**:
   - **Policy name**: Team members
   - **Action**: Allow
   - **Include rule**: Emails ending in `@yourcompany.com`
     (or list specific email addresses)

5. Save.

Now when a teammate visits `viewer.yourdomain.com`, they will see a
Cloudflare login page. They enter their email, receive a one-time code,
and are in. The session lasts 24 hours before they need to re-authenticate.

### Notes on Access

- The free tier (Zero Trust Free) supports up to 50 users
- No software install needed on the teammate's machine
- Works on any device with a modern browser
- You can revoke access instantly from the dashboard
- Access logs show who connected and when

---

## Script Reference

| Script | Purpose |
|--------|---------|
| `scripts/setup-cloudflare-tunnel.sh <domain>` | One-time: create tunnel + DNS records |
| `scripts/start-tunnel.sh` | Start tunnel in foreground |
| `scripts/start-tunnel.sh --background` | Start tunnel in background |
| `scripts/start-tunnel.sh --stop` | Stop background tunnel |
| `scripts/start-tunnel.sh --check` | Verify readiness without starting |
| `scripts/serve-bonsai-viewer.sh` | Start viewer + chat proxy (run first) |

---

## Troubleshooting

### "Cannot determine default origin certificate path"

You have not authenticated yet. Run:
```bash
cloudflared tunnel login
```

### Tunnel starts but pages do not load

1. Make sure the viewer is running: `curl http://localhost:5173`
2. Make sure the chat proxy is running: `curl http://localhost:5174/models`
3. Check DNS propagation: `dig viewer.yourdomain.com`
   (should show a CNAME to `<tunnel-id>.cfargotunnel.com`)

### SharedArrayBuffer errors in the viewer

web-ifc requires `Cross-Origin-Opener-Policy` and
`Cross-Origin-Embedder-Policy` headers. These are already set in
`vite.config.js`. Cloudflare tunnels pass these headers through
without modification.

### Chat proxy times out

The `bim_operator` agent has a 120-second timeout. If your MacBook is
under heavy load (Blender rendering, etc.), responses may be slow.
The `/research` endpoint returns immediately and runs in the background.

### Tunnel reconnects frequently

This is normal on residential internet. cloudflared automatically
reconnects. If it is a problem, check:
- Your Mac is not going to sleep (use `caffeinate` or Energy Saver settings)
- Your router is not dropping long-lived connections

---

## Stopping Everything

```bash
# Stop the tunnel
./scripts/start-tunnel.sh --stop

# Stop the viewer (Ctrl+C in Terminal 1, or):
# The serve script handles SIGINT cleanup automatically
```

---

## Removing the Tunnel

If you no longer need the tunnel:

```bash
# Delete DNS records (from Cloudflare dashboard or):
cloudflared tunnel route dns --delete bonsai-viewer viewer.yourdomain.com
cloudflared tunnel route dns --delete bonsai-viewer chat.yourdomain.com

# Delete the tunnel
cloudflared tunnel delete bonsai-viewer

# Remove config
rm ~/.cloudflared/config.yml
```
