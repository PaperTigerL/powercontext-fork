// 端侧 embedding：Transformers.js + 本地 ONNX 模型（无云端推理）
// 优先 WebGPU(FP16)，不支持时自动降级 WASM(INT8)，并在 UI 展示当前后端。
import { pipeline, env } from '@huggingface/transformers';

env.allowLocalModels = true;
env.localModelPath = '/models';
env.useBrowserCache = false;

export const MODEL_ID = 'bge-small-zh-v1.5';
export const DIMENSION = 512;

let extractor = null;
let currentBackend = null;
let currentDtype = null;
let loadMs = 0;

async function tryInit(device, dtype) {
  const t0 = performance.now();
  const pipe = await pipeline('feature-extraction', MODEL_ID, {
    device,
    dtype,
  });
  loadMs = Math.round(performance.now() - t0);
  return pipe;
}

export async function initEmbedder(options) {
  const preferDtype = (options && options.preferDtype) || 'q8';
  if (extractor) return info();
  const attempts = [
    { device: 'webgpu', dtype: 'fp16' },
    { device: 'wasm', dtype: preferDtype === 'fp16' ? 'fp16' : 'q8' },
  ];
  let lastError = null;
  for (const attempt of attempts) {
    try {
      extractor = await tryInit(attempt.device, attempt.dtype);
      currentBackend = attempt.device;
      currentDtype = attempt.dtype;
      return info();
    } catch (err) {
      lastError = err;
      extractor = null;
    }
  }
  throw new Error('模型初始化失败: ' + ((lastError && lastError.message) || String(lastError)));
}

export function info() {
  return {
    model: MODEL_ID,
    dimension: DIMENSION,
    backend: currentBackend,
    dtype: currentDtype,
    loadMs,
  };
}

// 返回 L2 归一化后的向量（bge 系列需归一化后用余弦距离）
export async function embed(texts) {
  if (!extractor) throw new Error('embedder 未初始化');
  const input = Array.isArray(texts) ? texts : [texts];
  const out = await extractor(input, { pooling: 'mean', normalize: true });
  const vectors = out.tolist();
  return vectors.map((v) => Array.from(v));
}