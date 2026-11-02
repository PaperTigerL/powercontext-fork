// HTTP 端到端：本地 embedding -> POST /api/documents -> POST /api/search
import { pipeline, env } from '@huggingface/transformers';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
env.allowLocalModels = true;
env.localModelPath = join(ROOT, 'web', 'public', 'models');
env.useBrowserCache = false;
const BASE = process.env.BASE || 'http://127.0.0.1:8787';

const pipe = await pipeline('feature-extraction', 'bge-small-zh-v1.5', { device: 'cpu', dtype: 'q8' });
const texts = [
  'seekdb 支持向量索引与全文索引，可在一张表上同时建两类索引',
  'WebGPU 可以在浏览器里加速神经网络推理',
  'PowerContext 为大模型应用提供记忆与上下文管理',
];
const vecs = (await pipe(texts, { pooling: 'mean', normalize: true })).tolist();
const items = texts.map((text, i) => ({
  id: 'e2e-' + Date.now() + '-' + i,
  text,
  vector: vecs[i],
  metadata: { source: 'e2e' },
}));

const addResp = await fetch(BASE + '/api/documents', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ items }),
});
console.log('ADD', addResp.status, await addResp.text());

const searchResp = await fetch(BASE + '/api/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ vector: vecs[0], text: '向量和全文混合检索', limit: 5 }),
});
const search = await searchResp.json();
console.log('SEARCH', searchResp.status);
for (const r of search.results || []) console.log(' -', r.id, '|', (r.document || '').slice(0, 40), '| d=' + r.distance);
process.exit(0);