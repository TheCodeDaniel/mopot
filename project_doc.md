# MOPOT — Project Documentation
### Autonomous Mobile Release Pipeline powered by Claude Code + UiPath

**Version:** 1.0  
**Hackathon:** UiPath AgentHack 2026 (devpost.com)  
**Track:** Track 3 — UiPath Test Cloud  
**Deadline:** June 29, 2026  
**Builder:** Daniel Ainoko / thecodedaniel  

---

## 1. What Is Mopot?

Mopot is an autonomous mobile release pipeline agent. A developer pushes code to GitHub and Mopot handles everything else — it tests the Flutter/Android app using Claude Code, finds bugs, opens a PR with fixes, and deploys to the Google Play Store. Humans stay in control through two approval gates powered by UiPath Action Center.

**Tagline:** *Push code. Mopot ships it.*

---

## 2. The Problem It Solves

Mobile developers waste hours every release on tasks that require no creative thinking:

- Manually running test suites and reading crash logs
- Hunting down bugs introduced in the latest commit
- Writing release notes from memory
- Exporting screenshots in 6 device sizes
- Filling in Play Store metadata
- Waiting on Play Console submission status

No existing tool automates this end to end. CI/CD tools like Codemagic and Bitrise build and upload the binary — but everything surrounding the store submission is still manual. Mopot closes that gap entirely.

---

## 3. Hackathon Track Justification

**Track 3: UiPath Test Cloud** — confirmed fit.

The Track 3 description explicitly states the goal is to build agents that:
- *"evaluate requirements and turn them into meaningful test scenarios"*
- *"recommend fixes when automation breaks"*
- *"orchestrate the right tests at the right time based on risk, coverage, and change impact"*

Mopot does all three. The testing + fix loop is the core innovation. BPMN process orchestration exists inside the solution and satisfies the UiPath Platform Usage criterion without repositioning the product.

**Bonus points:** Claude Code is the primary coding agent throughout. This earns additional points under the Platform Usage judging criterion per the hackathon rules.

---

## 4. Full Pipeline Flow

```
TRIGGER
Developer pushes code to GitHub
        │
        ▼
STEP 1 — UiPath Maestro BPMN starts
GitHub webhook → Maestro BPMN process triggers
        │
        ▼
STEP 2 — Build Phase
Local UiPath Robot receives task from Maestro
Python agent runs:
  → flutter clean
  → flutter pub get
  → flutter build apk --debug
        │
        ▼
STEP 3 — Agentic Testing Phase (Claude Code)
Android emulator spins up via ADB
Claude Code agent:
  → reads Flutter codebase for context
  → navigates the running app screen by screen
  → takes screenshots of every state
  → logs crashes, broken flows, visual bugs
  → cross-references with flutter test results
UiPath Test Cloud:
  → executes unit tests
  → executes widget tests
  → executes integration tests
  → records pass/fail with evidence artifacts
        │
        ▼
STEP 4 — ── HUMAN GATE 1 ──
UiPath Action Center presents bug report to developer
  → list of all issues found with severity
  → screenshots as evidence
  → "Approve auto-fix attempt?" YES / NO
        │ (YES)
        ▼
STEP 5 — Fix Phase (Claude Code)
Claude Code agent:
  → reads every reported bug
  → writes code fixes
  → commits to branch: mopot/fix-{run-id}
  → opens a GitHub Pull Request
  → PR description explains every fix
        │
        ▼
STEP 6 — Retest Phase
Pipeline reruns full test suite on fixed build
If tests pass → proceed
If tests fail → loop back to Claude for another fix attempt (max 2 retries)
        │
        ▼
STEP 7 — ── HUMAN GATE 2 ──
UiPath Action Center presents results to developer
  → "All tests passing. Approve deployment?" YES / NO
  → Shows diff summary of what was fixed
        │ (YES)
        ▼
STEP 8 — Asset Generation Phase (Claude Code)
Claude Code agent generates:
  → Release notes (from git diff + commit messages)
  → Play Store short description
  → Play Store full description
  → Screenshots framed for all required device sizes
        │
        ▼
STEP 9 — Deployment Phase
Python deployer agent:
  → Uploads APK to Play Store via Google Play Developer API
  → Uploads screenshots
  → Submits release notes and metadata
  → Sets rollout to internal testing track
        │
        ▼
STEP 10 — Monitoring Phase
Maestro monitors Play Console submission status
  → Rejection → Maestro routes back to Claude with rejection reason
  → Approved → Pipeline complete
Developer notified via Action Center + Email
```

