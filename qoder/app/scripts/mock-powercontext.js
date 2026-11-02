'use strict';

/**
 * PowerContext 契约桩（mock）。
 *
 * 用途：让参赛者在没有 PowerContext 集群的机器上离线联调前端与后端联调链路。
 * 它按 openapi/powercontext.yaml 的契约实现 remember / search / entries/list / scopes 四个接口，
 * 返回结构与真实 Server 一致。
 *
 * 重要：它只是桩，**不能**作为「已与真实 PowerContext 联调」的证据。
 * 真实验证请指向真实 Server，并用仓库里的 dify/scripts/verify_memory_api.py 交叉验证。
 *
 * 用法：
 *   node scripts/mock-powercontext.js            # 监听 8898
 *   node scripts/mock-powercontext.js 9000       # 指定端口
 */

const http = require('http');

const PORT = Number(process.argv[2] || process.env.MOCK_POWERCONTEXT_PORT || 8898);
const SCOPE_ID = 'mock-scope-memcoach';

const entries = [];
let counter = 0;

function memoryRef() {
  return { family: 'memory', artifact_id: 'mock-memory', revision: 'mock-rev-' + entries.length };
}

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'X-PowerContext-Request-ID': 'mock-req-' + Date.now() });
  res.end(body);
}

function sendError(res, status, code, message, details) {
  sendJson(res, status, { error: { code: code, message: message, details: details === undefined ? null : details } });
}

function utf8Bytes(value) {
  return Buffer.byteLength(String(value), 'utf8');
}

function scoreOf(query, text) {
  const keywords = String(query || '')
    .toLowerCase()
    .split(/[\s,，、。;；:：/]+/)
    .filter(Boolean);
  if (!keywords.length) {
    return 0;
  }
  const haystack = String(text || '').toLowerCase();
  let matched = 0;
  keywords.forEach((keyword) => {
    if (haystack.indexOf(keyword) >= 0) {
      matched += 1;
    }
  });
  return matched / keywords.length;
}

const server = http.createServer((req, res) => {
  const chunks = [];
  req.on('data', (chunk) => chunks.push(chunk));
  req.on('end', () => {
    const url = new URL(req.url, 'http://localhost');
    const raw = Buffer.concat(chunks).toString('utf8');
    let body = {};
    if (raw && raw.trim() !== '') {
      try {
        body = JSON.parse(raw);
      } catch (error) {
        sendError(res, 422, 'invalid_request', 'The request body is not valid JSON.');
        return;
      }
    }

    if (req.method === 'GET' && url.pathname === '/health/live') {
      sendJson(res, 200, { status: 'ok' });
      return;
    }

    if (req.method === 'GET' && url.pathname === '/v1/scopes') {
      sendJson(res, 200, { items: [{ scope_id: SCOPE_ID, title: 'MemCoach 记忆复习教练', summary: 'mock scope', version: 1 }] });
      return;
    }

    if (req.method === 'POST' && url.pathname === '/v1/scopes') {
      sendJson(res, 200, { scope_id: SCOPE_ID, title: body.title, summary: body.summary, version: 1 });
      return;
    }

    if (req.method === 'POST' && url.pathname === '/v1/memory/remember') {
      if (!body.scope_id) {
        sendError(res, 422, 'invalid_request', 'scope_id is required.');
        return;
      }
      if (!body.kind || !body.text) {
        sendError(res, 422, 'invalid_request', 'kind and text are required.');
        return;
      }
      const normalized = String(body.text).normalize('NFC').trim();
      if (utf8Bytes(normalized) > 8192) {
        sendError(res, 422, 'invalid_request', 'The request is invalid.', {
          code: 'text-too-long',
          message: 'memory entry text must not exceed 8192 UTF-8 bytes'
        });
        return;
      }
      counter += 1;
      const entry = {
        citation: {
          memory_ref: memoryRef(),
          entry_id: 'mock-entry-' + counter,
          entry_version_id: 'mock-entry-' + counter + '@v1'
        },
        version: 1,
        kind: body.kind,
        text: normalized,
        state: 'active',
        source_refs: [],
        artifact_refs: []
      };
      entries.push(entry);
      sendJson(res, 200, { memory: entry.citation.memory_ref, entry: entry });
      return;
    }

    if (req.method === 'POST' && url.pathname === '/v1/memory/search') {
      if (!body.scope_id || !body.query) {
        sendError(res, 422, 'invalid_request', 'scope_id and query are required.');
        return;
      }
      const limit = Math.max(1, Math.min(50, Number(body.limit) || 10));
      const hits = entries
        .map((entry) => ({ entry: entry, score: scoreOf(body.query, entry.text) }))
        .filter((row) => row.score > 0)
        .sort((left, right) => right.score - left.score)
        .slice(0, limit)
        .map((row) => ({ citation: row.entry.citation, text: row.entry.text, score: row.score, matched_by: ['fts'] }));
      sendJson(res, 200, { memory: memoryRef(), mode: body.mode || 'fts', hits: hits });
      return;
    }

    if (req.method === 'POST' && url.pathname === '/v1/memory/entries/list') {
      if (!body.scope_id) {
        sendError(res, 422, 'invalid_request', 'scope_id is required.');
        return;
      }
      sendJson(res, 200, { memory: memoryRef(), entries: entries.slice() });
      return;
    }

    sendError(res, 404, 'not_found', 'No such endpoint: ' + req.method + ' ' + url.pathname);
  });
});

server.listen(PORT, () => {
  console.log('PowerContext 契约桩已启动：http://127.0.0.1:' + PORT);
  console.log('scope_id = ' + SCOPE_ID + '（这是一个桩，不是真实 PowerContext Server）');
});
