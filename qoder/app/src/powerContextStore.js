'use strict';

const { AppError } = require('./errors');
const D = require('../public/domain.js');

/**
 * 实时模式存储：把 PowerContext 的 Memory 三个接口包装成 MemoryStore。
 *
 * 与演示模式（public/demo-store.js）接口一致：
 *   list()     -> { memory, entries: [MemoryEntry] }
 *   remember() -> { memory, entry: MemoryEntry }
 *   search()   -> { memory, mode, hits: [SearchMemoryHit] }
 *
 * scope 语义：所有写入与读取都绑定同一个 scope_id，条目之间互相隔离。
 */
function createLiveStore(options) {
  const client = options.client;
  const config = options.config;
  const searchMode = config.searchMode || 'fts';

  let scopePromise = null;

  function resolveScopeId() {
    if (config.scopeId) {
      return Promise.resolve(config.scopeId);
    }
    if (!scopePromise) {
      scopePromise = ensureScope();
    }
    return scopePromise;
  }

  /** 未配置 scope_id 时：按标题复用已有 Scope，没有则用固定幂等键创建。 */
  async function ensureScope() {
    if (!config.autoScope) {
      throw new AppError(
        503,
        'powercontext_not_configured',
        '未配置 POWERCONTEXT_SCOPE_ID。可先运行仓库里的 dify/scripts/init_scope.py 创建 Scope 后填入；' +
          '或设置 POWERCONTEXT_AUTO_SCOPE=1 让本应用用幂等键自动创建。',
        { base_url: config.baseUrl }
      );
    }
    const page = await client.get('/v1/scopes', { query: config.scopeTitle, query_field: 'title', limit: '100' });
    const items = (page.body && page.body.items) || [];
    const existing = items.find((item) => item && item.title === config.scopeTitle && item.scope_id);
    if (existing) {
      return existing.scope_id;
    }
    const created = await client.post('/v1/scopes', {
      title: config.scopeTitle,
      summary: config.scopeSummary,
      idempotency_key: config.scopeIdempotencyKey
    });
    const scopeId = created.body && created.body.scope_id;
    if (!scopeId) {
      throw new AppError(502, 'powercontext_scope_failed', '创建 Scope 失败：PowerContext 没有返回 scope_id。');
    }
    return scopeId;
  }

  return {
    mode: 'live',

    async scopeId() {
      return resolveScopeId();
    },

    async list() {
      const scopeId = await resolveScopeId();
      const result = await client.post('/v1/memory/entries/list', { scope_id: scopeId });
      return {
        memory: result.body.memory || null,
        entries: result.body.entries || []
      };
    },

    async remember(payload) {
      const scopeId = await resolveScopeId();
      const kind = String((payload && payload.kind) || D.CARD_KIND).trim() || D.CARD_KIND;
      const text = D.normalizeText((payload && payload.text) || '');
      if (!text) {
        throw new AppError(422, 'invalid_request', '记忆正文不能为空。');
      }
      // PowerContext 契约：正文 NFC 规范化并 trim 后最多 8192 个 UTF-8 字节，超出返回 422。
      if (D.utf8Bytes(text) > D.MAX_TEXT_BYTES) {
        throw new AppError(422, 'text-too-long', 'memory entry text must not exceed ' + D.MAX_TEXT_BYTES + ' UTF-8 bytes');
      }
      const body = {
        scope_id: scopeId,
        kind: kind,
        text: text,
        reason: (payload && payload.reason) || null
      };
      const result = await client.post('/v1/memory/remember', body);
      return {
        memory: result.body.memory || null,
        entry: result.body.entry || null,
        requestId: result.requestId || null
      };
    },

    async search(payload) {
      const scopeId = await resolveScopeId();
      const query = String((payload && payload.query) || '').trim();
      if (!query) {
        throw new AppError(422, 'invalid_request', '检索关键词不能为空。');
      }
      const limit = Math.max(1, Math.min(50, Number((payload && payload.limit) || 10) || 10));
      const result = await client.post('/v1/memory/search', {
        scope_id: scopeId,
        query: query,
        limit: limit,
        mode: searchMode
      });
      return {
        memory: result.body.memory || null,
        mode: result.body.mode || searchMode,
        hits: result.body.hits || []
      };
    }
  };
}

module.exports = { createLiveStore: createLiveStore };