---

## 5. Architecture

```
┌──────────────────────────────────────────────────────┐
│             UiPath Automation Cloud                  │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │         Maestro BPMN Process                │    │
│  │  Trigger→Build→Test→Gate1→Fix→Retest→       │    │
│  │  Gate2→Assets→Deploy→Monitor                │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌──────────────────┐  ┌────────────────────────┐   │
│  │ UiPath Test Cloud│  │ UiPath Action Center   │   │
│  │ (test execution) │  │ (human approval gates) │   │
│  └──────────────────┘  └────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │       Orchestrator Credential Store          │   │
│  │  ANTHROPIC_API_KEY | GITHUB_TOKEN |          │   │
│  │  PLAY_STORE_JSON   | UIPATH_PAT   |          │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
                       │
                       │ calls via UiPath Robot
                       ▼
┌──────────────────────────────────────────────────────┐
│          Developer's Local Machine                   │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │         Python Agents                        │    │
│  │  tester_agent.py   (Claude Code)            │    │
│  │  fixer_agent.py    (Claude Code)            │    │
│  │  deployer_agent.py (Play Store API)         │    │
│  │  asset_agent.py    (screenshots + notes)    │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │         Platform Adapters                    │    │
│  │  android_adapter.py   ← ACTIVE (v1.0)       │    │
│  │  ios_adapter.py       ← STUB (future)       │    │
│  │  react_native_adapter.py ← STUB (future)    │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  Android Emulator + ADB + Flutter CLI               │
└──────────────────────────────────────────────────────┘
```

---

## 6. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| CLI | Node.js + Commander.js | `mopot init`, `mopot status`, `mopot run` |
| Setup UI | Express.js + HTML/CSS/JS | Local web config wizard at localhost:3420 |
| Orchestration | UiPath Maestro BPMN | Pipeline coordination + governance |
| Testing | UiPath Test Cloud | Formal test execution + results |
| Human Gates | UiPath Action Center | Approval UI + email notifications |
| Secrets | UiPath Orchestrator | Encrypted credential store |
| AI Brain | Claude Code (Anthropic API) | Testing, fixing, asset generation |
| Mobile Control | ADB + Android Emulator | App navigation + screenshot capture |
| Build | Flutter CLI | APK compilation + test execution |
| Version Control | GitHub API + Webhooks | Trigger pipeline + commit fixes as PR |
| Deployment | Google Play Developer API | Submit APK + metadata to Play Store |
| Language (agents) | Python 3.11+ | All agent logic |
| Containerization | Docker | Packages agent environment for UiPath Robot |

---

## 7. Repository Structure

```
mopot/
│
├── cli/                          # Node.js CLI
│   ├── index.js                  # Entry point — commander setup
│   ├── commands/
│   │   ├── init.js               # Opens setup wizard
│   │   ├── config.js             # Update existing config
│   │   ├── status.js             # Health check all connections
│   │   ├── run.js                # Manually trigger pipeline
│   │   └── logs.js               # Tail recent runs
│   └── server/
│       ├── app.js                # Express server for setup UI
│       └── public/
│           └── index.html        # Setup wizard UI
│
├── agents/                       # Python agents (run via UiPath Robot)
│   ├── tester_agent.py           # Claude Code — navigate + find bugs
│   ├── fixer_agent.py            # Claude Code — write fixes + open PR
│   ├── asset_agent.py            # Claude Code — release notes + screenshots
│   └── deployer_agent.py         # Play Store API submission
│
├── platforms/                    # Platform adapter layer
│   ├── base_adapter.py           # Abstract interface (DO NOT MODIFY)
│   ├── android_adapter.py        # Android/ADB — ACTIVE
│   ├── ios_adapter.py            # iOS — STUB, future implementation
│   └── react_native_adapter.py   # React Native — STUB, future implementation
│
├── uipath/                       # UiPath configuration
│   ├── maestro_process.json      # BPMN process definition
│   ├── test_cloud_config.json    # Test Cloud setup
│   └── agent_builder/            # UiPath Agent Builder configs
│
├── webhook/                      # GitHub webhook receiver
│   └── main.py                   # FastAPI server — receives push events
│
├── tests/
│   └── sample_flutter_app/       # Demo Flutter app for hackathon demo
│
├── Dockerfile                    # Packages agent environment
├── docker-compose.yml
├── requirements.txt              # Python dependencies
├── package.json                  # Node.js CLI dependencies
└── README.md
```

