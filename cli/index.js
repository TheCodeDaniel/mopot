#!/usr/bin/env node
import { Command } from 'commander';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';

import initCommand from './commands/init.js';
import configCommand from './commands/config.js';
import statusCommand from './commands/status.js';
import runCommand from './commands/run.js';
import logsCommand from './commands/logs.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8'));

const program = new Command();

program
  .name('mopot')
  .description('Autonomous mobile release pipeline — push code, Mopot ships it.')
  .version(pkg.version);

program.addCommand(initCommand);
program.addCommand(configCommand);
program.addCommand(statusCommand);
program.addCommand(runCommand);
program.addCommand(logsCommand);

program.parse();
