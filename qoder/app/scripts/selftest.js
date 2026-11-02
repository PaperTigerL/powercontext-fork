'use strict';

/**
 * MemCoach 端到端自检脚本。
 *
 * 用法：
 *   node scripts/selftest.js                       # 默认 http://127.0.0.1:8899
 *   node scripts/selftest.js http://127.0.0.1:8787 # 指定地址
 *
 * 逐条验证：健康检查 → 记忆库 → 写入卡片 → 检索命中 → 复习出题 → 记录掌握度 → 统计。
 * 全部通过时退出码为 0，任一失败退出码为 1。
 */

const BASE_URL = (process.argv[2] || process.env.MEMCOACH_BASE_URL || 'http://127.0.0.1:8899').replace(/\/+$/, '');

let passed = 0;
let failed = 0;

function report(ok, title, detail) {
  if (ok) {
    passed += 1;
    console.log('  [PASS] ' + title + (detail ? ' —— ' + detail : ''));
  } else {
    failed += 1;
    console.log('  [FAIL] ' + title + (detail ? ' —— ' + detail : ''));
  }
}

async function call(path, options) {
  const response = await fetch(BASE_URL + path, Object.assign({ headers: { 'Content-Type': 'application/json' } }, options || {}));
  const text = await response.text();
  let body = null;
  if (text && text.trim() !== '') {
    try {
      body = JSON.parse(text);
    } catch (error) {
      body = null;
    }
  }
  return { status: response.status, body: body };
}

function post(path, payload) {
  return call(path, { method: 'POST', body: JSON.stringify(payload) });
}

async function main() {
  console.log('MemCoach 自检目标：' + BASE_URL);
  console.log('');

  console.log('[1/7] 健康检查');
  const health = await call('/api/health');
  report(health.status === 200 && health.body && health.body.ok === true, 'GET /api/health 返回 200 且 ok=true', 'mode=' + ((health.body && health.body.mode) || '未知'));
  const mode = (health.body && health.body.mode) || 'demo';
  console.log('       当前模式：' + mode + '｜' + ((health.body && health.body.reason) || ''));

  console.log('[2/7] 记忆库（entries/list）');
  const cardsBefore = await call('/api/cards');
  const beforeCount = (cardsBefore.body && cardsBefore.body.cards && cardsBefore.body.cards.length) || 0;
  const beforeShape = cardsBefore.status === 200 && Array.isArray(cardsBefore.body && cardsBefore.body.cards);
  report(beforeShape, 'GET /api/cards 返回 200 且结构正确（cards 数组）', beforeCount + ' 张');
  if (beforeCount === 0) {
    console.log('       提示：记忆库为空是合法状态（真实 PowerContext 的新 scope 就是空的，演示模式才有内置样例）。');
  }

  console.log('[3/7] 写入一张新卡片（memory/remember）');
  const marker = '自检样例-' + Date.now();
  const saved = await post('/api/cards', {
    title: marker,
    type: 'concept',
    points: ['自检写入的第一条要点', '自检写入的第二条要点'],
    tags: ['自检', '幂等'],
    source: 'selftest.js'
  });
  const entry = saved.body && saved.body.entry;
  const citation = (entry && entry.citation) || {};
  report(saved.status === 200 && Boolean(citation.entry_id), 'POST /api/cards 返回 entry.citation.entry_id', citation.entry_id || JSON.stringify(saved.body));
  report(entry && entry.kind === 'study-card', '写入条目的 kind 是 study-card', entry ? entry.kind : '无');
  report(entry && entry.state === 'active', '写入条目的 state 是 active', entry ? entry.state : '无');

  console.log('[4/7] 卡片进入记忆库');
  const cardsAfter = await call('/api/cards');
  const afterCards = (cardsAfter.body && cardsAfter.body.cards) || [];
  const found = afterCards.find((card) => card.id === citation.entry_id);
  report(afterCards.length === beforeCount + 1 && Boolean(found), '记忆库条数 +1 且能读到刚写入的卡片', beforeCount + ' -> ' + afterCards.length);

  console.log('[5/7] 检索命中（memory/search）');
  const searched = await post('/api/search', { query: marker, limit: 5 });
  const hits = (searched.body && searched.body.hits) || [];
  const hit = hits.find((item) => item.entryId === citation.entry_id);
  report(searched.status === 200 && hits.length > 0, 'POST /api/search 至少命中 1 条', hits.length + ' 条命中');
  report(Boolean(hit), '命中的条目就是刚写入的那一条', hit ? hit.entryId : '未命中');

  console.log('[6/7] 复习会话（用检索结果出题）');
  const session = await post('/api/review/session', { query: marker, limit: 5 });
  const items = (session.body && session.body.items) || [];
  const item = items.find((entryItem) => entryItem.cardId === citation.entry_id);
  report(session.status === 200 && items.length > 0, 'POST /api/review/session 返回复习条目', items.length + ' 条');
  report(Boolean(item) && item.questions.length > 0, '复习条目带有由记忆内容生成的题目', item ? item.questions.length + ' 道题' : '未找到条目');
  report(Boolean(item) && item.hit && Boolean(item.hit.score), '复习条目标注了检索来源与得分', item && item.hit ? 'score=' + item.hit.score : '无');

  console.log('[7/7] 记录掌握度（写入 review-outcome）并影响统计');
  const answered = await post('/api/review/answer', { cardId: citation.entry_id, verdict: 'weak', note: '自检：还需加强' });
  const reviewEntry = answered.body && answered.body.entry;
  report(answered.status === 200 && reviewEntry && reviewEntry.kind === 'review-outcome', 'POST /api/review/answer 写入 review-outcome 条目', reviewEntry ? reviewEntry.citation.entry_id : JSON.stringify(answered.body));

  const stats = await call('/api/stats');
  const totals = (stats.body && stats.body.totals) || {};
  const mastery = (stats.body && stats.body.mastery) || {};
  report(stats.status === 200 && totals.reviews >= 1, '统计里的复习记录数 ≥ 1', 'reviews=' + totals.reviews);
  report(mastery.weak >= 1, '统计里「需加强」≥ 1', 'weak=' + mastery.weak + ' strong=' + mastery.strong + ' unseen=' + mastery.unseen);

  const finalCards = await call('/api/cards');
  const finalItem = ((finalCards.body && finalCards.body.cards) || []).find((card) => card.id === citation.entry_id);
  report(Boolean(finalItem && finalItem.mastery && finalItem.mastery.verdict === 'weak'), '该卡片已显示掌握度「需加强」', finalItem && finalItem.mastery ? finalItem.mastery.verdict : '无');

  console.log('');
  console.log('结果：通过 ' + passed + ' 项，失败 ' + failed + ' 项。');
  if (failed > 0) {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error('自检脚本异常：' + (error && error.message ? error.message : String(error)));
  console.error('请先确认服务已启动：node server.js（默认端口 8899，可用 PORT 覆盖）。');
  process.exit(1);
});
