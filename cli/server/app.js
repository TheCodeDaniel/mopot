import { exec as execCb } from 'child_process';
import express from 'express';
import fs from 'fs-extra';
import axios from 'axios';
import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';
import { promisify } from 'util';

const exec = promisify(execCb);
const __dirname = path.dirname(fileURLToPath(import.meta.url));

const CONFIG_PATH = path.join(os.homedir(), '.mopot', 'config.json');

// Default Android SDK root per platform
function sdkRoot() {
  const env = process.env.ANDROID_SDK_ROOT || process.env.ANDROID_HOME;
  if (env) return env;
  const p = os.platform();
  if (p === 'darwin') return path.join(os.homedir(), 'Library', 'Android', 'sdk');
  if (p === 'win32')  return path.join(os.homedir(), 'AppData', 'Local', 'Android', 'Sdk');
  return path.join(os.homedir(), 'Android', 'Sdk'); // linux
}

export function createWizardServer() {
  const app = express();
  app.use(express.json());
  app.use(express.static(path.join(__dirname, 'public')));

  app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
  });

  // ── UiPath connection ──────────────────────────────────────────────────────
  // PATs (rt_...) are used directly as Bearer tokens against org-scoped endpoints.
  // Ref: https://docs.uipath.com/automation-cloud/latest/api-guide/personal-access-tokens
  app.post('/test-uipath', async (req, res) => {
    const { accountUrl, pat } = req.body;
    try {
      const orgName = accountUrl.replace(/\/$/, '').split('/').pop();
      const resp = await axios.get(
        `https://cloud.uipath.com/${orgName}/identity_/connect/userinfo`,
        { headers: { Authorization: `Bearer ${pat}` }, timeout: 10000 }
      );
      const name = resp.data.name || resp.data.email || 'authenticated';
      res.json({ ok: true, name });
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.error_description || err.response?.data?.error || err.message;
      if (status === 401) return res.json({ ok: false, error: 'PAT rejected — check token scopes and expiry' });
      if (status === 404) return res.json({ ok: false, error: 'Organisation not found — check your Account URL' });
      res.json({ ok: false, error: detail });
    }
  });

  // ── Anthropic API key ──────────────────────────────────────────────────────
  app.post('/test-anthropic', async (req, res) => {
    const { apiKey } = req.body;
    try {
      await axios.post(
        'https://api.anthropic.com/v1/messages',
        { model: 'claude-haiku-4-5-20251001', max_tokens: 10, messages: [{ role: 'user', content: 'hi' }] },
        { headers: { 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' }, timeout: 10000 }
      );
      res.json({ ok: true });
    } catch (err) {
      const status = err.response?.status;
      res.json({ ok: status === 400 || status === 200, error: status === 401 ? 'Invalid API key' : null });
    }
  });

  // ── GitHub token ───────────────────────────────────────────────────────────
  app.post('/test-github', async (req, res) => {
    const { token } = req.body;
    try {
      const resp = await axios.get('https://api.github.com/user', {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 8000,
      });
      res.json({ ok: true, login: resp.data.login });
    } catch (err) {
      res.json({ ok: false, error: err.message });
    }
  });

  // ── Native folder picker ───────────────────────────────────────────────────
  // Opens the OS-native folder dialog and returns the selected path.
  // macOS: osascript  |  Windows: PowerShell  |  Linux: zenity → kdialog → tkinter
  app.post('/pick-folder', async (req, res) => {
    const platform = os.platform();
    try {
      let folderPath = null;

      if (platform === 'darwin') {
        const { stdout } = await exec(
          `osascript -e 'POSIX path of (choose folder with prompt "Select your Flutter project folder")'`,
          { timeout: 120000 }
        );
        folderPath = stdout.trim().replace(/\/$/, '');

      } else if (platform === 'win32') {
        const ps = [
          'Add-Type -AssemblyName System.Windows.Forms',
          '$f = New-Object System.Windows.Forms.FolderBrowserDialog',
          '$f.Description = "Select your Flutter project folder"',
          'if ($f.ShowDialog() -eq "OK") { Write-Output $f.SelectedPath }',
        ].join('; ');
        const { stdout } = await exec(`powershell -NoProfile -Command "${ps}"`, { timeout: 120000 });
        folderPath = stdout.trim();

      } else {
        // Linux: try zenity, kdialog, then tkinter
        const cmds = [
          `zenity --file-selection --directory --title='Select Flutter project folder'`,
          `kdialog --getexistingdirectory "$HOME"`,
          `python3 -c "import tkinter; from tkinter import filedialog; r=tkinter.Tk(); r.withdraw(); v=filedialog.askdirectory(title='Select Flutter project folder'); print(v) if v else exit(1)"`,
        ];
        let found = false;
        for (const cmd of cmds) {
          try {
            const { stdout } = await exec(cmd, { timeout: 120000 });
            folderPath = stdout.trim();
            if (folderPath) { found = true; break; }
          } catch { continue; }
        }
        if (!found) {
          return res.json({ ok: false, error: 'No folder picker available — install zenity or kdialog, or type the path manually.' });
        }
      }

      if (!folderPath) return res.json({ ok: false, error: 'cancelled' });
      res.json({ ok: true, path: folderPath });
    } catch (err) {
      // osascript exits 1 when user clicks Cancel
      const msg = (err.stderr || err.message || '').toLowerCase();
      if (msg.includes('cancel') || err.code === 1) return res.json({ ok: false, error: 'cancelled' });
      res.json({ ok: false, error: err.message });
    }
  });

  // ── List installed Android emulators ──────────────────────────────────────
  app.get('/list-avds', async (req, res) => {
    const platform = os.platform();
    const emulatorBin = path.join(sdkRoot(), 'emulator', platform === 'win32' ? 'emulator.exe' : 'emulator');

    const parse = (stdout) =>
      stdout.trim().split('\n')
        .map(l => l.trim())
        .filter(l => l && !l.startsWith('INFO') && !l.startsWith('WARNING'));

    for (const cmd of [`"${emulatorBin}" -list-avds`, 'emulator -list-avds']) {
      try {
        const { stdout } = await exec(cmd, { timeout: 10000 });
        const avds = parse(stdout);
        return res.json({ ok: true, avds });
      } catch { continue; }
    }
    res.json({ ok: true, avds: [] });
  });

  // ── Detect git default branch ──────────────────────────────────────────────
  app.post('/detect-branch', async (req, res) => {
    const { projectPath } = req.body;
    if (!projectPath) return res.json({ ok: false });
    try {
      // Current HEAD branch
      const { stdout } = await exec(`git -C "${projectPath}" rev-parse --abbrev-ref HEAD`, { timeout: 5000 });
      const branch = stdout.trim();
      if (branch && branch !== 'HEAD') return res.json({ ok: true, branch });
      // Fallback: remote default
      const { stdout: ref } = await exec(`git -C "${projectPath}" symbolic-ref refs/remotes/origin/HEAD`, { timeout: 5000 });
      const b = ref.trim().replace('refs/remotes/origin/', '');
      res.json({ ok: true, branch: b || 'main' });
    } catch {
      res.json({ ok: false });
    }
  });

  // ── Verify Flutter project ─────────────────────────────────────────────────
  app.post('/verify-flutter', async (req, res) => {
    const { projectPath } = req.body;
    const pubspec = path.join(projectPath, 'pubspec.yaml');
    const exists = await fs.pathExists(pubspec);
    res.json({ ok: exists, error: exists ? null : 'pubspec.yaml not found at that path' });
  });

  // ── Save config and shut down ──────────────────────────────────────────────
  app.post('/save-config', async (req, res) => {
    const config = req.body;
    await fs.ensureDir(path.dirname(CONFIG_PATH));
    await fs.writeJson(CONFIG_PATH, config, { spaces: 2 });
    res.json({ ok: true });
    setTimeout(() => process.emit('SIGTERM'), 500);
  });

  return app;
}