---

## 8. Platform Adapter Interface

This is the core design decision that makes Mopot extensible. Every platform must implement this interface. UiPath and Claude Code never interact with platform specifics directly — they talk to the adapter.

```python
# platforms/base_adapter.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class BuildResult:
    success: bool
    artifact_path: str
    build_log: str
    error: Optional[str] = None

@dataclass
class EmulatorSession:
    device_id: str
    platform: str
    is_running: bool

@dataclass
class ScreenshotResult:
    path: str
    screen_name: str
    timestamp: str

@dataclass
class CrashLog:
    timestamp: str
    error_type: str
    stack_trace: str
    screen: Optional[str] = None

@dataclass
class DeployResult:
    success: bool
    track: str
    version_code: int
    error: Optional[str] = None

class MobilePlatformAdapter(ABC):

    @abstractmethod
    def build(self, project_path: str, config: dict) -> BuildResult:
        """Build the app and return artifact path"""
        pass

    @abstractmethod
    def launch_emulator(self, device_config: dict) -> EmulatorSession:
        """Start emulator/simulator and return session"""
        pass

    @abstractmethod
    def install_app(self, session: EmulatorSession, artifact_path: str) -> bool:
        """Install app on running emulator"""
        pass

    @abstractmethod
    def take_screenshot(self, session: EmulatorSession, label: str) -> ScreenshotResult:
        """Capture current screen state"""
        pass

    @abstractmethod
    def tap(self, session: EmulatorSession, x: int, y: int) -> bool:
        """Simulate tap at coordinates"""
        pass

    @abstractmethod
    def get_crash_logs(self, session: EmulatorSession) -> List[CrashLog]:
        """Return all crashes since session start"""
        pass

    @abstractmethod
    def run_tests(self, project_path: str) -> dict:
        """Execute test suite and return results"""
        pass

    @abstractmethod
    def deploy(self, artifact_path: str, store_config: dict) -> DeployResult:
        """Submit build to app store"""
        pass

    @abstractmethod
    def teardown(self, session: EmulatorSession) -> bool:
        """Stop emulator and clean up"""
        pass
```

---

## 9. CLI Commands

```bash
# Install globally
npm install -g mopot

# First-time setup — opens browser UI at localhost:3420
mopot init

# Update existing credentials
mopot config

# Check all connections are healthy
mopot status

# Manually trigger pipeline on current directory's repo
mopot run

# Tail recent pipeline run logs
mopot logs

# Show current version
mopot --version
```

---

## 10. Setup Wizard — User Experience

When the user runs `mopot init`, the CLI:

1. Finds a free port (default 3420, scans up if taken)
2. Spins up a temporary Express server
3. Opens `http://localhost:{port}` in the default browser
4. Displays a 5-step configuration wizard

**Step 1 — UiPath Connection**
- UiPath Cloud Account URL (e.g. `https://cloud.uipath.com/yourorg`)
- UiPath Personal Access Token
- ✅ "Test Connection" button — validates immediately

**Step 2 — Anthropic API Key**
- API Key field (masked input)
- ✅ "Test Connection" — makes a lightweight API call to verify
- Link: *"Get your key at console.anthropic.com"*

**Step 3 — GitHub**
- GitHub Personal Access Token (needs `repo` scope)
- ✅ "Test Connection" — calls GitHub `/user` endpoint
- Link: *"Generate at github.com/settings/tokens"*

**Step 4 — Google Play Store**
- File upload input for Service Account JSON
- ✅ "Validate JSON" — checks required fields are present
- Link: *"See guide below for how to get this file"*

**Step 5 — Project Setup**
- Flutter project path or GitHub repo URL
- Default branch name
- Play Store package name (e.g. `com.example.myapp`)
- ✅ "Verify Flutter Project" — checks pubspec.yaml exists

On final submit:
- CLI stores UiPath PAT locally in `~/.mopot/config.json` (encrypted)
- All other secrets pushed to UiPath Orchestrator via API
- Local server shuts down
- Terminal prints: `✅ Mopot is ready. Pipeline will trigger on your next push.`

