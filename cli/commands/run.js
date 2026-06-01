import { Command } from 'commander';
import chalk from 'chalk';
import ora from 'ora';
import axios from 'axios';

const MOPOT_PORT = process.env.MOPOT_PORT || 7432;

const runCommand = new Command('run')
  .description('Manually trigger the pipeline on the current project')
  .option('-p, --project <path>', 'Flutter project path', process.cwd())
  .option('-b, --branch <branch>', 'Branch name', 'main')
  .action(async (options) => {
    const spinner = ora('Triggering pipeline...').start();
    try {
      const res = await axios.post(
        `http://localhost:${MOPOT_PORT}/trigger`,
        { project_path: options.project, branch: options.branch },
        { headers: { 'content-type': 'application/json' }, timeout: 10000 }
      );
      spinner.succeed(`Pipeline started — run ID: ${chalk.cyan(res.data.run_id)}`);
      console.log(chalk.gray(`\nTrack progress: mopot logs --follow ${res.data.run_id}`));
    } catch (err) {
      spinner.fail('Failed to trigger pipeline');
      if (err.code === 'ECONNREFUSED') {
        console.error(chalk.red('Pipeline server is not running.'));
        console.error(chalk.gray('Start it with: uvicorn webhook.main:app --port ' + MOPOT_PORT));
      } else {
        console.error(chalk.red(err.message));
      }
      process.exit(1);
    }
  });

export default runCommand;
