import { Command } from 'commander';
import chalk from 'chalk';
import ora from 'ora';
import axios from 'axios';
import fs from 'fs-extra';
import path from 'path';
import os from 'os';

const CONFIG_PATH = path.join(os.homedir(), '.mopot', 'config.json');
const MOPOT_PORT = process.env.MOPOT_PORT || 7432;

async function checkServer() {
  try {
    const res = await axios.get(`http://localhost:${MOPOT_PORT}/health`, { timeout: 3000 });
    return { ok: true, detail: `v${res.data.version}` };
  } catch {
    return { ok: false, detail: 'not running' };
  }
}

async function checkGitHub(token) {
  if (!token) return { ok: false, detail: 'no token in config' };
  try {
    const res = await axios.get('https://api.github.com/user', {
      headers: { Authorization: `Bearer ${token}` },
      timeout: 5000,
    });
    return { ok: true, detail: `@${res.data.login}` };
  } catch {
    return { ok: false, detail: 'invalid token' };
  }
}

async function checkAnthropic(apiKey) {
  if (!apiKey) return { ok: false, detail: 'no key in config' };
  return { ok: true, detail: 'key present (not verified)' };
}

function fmt(label, { ok, detail }) {
  const icon = ok ? chalk.green('✅') : chalk.red('❌');
  const text = ok ? chalk.white(label) : chalk.gray(label);
  return `  ${icon}  ${text.padEnd(22)} ${chalk.gray(detail)}`;
}

const statusCommand = new Command('status')
  .description('Check all Mopot connections')
  .action(async () => {
    const spinner = ora('Checking connections...').start();

    let config = {};
    try {
      config = await fs.readJson(CONFIG_PATH);
    } catch {
      // config may not exist yet
    }

    const [server, github, anthropic] = await Promise.allSettled([
      checkServer(),
      checkGitHub(config.githubToken),
      checkAnthropic(config.anthropicKey),
    ]);

    const results = [server, github, anthropic].map(r =>
      r.status === 'fulfilled' ? r.value : { ok: false, detail: r.reason?.message || 'error' }
    );

    spinner.stop();
    console.log(chalk.bold('\nMopot Status\n'));
    console.log(fmt('Pipeline Server', results[0]));
    console.log(fmt('GitHub', results[1]));
    console.log(fmt('Anthropic', results[2]));
    console.log();

    const allOk = results.every(r => r.ok);
    if (allOk) {
      console.log(chalk.green('All systems go. 🚀'));
    } else {
      console.log(chalk.yellow('Some checks failed. Run `mopot init` to configure.'));
    }
  });

export default statusCommand;
