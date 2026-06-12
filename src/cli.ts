#!/usr/bin/env node

import { Command } from 'commander';
import { loadConfig } from './config/loader.js';
import { startServer } from './server.js';
import { runInit } from './commands/init.js';

const program = new Command();

program
  .name('siyuan-mcp-bridge')
  .description('MCP server bridging Claude/any AI with SiYuan Note')
  .version('0.2.0');

// 全局连接选项
program
  .option('--token <token>', 'SiYuan API token')
  .option('--port <port>', 'SiYuan API port', (v) => v)
  .option('--host <host>', 'SiYuan API host')
  .option('--rg-path <path>', 'ripgrep binary path')
  .option('--max-results <n>', 'Max search results', (v) => v);

// init 子命令
program
  .command('init')
  .description('Generate config interactively')
  .action(runInit);

// 默认命令：启动 MCP server
program.action(async (options) => {
  const config = loadConfig(options);
  await startServer(config);
});

program.parse();
