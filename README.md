# Mopot

**Push code. Mopot finds the bugs and opens the PR.**

Mopot is an autonomous mobile test + fix pipeline agent. A developer pushes code to GitHub and Mopot handles the hard parts — it builds the Flutter/Android app, navigates it with Claude AI vision to find bugs, writes code fixes, and opens a Pull Request. Humans stay in control through two approval gates powered by UiPath Action Center.

Built for **UiPath AgentHack 2026 — Track 3: UiPath Test Cloud**.

---

## How It Works

```
GitHub push
    │
    ▼ UiPath Maestro triggers pipeline
    │
    ├─ flutter build apk
    ├─ Claude vision navigates app → finds bugs → BugReport
    │
    ├─ HUMAN GATE 1: Approve auto-fix? (UiPath Action Center)
    │
    ├─ Claude writes code fixes → commits → opens GitHub PR
    ├─ Retest on fixed build
    │
    └─ HUMAN GATE 2: Fix PR is ready for review.
                     All tests passing. Merge the PR?
```

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Agent runtime |
| Node.js | 18+ | CLI |
| Flutter | 3.x | Build + test |
| Android SDK | API 34 | ADB + emulator |
| UiPath Robot | Community+ | Pipeline orchestration |

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/thecodedaniel/mopot.git
cd mopot
pip install -r requirements.txt
npm install
npm install -g .
```

### 2. Run the setup wizard

```bash
mopot init
```

This opens a browser UI at `http://localhost:3420` where you configure all credentials in 4 steps. The wizard auto-detects your installed Android emulators, reads your git default branch from the selected project folder, and provides a native OS folder picker — so most of Step 4 fills itself in.

### 3. Start the pipeline server

```bash
uvicorn webhook.main:app --port 7432
```

### 4. Configure your GitHub webhook

In your Flutter repo's Settings → Webhooks, add:
- **Payload URL**: `http://your-machine-ip:7432/webhook/github`
- **Content type**: `application/json`
- **Secret**: your `WEBHOOK_SECRET` value
- **Events**: Just the push event

### 5. Push code — Mopot runs

```bash
git push origin main
# Pipeline starts automatically
mopot logs --follow
```

---

## CLI Commands

```bash
mopot init        # First-time setup wizard (browser UI)
mopot config      # Update credentials
mopot status      # Health check all connections
mopot run         # Manually trigger pipeline
mopot logs        # View recent runs
mopot logs --follow <run-id>  # Live tail a specific run
mopot --version
```

---

## Environment Variables

All secrets are injected at runtime. Copy `.env.example` to `.env` and fill in your values.

```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
GITHUB_TOKEN=ghp_...
FLUTTER_PROJECT_PATH=/path/to/flutter/project
GITHUB_REPO=owner/repo-name
GITHUB_DEFAULT_BRANCH=main
WEBHOOK_SECRET=your-webhook-secret
MOPOT_PORT=7432
MOPOT_AVD=Pixel_9_Pro
```

In production, store all secrets in **UiPath Orchestrator Assets** — Mopot's setup wizard (`mopot init`) handles this automatically.

---

## Repository Structure

```
mopot/
├── cli/                        Node.js CLI (mopot command)
│   ├── index.js
│   ├── commands/               init, config, status, run, logs
│   └── server/                 Express setup wizard + HTML UI
├── agents/                     Python agents (Claude)
│   ├── tester_agent.py         Claude vision loop — finds bugs
│   └── fixer_agent.py          Claude fixes code — opens PR
├── platforms/                  Mobile platform adapter layer
│   ├── base_adapter.py         Abstract interface (do not modify)
│   ├── android_adapter.py      ADB + Flutter CLI (active)
│   ├── ios_adapter.py          Stub — v2.0
│   └── react_native_adapter.py Stub — v2.0
├── uipath/                     UiPath config templates
│   ├── maestro_process.json    BPMN pipeline definition
│   ├── test_cloud_config.json  Test Cloud integration
│   └── agent_builder/          Agent Builder action definitions
├── webhook/
│   └── main.py                 FastAPI server — receives push events
├── tests/
│   └── sample_flutter_app/     Demo Flutter app with 3 intentional bugs
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## UiPath Components

| Component | Purpose |
|---|---|
| **Maestro BPMN** | Pipeline coordination — import `uipath/maestro_process.json` |
| **Test Cloud** | Formal test execution — import `uipath/test_cloud_config.json` |
| **Action Center** | Human approval gates (Gate 1: fix? Gate 2: merge PR?) |
| **Orchestrator Assets** | Encrypted secret storage for all API keys |
| **Robot** | Executes Python agents on your local machine |
| **Agent Builder** | Action definitions — import `uipath/agent_builder/agent_config.json` |

---

## Docker (Linux only for emulator)

```bash
cp .env.example .env  # fill in your values
docker-compose up
```

> **macOS note:** The Android emulator requires KVM hardware acceleration, which is only available on Linux. On macOS, run the pipeline server natively and let it connect to an emulator running on the host. The `Dockerfile` is production-ready for Linux CI environments.

---

## Demo App

`tests/sample_flutter_app/` is a Flutter todo app with three intentional bugs for hackathon demos:

1. **Null crash** — `_items.length` on an uninitialised nullable list
2. **Row overflow** — `Text` in a `Row` without `Expanded` wrapper
3. **Broken route** — `Navigator.pushNamed(context, '/details')` with no `/details` route registered

Run `flutter test` inside that directory to see all three tests fail before Mopot fixes them.

---

## Hackathon Submission

- **Event**: UiPath AgentHack 2026
- **Track**: Track 3 — UiPath Test Cloud
- **Builder**: Daniel Ainoko / thecodedaniel
- **Deadline**: June 29, 2026

---

## License

MIT © Daniel Ainoko / thecodedaniel
