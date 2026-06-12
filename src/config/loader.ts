import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import yaml from 'yaml';
import { Config, CodebaseRepo, DEFAULTS } from './index.js';

/** CLI 参数接口 */
export interface CliArgs {
  token?: string;
  port?: string;
  host?: string;
  rgPath?: string;
  maxResults?: string;
}

/**
 * 深度合并对象（仅普通对象递归，数组直接替换）
 */
function deepMerge(base: Record<string, unknown>, override: Record<string, unknown>): Record<string, unknown> {
  const result = { ...base };
  for (const [key, val] of Object.entries(override)) {
    if (
      val !== null &&
      typeof val === 'object' &&
      !Array.isArray(val) &&
      typeof result[key] === 'object' &&
      result[key] !== null &&
      !Array.isArray(result[key])
    ) {
      result[key] = deepMerge(result[key] as Record<string, unknown>, val as Record<string, unknown>);
    } else {
      result[key] = val;
    }
  }
  return result;
}

/**
 * 查找配置文件路径
 * 搜索顺序：cwd/config.yaml > cwd/config.yml > ~/.siyuan-mcp/config.yaml
 */
function findConfigPath(): string | null {
  const candidates = [
    path.join(process.cwd(), 'config.yaml'),
    path.join(process.cwd(), 'config.yml'),
    path.join(os.homedir(), '.siyuan-mcp', 'config.yaml'),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}

/**
 * 应用环境变量覆盖
 */
function applyEnvOverrides(raw: Record<string, unknown>): Record<string, unknown> {
  const env = process.env;

  if (env.SIYUAN_HOST) {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const siyuan = raw.siyuan as Record<string, unknown> || {};
    siyuan.host = env.SIYUAN_HOST;
    raw.siyuan = siyuan;
  }
  if (env.SIYUAN_PORT) {
    const siyuan = raw.siyuan as Record<string, unknown> || {};
    siyuan.port = parseInt(env.SIYUAN_PORT, 10);
    raw.siyuan = siyuan;
  }
  if (env.SIYUAN_TOKEN) {
    const siyuan = raw.siyuan as Record<string, unknown> || {};
    siyuan.token = env.SIYUAN_TOKEN;
    raw.siyuan = siyuan;
  }
  if (env.SEARCH_MAX_RESULTS) {
    const search = raw.search as Record<string, unknown> || {};
    search.maxResults = parseInt(env.SEARCH_MAX_RESULTS, 10);
    raw.search = search;
  }
  if (env.CODEBASE_REPOS) {
    try {
      raw.codebase = { repos: JSON.parse(env.CODEBASE_REPOS) as CodebaseRepo[] };
    } catch {
      // 忽略无效 JSON
    }
  }

  return raw;
}

/**
 * 应用 CLI 参数覆盖（最高优先级）
 */
function applyCliOverrides(raw: Record<string, unknown>, cli: CliArgs): Record<string, unknown> {
  if (cli.host) {
    const siyuan = raw.siyuan as Record<string, unknown> || {};
    siyuan.host = cli.host;
    raw.siyuan = siyuan;
  }
  if (cli.port) {
    const siyuan = raw.siyuan as Record<string, unknown> || {};
    siyuan.port = parseInt(cli.port, 10);
    raw.siyuan = siyuan;
  }
  if (cli.token !== undefined) {
    const siyuan = raw.siyuan as Record<string, unknown> || {};
    siyuan.token = cli.token;
    raw.siyuan = siyuan;
  }
  if (cli.rgPath) {
    const search = raw.search as Record<string, unknown> || {};
    search.rgPath = cli.rgPath;
    raw.search = search;
  }
  if (cli.maxResults) {
    const search = raw.search as Record<string, unknown> || {};
    search.maxResults = parseInt(cli.maxResults, 10);
    raw.search = search;
  }
  return raw;
}

/**
 * 加载配置
 * 优先级：CLI 参数 > 环境变量 > YAML 文件 > 默认值
 */
export function loadConfig(cli: CliArgs = {}): Config {
  // 1. 从默认值开始
  let raw = JSON.parse(JSON.stringify(DEFAULTS)) as Record<string, unknown>;

  // 2. 尝试加载 YAML 配置文件
  const configPath = findConfigPath();
  if (configPath) {
    try {
      const fileContent = fs.readFileSync(configPath, 'utf-8');
      const yamlData = yaml.parse(fileContent);
      if (yamlData && typeof yamlData === 'object') {
        raw = deepMerge(raw, yamlData as Record<string, unknown>);
      }
    } catch {
      // 配置文件解析失败时使用默认值
    }
  }

  // 3. 环境变量覆盖
  raw = applyEnvOverrides(raw);

  // 4. CLI 参数覆盖
  raw = applyCliOverrides(raw, cli);

  return raw as unknown as Config;
}
