'use strict';

const DEFAULT_PORT = 8899;
const DEFAULT_SEARCH_MODE = 'fts';
const DEFAULT_TIMEOUT_MS = 15000;

const SCOPE_TITLE = 'MemCoach 记忆复习教练';
const SCOPE_SUMMARY = 'MemCoach 参赛作品的长期记忆档案：学习卡片与复习结果都保存在这个 Scope 的 Memory 里。';
const SCOPE_IDEMPOTENCY_KEY = 'memcoach-review-coach';

function firstNonEmpty() {
  for (let index = 0; index < arguments.length; index += 1) {
    const value = arguments[index];
    if (value !== undefined && value !== null && String(value).trim() !== '') {
      return String(value).trim();
    }
  }
  return '';
}

/**
 * 读取环境变量并决定运行模式。
 *
 * MEMCOACH_MODE=auto（默认）：配置了 PowerContext 地址与 scope 就走实时模式，否则走演示模式。
 * MEMCOACH_MODE=live：强制实时模式；配置缺失时接口返回清晰错误，而不是让服务崩溃。
 * MEMCOACH_MODE=demo：强制演示模式。
 */
function loadConfig(env) {
  const source = env || {};

  const baseUrl = firstNonEmpty(source.POWERCONTEXT_URL, source.PC_BASE_URL);
  const scopeId = firstNonEmpty(source.POWERCONTEXT_SCOPE_ID, source.POWERCONTEXT_SCOPE, source.PC_SCOPE_ID);
  const token = firstNonEmpty(source.POWERCONTEXT_TOKEN, source.POWERCONTEXT_CLIENT_API_TOKEN, source.PC_AUTH_TOKEN);

  const requestedMode = firstNonEmpty(source.MEMCOACH_MODE).toLowerCase() || 'auto';
  const mode = ['auto', 'demo', 'live'].indexOf(requestedMode) >= 0 ? requestedMode : 'auto';

  const searchMode = firstNonEmpty(source.MEMCOACH_SEARCH_MODE).toLowerCase() || DEFAULT_SEARCH_MODE;
  const autoScope = firstNonEmpty(source.POWERCONTEXT_AUTO_SCOPE) === '1';
  const port = Number(firstNonEmpty(source.PORT) || DEFAULT_PORT) || DEFAULT_PORT;
  const timeoutMs = Number(firstNonEmpty(source.MEMCOACH_TIMEOUT_MS) || DEFAULT_TIMEOUT_MS) || DEFAULT_TIMEOUT_MS;

  const fullyConfigured = Boolean(baseUrl && scopeId);
  const effectiveMode = mode === 'auto' ? (fullyConfigured ? 'live' : 'demo') : mode;

  let reason = '';
  if (effectiveMode === 'demo') {
    reason = mode === 'demo'
      ? 'MEMCOACH_MODE=demo，强制使用内置样例数据。'
      : '未检测到 POWERCONTEXT_URL 与 POWERCONTEXT_SCOPE_ID，自动使用内置样例数据（演示模式）。';
  } else if (!fullyConfigured) {
    const missing = [];
    if (!baseUrl) {
      missing.push('POWERCONTEXT_URL');
    }
    if (!scopeId) {
      missing.push('POWERCONTEXT_SCOPE_ID');
    }
    reason = '强制实时模式但缺少 ' + missing.join(' 与 ') + '；相关接口会返回 503 并说明如何配置。';
  } else {
    reason = '实时模式：读写 PowerContext Server ' + baseUrl + ' 的 scope ' + scopeId + '。';
  }

  return {
    mode: effectiveMode,
    requestedMode: mode,
    reason: reason,
    baseUrl: baseUrl,
    scopeId: scopeId,
    token: token,
    tokenConfigured: Boolean(token),
    searchMode: searchMode,
    autoScope: autoScope,
    port: port,
    timeoutMs: timeoutMs,
    scopeTitle: SCOPE_TITLE,
    scopeSummary: SCOPE_SUMMARY,
    scopeIdempotencyKey: SCOPE_IDEMPOTENCY_KEY
  };
}

module.exports = {
  loadConfig: loadConfig,
  DEFAULT_PORT: DEFAULT_PORT,
  DEFAULT_SEARCH_MODE: DEFAULT_SEARCH_MODE,
  SCOPE_TITLE: SCOPE_TITLE,
  SCOPE_SUMMARY: SCOPE_SUMMARY,
  SCOPE_IDEMPOTENCY_KEY: SCOPE_IDEMPOTENCY_KEY
};
