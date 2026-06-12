/** 代码库仓库配置 */
export interface CodebaseRepo {
  path: string;
  name: string;
}

/** 思源连接配置 */
export interface SiyuanConfig {
  host: string;
  port: number;
  token: string;
}

/** 搜索配置 */
export interface SearchConfig {
  maxResults: number;
  rgPath: string;
}

/** 完整配置 */
export interface Config {
  siyuan: SiyuanConfig;
  codebase: { repos: CodebaseRepo[] };
  search: SearchConfig;
}

export const DEFAULTS: Config = {
  siyuan: { host: '127.0.0.1', port: 6806, token: '' },
  codebase: { repos: [] },
  search: { maxResults: 10, rgPath: 'rg' },
};
