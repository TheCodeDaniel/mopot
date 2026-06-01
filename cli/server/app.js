import express from 'express';
import { createServer } from 'http';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs-extra';
import axios from 'axios';
import os from 'os';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const CONFIG_PATH = path.join(os.homedir(), '.mopot', 'config.json');

export function createWizardServer() {
  const app = express();
  app.use(express.json());
  app.use(express.static(path.join(__dirname, 'public')));

  app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
  });

  // Test UiPath connection
  app.post('/test-uipath', async (req, res) => {
    const { accountUrl, pat } = req.body;
    try {
      const url = accountUrl.replace(/\/$/, '') + '/identity_/connect/token';
      await axios.post(url, new URLSearchParams({
        grant_type: 'refresh_token',
        client_id: 'fc48a73a-3b19-4089-80b0-e48c55440d37',
        refresh_token: pat,
      }), { timeout: 8000 });
      res.json({ ok: true });
    } catch (err) {
      res.json({ ok: false, error: err.message });
    }
  });

  // Test Anthropic API key
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
      // 200 or 400 (bad request body) both mean the key is valid
      res.json({ ok: status === 400 || status === 200, error: status === 401 ? 'Invalid API key' : null });
    }
  });

  // Test GitHub token
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

  // Validate Play Store JSON
  app.post('/validate-play-json', async (req, res) => {
    const { content } = req.body;
    try {
      const parsed = JSON.parse(content);
      const required = ['type', 'project_id', 'client_email', 'private_key'];
      const missing = required.filter(k => !parsed[k]);
      if (missing.length > 0) {
        return res.json({ ok: false, error: `Missing fields: ${missing.join(', ')}` });
      }
      if (parsed.type !== 'service_account') {
        return res.json({ ok: false, error: 'type must be "service_account"' });
      }
      res.json({ ok: true, client_email: parsed.client_email });
    } catch {
      res.json({ ok: false, error: 'Invalid JSON' });
    }
  });

  // Verify Flutter project
  app.post('/verify-flutter', async (req, res) => {
    const { projectPath } = req.body;
    const pubspec = path.join(projectPath, 'pubspec.yaml');
    const exists = await fs.pathExists(pubspec);
    res.json({ ok: exists, error: exists ? null : 'pubspec.yaml not found at that path' });
  });

  // Save config and shut down server
  app.post('/save-config', async (req, res) => {
    const config = req.body;
    await fs.ensureDir(path.dirname(CONFIG_PATH));
    await fs.writeJson(CONFIG_PATH, config, { spaces: 2 });
    res.json({ ok: true });
    // Graceful shutdown after response is sent
    setTimeout(() => process.emit('SIGTERM'), 500);
  });

  return app;
}
