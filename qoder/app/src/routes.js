'use strict';

const D = require('../public/domain.js');
const { AppError } = require('./errors');

function asArray(value) {
  if (Array.isArray(value)) {
    return value;
  }
  if (typeof value === 'string') {
    return value
      .split(/[,，\s]+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}

function pickCards(entries) {
  return entries.filter((entry) => entry.kind === D.CARD_KIND).map(D.toCard);
}

/**
 * MemCoach 的业务接口。演示模式与实时模式走完全相同的一段代码，
 * 差别只在于底层 store 是内存版还是 PowerContext 版。
 */
function createRoutes(deps) {
  const store = deps.store;
  const config = deps.config;

  async function loadEntries() {
    const result = await store.list();
    return result.entries || [];
  }

  const routes = [
    {
      method: 'GET',
      path: '/api/health',
      handler: async function () {
        let scopeId = config.scopeId || null;
        let scopeError = null;
        if (typeof store.scopeId === 'function') {
          try {
            scopeId = await store.scopeId();
          } catch (error) {
            scopeError = error instanceof AppError ? error.message : String(error && error.message);
          }
        }
        return {
          ok: true,
          app: 'memcoach',
          mode: store.mode,
          reason: config.reason,
          powercontext: {
            base_url: config.baseUrl || null,
            scope_id: scopeId,
            token_configured: Boolean(config.token),
            search_mode: config.searchMode,
            reachable: store.mode === 'live' ? scopeError === null : null
          },
          scope_error: scopeError,
          server_time: new Date().toISOString()
        };
      }
    },

    {
      method: 'GET',
      path: '/api/entries',
      handler: async function () {
        const entries = await loadEntries();
        return { mode: store.mode, count: entries.length, entries: entries };
      }
    },

    {
      method: 'GET',
      path: '/api/cards',
      handler: async function () {
        const entries = await loadEntries();
        const cards = pickCards(entries);
        const mastery = D.summarizeMastery(entries);
        return {
          mode: store.mode,
          count: cards.length,
          cards: cards.map((card) => ({ ...card, mastery: mastery[card.id] || null }))
        };
      }
    },

    {
      method: 'POST',
      path: '/api/cards',
      handler: async function (ctx) {
        const body = ctx.body || {};
        const title = D.clean(body.title);
        if (!title) {
          throw new AppError(422, 'invalid_request', '卡片标题不能为空。');
        }
        const text = D.formatCard({
          title: title,
          type: body.type,
          points: asArray(body.points),
          tags: asArray(body.tags),
          source: body.source
        });
        const saved = await store.remember({
          kind: D.CARD_KIND,
          text: text,
          reason: 'MemCoach：保存一张学习卡片'
        });
        if (!saved.entry) {
          throw new AppError(502, 'powercontext_no_entry', 'PowerContext 已接受写入，但没有返回 entry。');
        }
        return { mode: store.mode, memory: saved.memory || null, entry: saved.entry, card: D.toCard(saved.entry) };
      }
    },

    {
      method: 'POST',
      path: '/api/search',
      handler: async function (ctx) {
        const body = ctx.body || {};
        const query = String(body.query || '').trim();
        if (!query) {
          throw new AppError(422, 'invalid_request', '检索关键词不能为空。');
        }
        const limit = Math.max(1, Math.min(50, Number(body.limit) || 10));
        const result = await store.search({ query: query, limit: limit });
        return {
          mode: store.mode,
          query: query,
          search_mode: result.mode || null,
          memory: result.memory || null,
          count: (result.hits || []).length,
          hits: (result.hits || []).map(D.toHit)
        };
      }
    },

    {
      method: 'POST',
      path: '/api/review/session',
      handler: async function (ctx) {
        const body = ctx.body || {};
        const query = String(body.query || '').trim();
        const limit = Math.max(1, Math.min(50, Number(body.limit) || 10));
        const entries = await loadEntries();

        let hits = [];
        if (query) {
          const result = await store.search({ query: query, limit: limit });
          hits = (result.hits || []).map(D.toHit);
        }
        const session = D.buildSession(entries, query, hits);
        return {
          mode: store.mode,
          query: query || null,
          generated_at: new Date().toISOString(),
          count: session.count,
          hits: hits,
          items: session.items
        };
      }
    },

    {
      method: 'POST',
      path: '/api/review/answer',
      handler: async function (ctx) {
        const body = ctx.body || {};
        const cardId = D.clean(body.cardId);
        if (!cardId) {
          throw new AppError(422, 'invalid_request', '缺少 cardId，无法记录复习结果。');
        }
        const verdict = D.VERDICTS.indexOf(body.verdict) >= 0 ? body.verdict : null;
        if (!verdict) {
          throw new AppError(422, 'invalid_request', 'verdict 只能是 strong 或 weak。');
        }
        const text = D.formatReview({
          cardId: cardId,
          verdict: verdict,
          note: body.note,
          at: new Date().toISOString()
        });
        const saved = await store.remember({
          kind: D.REVIEW_KIND,
          text: text,
          reason: 'MemCoach：记录一次复习结果'
        });
        if (!saved.entry) {
          throw new AppError(502, 'powercontext_no_entry', 'PowerContext 已接受写入，但没有返回 entry。');
        }
        return { mode: store.mode, memory: saved.memory || null, entry: saved.entry };
      }
    },

    {
      method: 'GET',
      path: '/api/stats',
      handler: async function () {
        const entries = await loadEntries();
        return Object.assign({ mode: store.mode }, D.computeStats(entries));
      }
    }
  ];

  return routes;
}

module.exports = { createRoutes: createRoutes };
