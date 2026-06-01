import { Command } from 'commander';
import { createServer } from 'http';
import net from 'net';
import chalk from 'chalk';
import ora from 'ora';
import open from 'open';
import { createWizardServer } from '../server/app.js';

function findFreePort(start = 3420) {
  return new Promise((resolve) => {
    let p = start;
    function tryPort() {
      const s = net.createServer();
      s.once('error', () => { p++; tryPort(); });
      s.once('listening', () => { s.close(() => resolve(p)); });
      s.listen(p);
    }
    tryPort();
  });
}

const initCommand = new Command('init')
  .description('Run the Mopot setup wizard (opens browser UI)')
  .action(async () => {
    const spinner = ora('Starting setup wizard...').start();
    const port = await findFreePort(3420);

    const app = createWizardServer();
    const server = createServer(app);

    server.listen(port, () => {
      spinner.succeed(`Setup wizard running at ${chalk.cyan(`http://localhost:${port}`)}`);
      console.log(chalk.gray('Complete all 5 steps in the browser, then return here.'));
      open(`http://localhost:${port}`);
    });

    process.on('SIGTERM', () => {
      server.close(() => {
        console.log(chalk.green('\n✅ Mopot is ready. Pipeline will trigger on your next push.'));
        process.exit(0);
      });
    });
  });

export default initCommand;
