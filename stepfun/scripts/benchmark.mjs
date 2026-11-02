// 基准：在 Node 中用本地 ONNX 模型（WASM）完成
//   语料向量化 -> 写入 seekdb -> 混合检索 -> 质量(Recall@10)/延迟对比
// 浏览器端同理（WebGPU/WASM），此处用于在无浏览器环境验证全链路与产出报告数据。
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { pipeline, env } from '@huggingface/transformers';
import { addDocuments, hybridSearch, getCollection } from '../server/seekdb.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
env.allowLocalModels = true;
env.localModelPath = join(ROOT, 'web', 'public', 'models');
env.useBrowserCache = false;

const MODEL_ID = 'bge-small-zh-v1.5';
const corpus = JSON.parse(await readFile(join(ROOT, 'web', 'public', 'eval-corpus.json'), 'utf8'));

async function makeExtractor(dtype) {
  const t0 = Date.now();
  // Node 环境用 cpu 执行提供方（浏览器端为 webgpu/wasm，见 web/src/embedder.js）
  const pipe = await pipeline('feature-extraction', MODEL_ID, { device: 'cpu', dtype });
  return { pipe, loadMs: Date.now() - t0 };
}

async function embedAll(pipe, texts) {
  const out = await pipe(texts, { pooling: 'mean', normalize: true, batch_size: 8 });
  return out.tolist();
}

async function runVariant(dtype, collectionName) {
  const mod = await import('../server/seekdb.mjs');
  const { pipe, loadMs } = await makeExtractor(dtype);
  const t0 = Date.now();
  const vectors = await embedAll(pipe, corpus.documents.map((d) => d.text));
  const embedMs = Date.now() - t0;
  const perDoc = Math.round(embedMs / corpus.documents.length);
  const items = corpus.documents.map((d, i) => ({
    id: d.id,
    text: d.text,
    vector: vectors[i],
    metadata: { topic: d.topic },
  }));
  const w0 = Date.now();
  await mod.addDocuments(items, collectionName);
  const writeMs = Date.now() - w0;
  let hits = 0;
  let searchMsTotal = 0;
  const details = [];
  for (const query of corpus.queries) {
    const [qv] = await embedAll(pipe, [query.q]);
    const s0 = Date.now();
    const results = await mod.hybridSearch(qv, query.q, 10, collectionName);
    searchMsTotal += Date.now() - s0;
    const got = new Set(results.map((r) => String(r.id).split('-')[0]));
    const hit = query.expect.some((e) => got.has(e));
    if (hit) hits++;
    details.push({ q: query.q, expect: query.expect, top: results.slice(0, 3).map((r) => r.id), hit });
  }
  return {
    dtype,
    collection: collectionName,
    loadMs,
    embedTotalMs: embedMs,
    embedPerDocMs: perDoc,
    writeMs,
    searchAvgMs: Math.round(searchMsTotal / corpus.queries.length),
    recallAt10: hits / corpus.queries.length,
    details,
  };
}

const RUN = Date.now();
const variants = [];
for (const [dtype, name] of [['q8', 'edge_kb_int8_' + RUN], ['fp16', 'edge_kb_fp16_' + RUN]]) {
  console.log('running variant', dtype, name);
  variants.push(await runVariant(dtype, name));
}
const report = { model: MODEL_ID, dimension: 512, at: new Date().toISOString(), variants };
const outDir = join(ROOT, 'test-results');
await mkdir(outDir, { recursive: true });
await writeFile(join(outDir, 'benchmark.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify(variants.map((v) => ({
  dtype: v.dtype, loadMs: v.loadMs, embedPerDocMs: v.embedPerDocMs,
  searchAvgMs: v.searchAvgMs, recallAt10: v.recallAt10,
})), null, 2));
console.log('report -> ' + join(outDir, 'benchmark.json'));
process.exit(0); // mysql2 连接池会保持事件循环，显式退出