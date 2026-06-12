#!/usr/bin/env node
import('../dist/cli.js').catch(err => {
  console.error('Failed to load siyuan-mcp-bridge:', err.message);
  process.exit(1);
});