---

## 11. Where to Get Every Key

### 11.1 Anthropic API Key

**What it's for:** Claude Code calls (testing, fixing, asset generation)

**Steps:**
1. Go to `https://console.anthropic.com`
2. Sign in or create an account
3. Navigate to **API Keys** in the left sidebar
4. Click **Create Key**
5. Name it `mopot-pipeline`
6. Copy the key immediately — it is only shown once
7. Ensure your account has a payment method added (pay-per-use billing)

**Format:** `sk-ant-api03-...`

**Estimated cost per pipeline run:** ~$0.10–$0.40 depending on codebase size

---

### 11.2 UiPath Personal Access Token (PAT)

**What it's for:** CLI authenticates to UiPath Automation Cloud to store secrets and trigger pipelines

**Steps:**
1. Go to `https://cloud.uipath.com`
2. Sign in (free Community Edition is sufficient for hackathon)
3. Click your profile icon → **My Profile**
4. Navigate to **Access Tokens** tab
5. Click **Generate New Token**
6. Name: `mopot-cli`
7. Expiry: 1 year
8. Scopes: select `OR.Execution`, `OR.Assets`, `OR.Settings`
9. Click **Generate** — copy immediately

**Format:** `rt_...`

---

### 11.3 GitHub Personal Access Token

**What it's for:** Read repo, commit fixes, open Pull Requests

**Steps:**
1. Go to `https://github.com/settings/tokens`
2. Click **Generate new token (classic)**
3. Name: `mopot-pipeline`
4. Expiry: 1 year
5. Scopes: check `repo` (full repo access — required for PR creation)
6. Click **Generate token** — copy immediately

**Format:** `ghp_...`

---

### 11.4 Google Play Service Account JSON

**What it's for:** Programmatic deployment to Play Store

**Steps:**
1. Go to `https://console.cloud.google.com`
2. Create a new project or select existing
3. Navigate to **IAM & Admin → Service Accounts**
4. Click **Create Service Account**
5. Name: `mopot-deployer`
6. Click **Create and Continue**
7. Skip role assignment for now → click **Done**
8. Click on the newly created service account
9. Go to **Keys** tab → **Add Key → Create new key**
10. Select **JSON** → click **Create**
11. JSON file downloads automatically — this is your credential file

**Then link to Play Console:**
1. Go to `https://play.google.com/console`
2. Navigate to **Setup → API access**
3. Click **Link to a Google Cloud Project** → select the project you just used
4. Under **Service Accounts**, you should see `mopot-deployer`
5. Click **Grant Access**
6. Assign role: **Release Manager**
7. Click **Invite user**

**Upload this JSON file in Mopot's setup wizard Step 4.**

---

### 11.5 UiPath Robot — Local Installation

**What it's for:** Runs Python agents on your machine, orchestrated by UiPath Cloud

**Steps:**
1. Go to `https://cloud.uipath.com`
2. Navigate to **Automation → Robots**
3. Click **Add Robot → Unattended Robot**
4. Give it a name: `mopot-local`
5. Download **UiPath Assistant** for your OS from `https://www.uipath.com/developers/community-edition-download`
6. Install it
7. Open UiPath Assistant → click **Sign In**
8. Sign in with your UiPath Cloud account
9. Robot will appear as connected in your Cloud console

---

## 12. Environment Variables Reference

All secrets are stored in UiPath Orchestrator and injected at runtime. Never commit these to Git.

```bash
# Injected by UiPath Orchestrator into Python agents at runtime
ANTHROPIC_API_KEY=sk-ant-api03-...
GITHUB_TOKEN=ghp_...
PLAY_STORE_JSON_PATH=/tmp/mopot/play_store_credentials.json
FLUTTER_PROJECT_PATH=/path/to/project
GITHUB_REPO=owner/repo-name
GITHUB_DEFAULT_BRANCH=main
PLAY_STORE_PACKAGE_NAME=com.example.yourapp

# UiPath connection (stored locally in ~/.mopot/config.json)
UIPATH_ACCOUNT_URL=https://cloud.uipath.com/yourorg
UIPATH_PAT=rt_...
UIPATH_TENANT_NAME=DefaultTenant
UIPATH_FOLDER_NAME=Mopot
```

