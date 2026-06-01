import { Command } from 'commander';
import chalk from 'chalk';
import fs from 'fs-extra';
import path from 'path';
import os from 'os';

const RUNS_DIR = path.join(os.homedir(), '.mopot', 'runs');

const STATUS_COLOR = {
  queued:     chalk.gray,
  building:   chalk.yellow,
  testing:    chalk.blue,
  fixing:     chalk.magenta,
  rebuilding: chalk.yellow,
  assets:     chalk.cyan,
  deploying:  chalk.cyan,
  complete:   chalk.green,
  failed:     chalk.red,
};

function colorStatus(status) {
  const fn = STATUS_COLOR[status] || chalk.white;
  return fn(status.padEnd(12));
}

function fmtTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString();
}

async function readRuns(filter) {
  if (!await fs.pathExists(RUNS_DIR)) return [];
  const files = (await fs.readdir(RUNS_DIR))
    .filter(f => f.endsWith('.json'))
    .sort()
    .reverse()
    .slice(0, 20);

  const runs = [];
  for (const f of files) {
    try {
      const data = await fs.readJson(path.join(RUNS_DIR, f));
      if (!filter || data.run_id === filter || data.run_id?.startsWith(filter)) {
        runs.push(data);
      }
    } catch {}
  }
  return runs;
}

const logsCommand = new Command('logs')
  .description('Show recent pipeline run logs')
  .argument('[run-id]', 'Show details for a specific run')
  .option('-f, --follow', 'Poll for updates every 2 seconds')
  .action(async (runId, options) => {
    async function display() {
      const runs = await readRuns(runId);

      if (runs.length === 0) {
        console.log(chalk.gray('No runs found.'));
        return;
      }

      if (runId && runs.length === 1) {
        // Detailed view for a single run
        const r = runs[0];
        console.clear();
        console.log(chalk.bold(`Run: ${r.run_id}`));
        console.log(`Status:  ${colorStatus(r.status)}`);
        console.log(`Started: ${fmtTime(r.started_at)}`);
        console.log(`Updated: ${fmtTime(r.updated_at)}`);
        console.log(`Repo:    ${chalk.gray(r.repo || '—')}`);
        console.log(`Branch:  ${chalk.gray(r.branch || '—')}`);
        if (r.fix_pr_url) console.log(`PR:      ${chalk.cyan(r.fix_pr_url)}`);
        if (r.error) console.log(`\n${chalk.red('Error:')} ${r.error}`);
        if (r.bug_report?.bugs?.length) {
          console.log(`\n${chalk.bold('Bugs found:')} ${r.bug_report.bugs.length}`);
          r.bug_report.bugs.slice(0, 5).forEach(b =>
            console.log(`  [${b.severity}] ${b.description?.slice(0, 80)}`)
          );
        }
      } else {
        // List view
        console.clear();
        console.log(chalk.bold('Recent Runs\n'));
        console.log(
          chalk.gray('RUN ID'.padEnd(14) + 'STATUS'.padEnd(14) + 'BRANCH'.padEnd(20) + 'STARTED')
        );
        runs.forEach(r => {
          console.log(
            r.run_id.padEnd(14) +
            colorStatus(r.status) +
            (r.branch || '—').padEnd(20) +
            chalk.gray(fmtTime(r.started_at))
          );
        });
      }
    }

    await display();

    if (options.follow) {
      const interval = setInterval(display, 2000);
      process.on('SIGINT', () => { clearInterval(interval); process.exit(0); });
    }
  });

export default logsCommand;
