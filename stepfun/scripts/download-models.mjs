// 下载 bge-small-zh-v1.5 的 ONNX 版（Transformers.js 可直接加载）
// 国内网络默认走 hf-mirror 镜像；可用 HF_ENDPOINT 覆盖。
import { mkdir, writeFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const MODEL_ID = 'Xenova/bge-small-zh-v1.5';
const OUT = join(ROOT, 'web', 'public', 'models', 'bge-small-zh-v1.5');
const ENDPOINT = (process.env.HF_ENDPOINT || 'https://hf-mirror.com').replace(/\/$/, '');

const FILES = [
  'config.json',
  'tokenizer.json',
  'tokenizer_config.json',
  'special_tokens_map.json',
  'vocab.txt',
  'onnx/model_fp16.onnx',
  'onnx/model_quantized.onnx',
];

async function download(rel) {
  const url = ENDPOINT + '/' + MODEL_ID + '/resolve/main/' + rel;
  const dest = join(OUT, rel);
  await mkdir(dirname(dest), { recursive: true });
  process.stdout.write('GET ' + rel + ' ... ');
  const resp = await fetch(url, { redirect: 'follow' });
  if (!resp.ok) throw new Error(rel + ' -> HTTP ' + resp.status);
  const buf = Buffer.from(await resp.arrayBuffer());
  await writeFile(dest, buf);
  console.log((buf.length / 1024 / 1024).toFixed(2) + ' MB');
  return buf.length;
}

console.log('endpoint:', ENDPOINT);
let total = 0;
for (const f of FILES) total += await download(f);
console.log('DONE total=' + (total / 1024 / 1024).toFixed(2) + ' MB -> ' + OUT);