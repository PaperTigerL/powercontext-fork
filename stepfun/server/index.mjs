// 本地服务：静态资源 + /api 代理到 seekdb。
// 浏览器只做本地推理；向量的存储与混合检索全部由 seekdb 完成。
import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { join, extname, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
import { getCollection, addDocuments, hybridSearch, COLLECTION_NAME, DIMENSION } from './seekdb.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const WEB_DIR = join(ROOT, 'web');
const MODELS_DIR = join(WEB_DIR, 'public', 'models');
const DIST_DIR = join(WEB_DIR, 'dist');
const PORT = Number(process.env.PORT || 8787);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.onnx': 'application/octet-stream',
  '.txt': 'text/plain; charset=utf-8',
  '.wasm': 'application/wasm',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
};

function sendJson(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  });
  res.end(body);
}

async function readBody(req) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

async function serveStatic(res, urlPath) {
  // /models/* 映射到本地打包模型；其余优先 dist，回退 web 源码（开发态）
  let filePath;
  if (urlPath.startsWith('/models/')) {
    filePath = join(MODELS_DIR, normalize(urlPath.slice('/models/'.length)));
  } else {
    const rel = normalize(urlPath === '/' ? 'index.html' : urlPath.replace(/^\/+/, ''));
    filePath = join(DIST_DIR, rel);
    try {
      await stat(filePath);
    } catch {
      filePath = join(WEB_DIR, rel);
    }
  }
  if (!filePath.startsWith(WEB_DIR) && !filePath.startsWith(MODELS_DIR)) {
    res.writeHead(403); res.end('forbidden'); return;
  }
  try {
    const data = await readFile(filePath);
    res.writeHead(200, { 'Content-Type': MIME[extname(filePath)] || 'application/octet-stream' });
    res.end(data);
  } catch {
    res.writeHead(404); res.end('not found');
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  try {
    if (req.method === 'OPTIONS') { sendJson(res, 204, {}); return; }
    if (url.pathname === '/api/info') {
      const col = await getCollection();
      sendJson(res, 200, { collection: COLLECTION_NAME, dimension: DIMENSION, count: await col.count() });
      return;
    }
    if (url.pathname === '/api/documents' && req.method === 'POST') {
      const body = await readBody(req);
      const items = body.items || [];
      if (!items.length) { sendJson(res, 400, { error: 'empty items' }); return; }
      for (const it of items) {
        if (!Array.isArray(it.vector) || it.vector.length !== DIMENSION) {
          sendJson(res, 400, { error: 'vector dimension mismatch, expect ' + DIMENSION });
          return;
        }
      }
      const count = await addDocuments(items);
      sendJson(res, 200, { ok: true, count, collection: COLLECTION_NAME });
      return;
    }
    if (url.pathname === '/api/search' && req.method === 'POST') {
      const body = await readBody(req);
      if (!Array.isArray(body.vector) || body.vector.length !== DIMENSION) {
        sendJson(res, 400, { error: 'vector dimension mismatch' });
        return;
      }
      const results = await hybridSearch(body.vector, String(body.text || ''), Number(body.limit) || 10);
      sendJson(res, 200, { results });
      return;
    }
    if (url.pathname.startsWith('/api/')) { sendJson(res, 404, { error: 'unknown api' }); return; }
    await serveStatic(res, url.pathname);
  } catch (err) {
    sendJson(res, 500, { error: (err && err.message) || String(err) });
  }
});

server.listen(PORT, () => {
  console.log('edge-kb server listening on http://127.0.0.1:' + PORT);
  console.log('seekdb target: ' + (process.env.SEEKDB_HOST || '127.0.0.1') + ':' + (process.env.SEEKDB_PORT || 2881));
});