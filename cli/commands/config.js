import { Command } from 'commander';
import { createServer } from 'http';
import net from 'net';
import chalk from 'chalk';
import open from 'open';
import { createWizardServer } from '../server/app.js';

function findFreePort(start = 3421) {
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

const configCommand = new Command('config')
  .description('Update Mopot credentials and project settings')
  .action(async () => {
    const port = await findFreePort(3421);
    const app = createWizardServer();
    const server = createServer(app);

    server.listen(port, () => {
      console.log(chalk.cyan(`\nOpening config wizard at http://localhost:${port}`));
      open(`http://localhost:${port}`);
    });

    process.on('SIGTERM', () => {
      server.close(() => {
        console.log(chalk.green('\n✅ Configuration updated.'));
        process.exit(0);
      });
    });
  });

export default configCommand;
