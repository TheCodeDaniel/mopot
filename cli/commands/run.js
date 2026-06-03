import { Command } from 'commander';
import chalk from 'chalk';
import ora from 'ora';
import axios from 'axios';
import fs from 'fs-extra';
import path from 'path';
import os from 'os';

const MOPOT_PORT = process.env.MOPOT_PORT || 7432;
const CONFIG_PATH = path.join(os.homedir(), '.mopot', 'config.json');

const runCommand = new Command('run')
  .description('Manually trigger the pipeline on the configured Flutter project')
  .option('-p, --project <path>', 'Override Flutter project path')
  .option('-b, --branch <branch>', 'Override branch name')
  .action(async (options) => {
    let config = {};
    try {
      config = await fs.readJson(CONFIG_PATH);
    } catch {
      // config may not exist yet — will rely on CLI flags or fail with a clear message
    }

    const projectPath = options.project
      || config.flutterProjectPath
      || process.env.FLUTTER_PROJECT_PATH;

    const branch = options.branch
      || config.defaultBranch
      || 'main';

    const repo = config.githubRepo || process.env.GITHUB_REPO || '';

    if (!projectPath) {
      console.error(chalk.red('\nNo Flutter project path found.'));
      console.error(chalk.gray('Run `mopot init` to configure it, or pass it directly:'));
      console.error(chalk.gray('  mopot run --project /path/to/your/flutter/app'));
      process.exit(1);
    }

    const spinner = ora(`Triggering pipeline on ${chalk.cyan(projectPath)}...`).start();
    try {
      const res = await axios.post(
        `http://localhost:${MOPOT_PORT}/trigger`,
        { project_path: projectPath, branch, repo },
        { headers: { 'content-type': 'application/json' }, timeout: 10000 }
      );
      spinner.succeed(`Pipeline started — run ID: ${chalk.cyan(res.data.run_id)}`);
      console.log(chalk.gray(`\nTrack progress: mopot logs --follow ${res.data.run_id}`));
    } catch (err) {
      spinner.fail('Failed to trigger pipeline');
      if (err.code === 'ECONNREFUSED') {
        console.error(chalk.red('\nPipeline server is not running.'));
        console.error(chalk.gray('Start it with: uvicorn webhook.main:app --port ' + MOPOT_PORT));
      } else {
        console.error(chalk.red(err.message));
      }
      process.exit(1);
    }
  });

export default runCommand;
