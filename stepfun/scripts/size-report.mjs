// 模型体积报告：本地打包文件 + 上游 FP32 原始体积 -> 压缩比
import { readdir, stat, writeFile, mkdir } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const MODEL_DIR = join(ROOT, 'web', 'public', 'models', 'bge-small-zh-v1.5');
const ENDPOINT = (process.env.HF_ENDPOINT || 'https://hf-mirror.com').replace(/\/$/, '');

async function walk(dir) {
  const out = [];
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...(await walk(p)));
    else out.push({ path: p.slice(MODEL_DIR.length + 1).split('\\').join('/'), bytes: (await stat(p)).size });
  }
  return out;
}

async function upstreamFp32Bytes() {
  // BAAI/bge-small-zh-v1.5 的 PyTorch FP32 权重体积（量化前基线，HEAD 取 Content-Length）
  const urls = [
    ENDPOINT + '/BAAI/bge-small-zh-v1.5/resolve/main/pytorch_model.bin',
    ENDPOINT + '/BAAI/bge-small-zh-v1.5/resolve/main/model.safetensors',
  ];
  for (const u of urls) {
    try {
      const resp = await fetch(u, { method: 'HEAD' });
      const len = Number(resp.headers.get('content-length'));
      if (resp.ok && Number.isFinite(len) && len > 0) return len;
    } catch { /* 离线时跳过 */ }
  }
  return null;
}

const files = await walk(MODEL_DIR);
const byName = Object.fromEntries(files.map((f) => [f.path, f.bytes]));
const fp16 = byName['onnx/model_fp16.onnx'] ?? null;
const int8 = byName['onnx/model_quantized.onnx'] ?? null;
const fp32 = await upstreamFp32Bytes();

const mb = (b) => (b / 1024 / 1024).toFixed(2) + ' MB';
const report = {
  model: 'bge-small-zh-v1.5',
  files: files.map((f) => ({ file: f.path, mb: +(f.bytes / 1024 / 1024).toFixed(2) })),
  fp32_upstream_mb: fp32 ? +(fp32 / 1024 / 1024).toFixed(2) : null,
  fp16_mb: fp16 ? +(fp16 / 1024 / 1024).toFixed(2) : null,
  int8_mb: int8 ? +(int8 / 1024 / 1024).toFixed(2) : null,
  ratio_fp16_vs_fp32: fp32 && fp16 ? +(fp32 / fp16).toFixed(2) : null,
  ratio_int8_vs_fp32: fp32 && int8 ? +(fp32 / int8).toFixed(2) : null,
  ratio_int8_vs_fp16: fp16 && int8 ? +(fp16 / int8).toFixed(2) : null,
};
console.log(JSON.stringify(report, null, 2));
const outDir = join(ROOT, 'test-results');
await mkdir(outDir, { recursive: true });
await writeFile(join(outDir, 'size-report.json'), JSON.stringify(report, null, 2));
console.log('report -> ' + join(outDir, 'size-report.json'));