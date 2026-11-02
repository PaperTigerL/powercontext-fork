/*
 * MemCoach 演示模式存储。
 *
 * 与实时模式（src/powerContextStore.js）实现完全相同的 MemoryStore 接口，
 * 返回结构也逐字段对齐 PowerContext 的 OpenAPI 契约：
 *   list()     -> { memory, entries: [MemoryEntry] }
 *   remember() -> { memory, entry: MemoryEntry }
 *   search()   -> { memory, mode, hits: [SearchMemoryHit] }
 * 因此演示模式不是「假页面」，而是同一套业务逻辑跑在一个内存版 Memory 上。
 */
(function (root, factory) {
  'use strict';
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./domain.js'), require('./demo-data.js'));
  } else {
    root.MemCoachDemoStore = factory(root.MemCoachDomain, root.MemCoachDemoData);
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function (D, Data) {
  'use strict';

  function createDemoStore() {
    let entries = Data.seedEntries();
    let counter = entries.length;
    let revision = entries.length;

    function memoryRef() {
      revision += 1;
      return { family: 'memory', artifact_id: 'demo-memory', revision: 'demo-rev-' + revision };
    }

    return {
      mode: 'demo',
      description: '内置样例数据，未连接任何后端服务',

      async list() {
        return { memory: memoryRef(), entries: entries.slice() };
      },

      async remember(payload) {
        const kind = String((payload && payload.kind) || D.CARD_KIND);
        const normalized = D.normalizeText((payload && payload.text) || '');
        if (!normalized) {
          const error = new Error('记忆正文不能为空');
          error.code = 'invalid_request';
          error.status = 422;
          throw error;
        }
        if (D.utf8Bytes(normalized) > D.MAX_TEXT_BYTES) {
          const error = new Error('memory entry text must not exceed ' + D.MAX_TEXT_BYTES + ' UTF-8 bytes');
          error.code = 'text-too-long';
          error.status = 422;
          throw error;
        }
        counter += 1;
        const entry = {
          citation: {
            memory_ref: memoryRef(),
            entry_id: 'demo-entry-' + counter,
            entry_version_id: 'demo-entry-' + counter + '@v1'
          },
          version: 1,
          kind: kind,
          text: normalized,
          state: 'active',
          source_refs: [],
          artifact_refs: []
        };
        entries = entries.concat([entry]);
        return { memory: entry.citation.memory_ref, entry: entry };
      },

      async search(payload) {
        const query = (payload && payload.query) || '';
        const limit = Math.max(1, Math.min(50, Number((payload && payload.limit) || 10)));
        const hits = entries
          .map((entry) => ({ entry: entry, score: D.scoreText(query, entry.text) }))
          .filter((row) => row.score > 0)
          .sort((left, right) => right.score - left.score || left.entry.citation.entry_id.localeCompare(right.entry.citation.entry_id))
          .slice(0, limit)
          .map((row) => ({
            citation: row.entry.citation,
            text: row.entry.text,
            score: row.score,
            matched_by: ['fts']
          }));
        return { memory: memoryRef(), mode: 'fts', hits: hits };
      }
    };
  }

  return { createDemoStore: createDemoStore };
});
