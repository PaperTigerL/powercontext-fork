/*
 * MemCoach 前端。
 *
 * 两种运行方式：
 *  - 后端模式：页面由 Node 服务（或任意部署了本服务的环境）提供，前端调用 /api/* 接口，
 *    后端再真实读写 PowerContext。
 *  - 演示模式：页面作为纯静态文件打开（Qoder Sites 直接托管 public/ 目录），
 *    前端用内置样例数据与同一套领域逻辑完成全部交互。
 */
(function () {
  'use strict';

  const D = window.MemCoachDomain;
  const Demo = window.MemCoachDemoStore;
  const STORAGE_KEY = 'memcoach.apiBase';

  const state = {
    api: null,
    health: null,
    entries: [],
    hits: [],
    session: null,
    stats: null
  };

  function el(id) {
    return document.getElementById(id);
  }

  function esc(value) {
    return String(value === undefined || value === null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function readStorage() {
    try {
      return localStorage.getItem(STORAGE_KEY) || '';
    } catch (error) {
      return '';
    }
  }

  function writeStorage(value) {
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch (error) {
      /* 隐私模式下 localStorage 不可用，忽略即可。 */
    }
  }

  async function requestJson(url, options) {
    const response = await fetch(url, Object.assign({ headers: { 'Content-Type': 'application/json' } }, options || {}));
    const text = await response.text();
    let body = null;
    if (text && text.trim() !== '') {
      try {
        body = JSON.parse(text);
      } catch (error) {
        body = null;
      }
    }
    if (!response.ok) {
      const envelope = (body && body.error) || {};
      const error = new Error(envelope.message || ('请求失败：HTTP ' + response.status));
      error.code = envelope.code || 'http_' + response.status;
      error.details = envelope.details || null;
      throw error;
    }
    return body;
  }

  /** 后端适配器：所有读写都经过 Node 服务，由它去访问 PowerContext。 */
  function backendApi(base) {
    function call(path, options) {
      return requestJson(base + path, options);
    }
    function post(path, payload) {
      return call(path, { method: 'POST', body: JSON.stringify(payload) });
    }
    return {
      kind: 'backend',
      health: function () {
        return call('/api/health');
      },
      entries: async function () {
        const result = await call('/api/entries');
        return result.entries || [];
      },
      saveCard: async function (payload) {
        const result = await post('/api/cards', payload);
        return { entry: result.entry, card: result.card };
      },
      search: async function (query, limit) {
        const result = await post('/api/search', { query: query, limit: limit || 10 });
        return { hits: result.hits || [], mode: result.search_mode };
      },
      session: async function (query) {
        const result = await post('/api/review/session', { query: query });
        return { items: result.items || [], hits: result.hits || [], count: result.count || 0 };
      },
      answer: async function (payload) {
        const result = await post('/api/review/answer', payload);
        return { entry: result.entry };
      },
      stats: async function () {
        return call('/api/stats');
      }
    };
  }

  /** 演示适配器：用内置样例数据跑同一套业务逻辑。 */
  function demoApi() {
    const store = Demo.createDemoStore();
    return {
      kind: 'demo',
      health: async function () {
        return {
          ok: true,
          mode: 'demo',
          reason: '前端内置演示模式：未连接任何后端服务，数据保存在当前页面内存中。',
          powercontext: { base_url: null, scope_id: 'demo-scope', token_configured: false, search_mode: 'fts', reachable: null }
        };
      },
      entries: async function () {
        const result = await store.list();
        return result.entries || [];
      },
      saveCard: async function (payload) {
        const text = D.formatCard(payload);
        const saved = await store.remember({ kind: D.CARD_KIND, text: text, reason: 'MemCoach：保存一张学习卡片' });
        return { entry: saved.entry, card: D.toCard(saved.entry) };
      },
      search: async function (query, limit) {
        const result = await store.search({ query: query, limit: limit || 10 });
        return { hits: (result.hits || []).map(D.toHit), mode: result.mode };
      },
      session: async function (query) {
        const entries = (await store.list()).entries;
        let hits = [];
        if (query) {
          const result = await store.search({ query: query, limit: 10 });
          hits = (result.hits || []).map(D.toHit);
        }
        const session = D.buildSession(entries, query, hits);
        return { items: session.items, hits: hits, count: session.count };
      },
      answer: async function (payload) {
        const text = D.formatReview({
          cardId: payload.cardId,
          verdict: payload.verdict,
          note: payload.note,
          at: new Date().toISOString()
        });
        const saved = await store.remember({ kind: D.REVIEW_KIND, text: text, reason: 'MemCoach：记录一次复习结果' });
        return { entry: saved.entry };
      },
      stats: async function () {
        const entries = (await store.list()).entries;
        return Object.assign({ mode: 'demo' }, D.computeStats(entries));
      }
    };
  }

  function renderStatus() {
    const badge = el('mode-badge');
    const health = state.health || {};
    const pc = health.powercontext || {};
    const isBackend = state.api && state.api.kind === 'backend';
    const live = isBackend && health.mode === 'live';

    badge.textContent = live
      ? '实时模式 · PowerContext'
      : isBackend
        ? '后端模式 · 演示数据'
        : '演示模式（内置数据）';
    badge.className = 'badge ' + (live ? 'live' : 'demo');

    const parts = [];
    if (pc.base_url) {
      parts.push('PowerContext ' + pc.base_url);
    }
    if (pc.scope_id) {
      parts.push('scope ' + pc.scope_id);
    }
    if (pc.search_mode) {
      parts.push('检索 ' + pc.search_mode);
    }
    if (health.reason) {
      parts.push(health.reason);
    }
    el('pc-info').textContent = parts.join(' · ');
  }

  function renderMemory() {
    const list = el('memory-list');
    const entries = state.entries;
    el('memory-count').textContent = '共 ' + entries.length + ' 条活跃条目';
    if (!entries.length) {
      list.innerHTML = '<li class="notice">记忆库还是空的，先在左边录入一张卡片。</li>';
      return;
    }
    list.innerHTML = entries
      .map(function (entry) {
        const card = D.toCard(entry);
        const isCard = entry.kind === D.CARD_KIND;
        const tags = isCard ? [D.TYPE_LABELS[card.type] || card.type].concat(card.tags) : ['复习记录'];
        const citation = entry.citation || {};
        return (
          '<li>' +
          '<div class="entry-head">' +
          '<span class="tag ' + (isCard ? '' : 'review') + '">' + esc(entry.kind) + '</span>' +
          tags.map(function (tag) { return '<span class="tag">' + esc(tag) + '</span>'; }).join('') +
          '<span class="tag state">' + esc(entry.state) + '</span>' +
          '</div>' +
          '<div class="entry-text">' + esc(entry.text) + '</div>' +
          '<div class="entry-meta">entry_id=' + esc(citation.entry_id) +
          ' · entry_version_id=' + esc(citation.entry_version_id) +
          ' · v' + esc(entry.version) + '</div>' +
          '</li>'
        );
      })
      .join('');
  }

  function renderSearch() {
    const box = el('search-result');
    if (!state.hits.length && state.hits !== null && state.session === null) {
      box.innerHTML = '';
      return;
    }
    if (!state.hits.length) {
      box.innerHTML = '<div class="notice">没有命中任何记忆条目。试试别的关键词，或先录入一张卡片。</div>';
      return;
    }
    box.innerHTML = state.hits
      .map(function (hit) {
        const matched = (hit.matchedBy || []).join('/') || '-';
        return (
          '<div class="hit">' +
          '<div class="entry-head"><span class="tag">命中</span><span class="tag state">得分 ' + Number(hit.score).toFixed(2) + '</span>' +
          '<span class="tag">' + esc(matched) + '</span></div>' +
          '<div class="entry-text">' + esc(hit.text) + '</div>' +
          '<div class="entry-meta">entry_id=' + esc(hit.entryId) + ' · entry_version_id=' + esc(hit.entryVersionId) + '</div>' +
          '</div>'
        );
      })
      .join('');
  }

  function renderReview() {
    const box = el('review-result');
    const session = state.session;
    if (!session) {
      box.innerHTML = '';
      return;
    }
    if (!session.items.length) {
      box.innerHTML = '<div class="notice">没有匹配的记忆条目。换个关键词，或先录入一张卡片。</div>';
      return;
    }
    box.innerHTML = session.items
      .map(function (item) {
        const hitLine = item.hit
          ? '检索命中（得分 ' + Number(item.hit.score).toFixed(2) + '，' + ((item.hit.matchedBy || []).join('/') || '-') + '）'
          : '未命中检索（本次按掌握度排序）';
        const masteryLine = item.mastery
          ? '上次结果：' + item.mastery.verdictLabel + (item.mastery.at ? '（' + String(item.mastery.at).slice(0, 10) + '）' : '') + (item.mastery.note ? ' · ' + item.mastery.note : '')
          : '还没复习过';
        return (
          '<div class="review-item">' +
          '<h3>' + esc(item.title) + ' <span class="tag">' + esc(item.typeLabel) + '</span></h3>' +
          '<div class="source-line">来源记忆条目 <b>#' + esc(item.cardId) + '</b>（v' + esc(item.version) + '） · ' + hitLine + ' · ' + masteryLine + '</div>' +
          '<ul class="questions">' +
          item.questions.map(function (q) { return '<li>' + esc(q.prompt) + '</li>'; }).join('') +
          '</ul>' +
          '<div class="answer-row">' +
          '<input data-note="' + esc(item.cardId) + '" placeholder="复习备注（可选）" />' +
          '<button class="strong" data-answer="strong" data-card="' + esc(item.cardId) + '">已掌握</button>' +
          '<button class="weak" data-answer="weak" data-card="' + esc(item.cardId) + '">需加强</button>' +
          '</div>' +
          '</div>'
        );
      })
      .join('');
  }

  function renderStats() {
    const stats = state.stats;
    if (!stats) {
      return;
    }
    const totals = stats.totals || {};
    const mastery = stats.mastery || {};
    const byType = stats.by_type || {};
    function stat(value, label) {
      return '<div class="stat"><b>' + esc(value) + '</b><span>' + esc(label) + '</span></div>';
    }
    const typeLine = Object.keys(byType)
      .map(function (key) { return (D.TYPE_LABELS[key] || key) + ' ' + byType[key]; })
      .join(' · ');
    el('stats-result').innerHTML =
      '<div class="stat-grid">' +
      stat(totals.entries, '记忆条目') +
      stat(totals.cards, '学习卡片') +
      stat(totals.reviews, '复习记录') +
      stat(mastery.strong, '已掌握') +
      stat(mastery.weak, '需加强') +
      stat(mastery.unseen, '未复习') +
      '</div>' +
      '<div class="muted" style="margin-top:10px">类型分布：' + esc(typeLine || '暂无') + '</div>';
  }

  function showError(boxId, error) {
    const box = el(boxId);
    box.innerHTML = '<div class="notice err">' + esc(error && error.message ? error.message : String(error)) + '</div>';
  }

  async function refreshMemory() {
    state.entries = await state.api.entries();
    renderMemory();
  }

  async function refreshStats() {
    state.stats = await state.api.stats();
    renderStats();
  }

  async function refreshAll() {
    try {
      await refreshMemory();
      await refreshStats();
    } catch (error) {
      showError('memory-list', error);
    }
  }

  async function connect(base) {
    const badge = el('mode-badge');
    badge.textContent = '连接中…';
    badge.className = 'badge';
    let health = null;
    let api = null;
    if (base !== null && base !== undefined) {
      try {
        const candidate = backendApi(base);
        health = await candidate.health();
        api = candidate;
      } catch (error) {
        health = null;
      }
    }
    if (!health) {
      api = demoApi();
      health = await api.health();
    }
    state.api = api;
    state.health = health;
    renderStatus();
    await refreshAll();
  }

  function readCardForm() {
    return {
      title: el('card-title').value,
      type: el('card-type').value,
      points: el('card-points').value.split('\n').map(function (line) { return line.trim(); }).filter(Boolean),
      tags: el('card-tags').value.split(/[,，]/).map(function (tag) { return tag.trim(); }).filter(Boolean),
      source: el('card-source').value
    };
  }

  function bind() {
    el('card-form').addEventListener('submit', async function (event) {
      event.preventDefault();
      const box = el('save-result');
      box.innerHTML = '<div class="notice">正在写入长期记忆…</div>';
      try {
        const saved = await state.api.saveCard(readCardForm());
        const citation = (saved.entry && saved.entry.citation) || {};
        box.innerHTML =
          '<div class="notice ok">已写入：entry_id=' + esc(citation.entry_id) +
          ' · entry_version_id=' + esc(citation.entry_version_id) + '</div>';
        el('card-form').reset();
        await refreshAll();
      } catch (error) {
        showError('save-result', error);
      }
    });

    el('refresh-memory').addEventListener('click', async function () {
      try {
        await refreshMemory();
      } catch (error) {
        showError('memory-list', error);
      }
    });

    el('do-search').addEventListener('click', async function () {
      const query = el('search-query').value.trim();
      if (!query) {
        el('search-result').innerHTML = '<div class="notice">请输入检索关键词。</div>';
        return;
      }
      el('search-result').innerHTML = '<div class="notice">检索中…</div>';
      try {
        const result = await state.api.search(query, 10);
        state.hits = result.hits || [];
        renderSearch();
      } catch (error) {
        showError('search-result', error);
      }
    });

    el('start-review').addEventListener('click', async function () {
      const query = el('review-query').value.trim();
      el('review-result').innerHTML = '<div class="notice">正在组织复习会话…</div>';
      try {
        state.session = await state.api.session(query);
        renderReview();
        await refreshStats();
      } catch (error) {
        showError('review-result', error);
      }
    });

    el('review-result').addEventListener('click', async function (event) {
      const button = event.target.closest('button[data-answer]');
      if (!button) {
        return;
      }
      const cardId = button.getAttribute('data-card');
      const verdict = button.getAttribute('data-answer');
      const noteInput = el('review-result').querySelector('input[data-note="' + cardId + '"]');
      const note = noteInput ? noteInput.value : '';
      button.disabled = true;
      try {
        await state.api.answer({ cardId: cardId, verdict: verdict, note: note });
        state.session = await state.api.session(el('review-query').value.trim());
        renderReview();
        await refreshAll();
      } catch (error) {
        button.disabled = false;
        showError('review-result', error);
      }
    });

    el('api-apply').addEventListener('click', async function () {
      const base = el('api-base').value.trim().replace(/\/+$/, '');
      writeStorage(base);
      await connect(base);
    });
  }

  async function boot() {
    bind();
    const saved = readStorage();
    el('api-base').value = saved;
    await connect(saved);
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