---

## 13. Judging Criteria Mapping

| Criterion | How Mopot Addresses It |
|---|---|
| Business Impact | Every mobile dev team has this pain. Saves 3–6 hours per release. Immediate ROI story. |
| Platform Usage | Maestro BPMN + Test Cloud + Action Center + Orchestrator Credential Store + Robot + Claude Code (bonus points) |
| Technical Execution | Platform adapter pattern, retry logic, human gates, exception handling at every step |
| Completeness | End-to-end: push → test → fix → deploy. Full GitHub repo + README + demo video. |
| Creativity | Only mobile-native testing pipeline in the submissions. Everyone else builds CRUD workflows. |
| Presentation | Live demo on a real Flutter app. Clear before/after story. |
| Coding Agents Bonus | Claude Code is the primary agent for testing, fixing, and asset generation |

---

## 14. Submission Checklist

- [ ] Devpost project page with description, screenshots, track selection
- [ ] Demo video (max 5 minutes) on YouTube — shows pipeline running end to end
- [ ] Public GitHub repository with MIT license
- [ ] README with setup instructions, UiPath components list, prerequisites
- [ ] Solution running on UiPath Automation Cloud
- [ ] Presentation deck (UiPath template from bit.ly/3R0MsHU)
- [ ] Optional: Product feedback form for Best Product Feedback award ($1,500)

---

## 15. MVP Scope for Hackathon

Build these. Nothing else.

**In scope (v1.0 — hackathon):**
- CLI with `init`, `status`, `run`, `logs`
- Setup wizard UI (localhost)
- Android adapter (ADB + emulator)
- Claude Code tester agent
- Claude Code fixer agent (opens PR)
- UiPath Test Cloud integration (flutter test)
- UiPath Action Center gates (2 approval points)
- Play Store deployment agent
- GitHub webhook trigger
- Release notes generation

**Out of scope (post-hackathon):**
- iOS adapter
- React Native adapter
- Multi-project support
- Team/organization accounts
- Dashboard web UI
- Slack notifications
- Custom test configuration

---

## 16. Instructions for Claude Code

> The following is a prompt you can give directly to Claude Code to start building.

---

**PROMPT FOR CLAUDE CODE:**

```
You are building Mopot — an autonomous mobile release pipeline agent.
Read this entire document before writing any code.

Tech context:
- CLI: Node.js + Commander.js
- Agents: Python 3.11+
- AI calls: Anthropic API (ANTHROPIC_API_KEY env var)
- Orchestration: UiPath Automation Cloud (do not build this — configure via UI)
- Mobile: ADB + Android Emulator + Flutter CLI
- Deployment: Google Play Developer API (google-api-python-client)

Start with this order:
1. Scaffold the repo structure exactly as defined in Section 7
2. Implement platforms/base_adapter.py exactly as defined in Section 8
3. Implement platforms/android_adapter.py — a full working implementation of base_adapter.py using ADB commands and Flutter CLI
4. Implement platforms/ios_adapter.py as a STUB — every method raises NotImplementedError with a clear message
5. Implement platforms/react_native_adapter.py as a STUB — same pattern
6. Implement agents/tester_agent.py — uses ANTHROPIC_API_KEY, receives flutter project path, launches the android adapter, navigates the app, captures screenshots, returns a structured bug report as JSON
7. Implement agents/fixer_agent.py — receives bug report JSON + project path, uses Claude to write fixes, commits to branch mopot/fix-{run_id}, opens GitHub PR using GITHUB_TOKEN
8. Implement webhook/main.py — FastAPI server that receives GitHub push webhooks and triggers the pipeline
9. Implement cli/index.js and cli/commands/ — all 5 commands
10. Implement cli/server/app.js and cli/server/public/index.html — setup wizard

Rules:
- Never hardcode any API keys or secrets
- Always read secrets from environment variables
- The platform adapter interface in base_adapter.py must never be modified
- Every agent must handle exceptions gracefully and return structured error JSON
- Every file must have a module-level docstring explaining what it does
- Use type hints everywhere in Python
- Follow this exactly — do not improvise the structure
```

---

*Document version 1.0 — Daniel Ainoko / thecodedaniel*  
*Built for UiPath AgentHack 2026 — Track 3: UiPath Test Cloud*