#!/usr/bin/env node
const { spawn } = require('child_process');
const child = spawn('python', ['-m', 'siyuan_mcp'], { stdio: 'inherit' });
child.on('exit', code => process.exit(code ?? 0));
