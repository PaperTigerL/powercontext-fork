import { initEmbedder, embed, info } from './embedder.js';
import { getInfo, addDocuments, hybridSearch } from './api.js';

const $ = (id) => document.getElementById(id);

function setStatus(text) { $('status').textContent = text || ''; }

function renderBackend(modelInfo) {
  const el = $('backend');
  if (modelInfo.backend === 'webgpu') {
    el.textContent = '推理后端: WebGPU · ' + modelInfo.dtype.toUpperCase();
    el.className = 'badge ok';
  } else {
    el.textContent = '推理后端: WASM(降级) · ' + modelInfo.dtype.toUpperCase();
    el.className = 'badge warn';
  }
}

async function boot() {
  setStatus('正在加载本地模型（首次需下载/解析 ONNX）...');
  try {
    const preferDtype = $('dtype').value;
    const modelInfo = await initEmbedder({ preferDtype });
    renderBackend(modelInfo);
    $('model').textContent = '模型: ' + modelInfo.model + ' · ' + modelInfo.dimension + ' 维 · 加载 ' + modelInfo.loadMs + 'ms';
    const srv = await getInfo();
    $('count').textContent = '集合 ' + srv.collection + ' · 已索引 ' + srv.count + ' 条';
    setStatus('');
  } catch (err) {
    setStatus('初始化失败: ' + err.message);
  }
}

async function onImport() {
  const raw = $('docs').value.trim();
  if (!raw) { setStatus('请先输入要导入的文本（每行一条）'); return; }
  const lines = raw.split(/\n+/).map((s) => s.trim()).filter(Boolean);
  setStatus('正在本地向量化 ' + lines.length + ' 条文档...');
  try {
    const vectors = await embed(lines);
    const items = lines.map((text, i) => ({
      id: 'doc-' + Date.now() + '-' + i,
      text,
      vector: vectors[i],
      metadata: { source: 'manual-import', seq: String(i) },
    }));
    setStatus('正在写入 seekdb 并刷新索引...');
    const r = await addDocuments(items);
    $('count').textContent = '集合 ' + r.collection + ' · 已索引 ' + r.count + ' 条';
    $('docs').value = '';
    setStatus('导入完成：' + lines.length + ' 条，索引已刷新，可检索');
  } catch (err) {
    setStatus('导入失败: ' + err.message);
  }
}

async function onSearch() {
  const q = $('q').value.trim();
  if (!q) { setStatus('请输入查询'); return; }
  setStatus('本地生成查询向量并执行数据库混合检索...');
  try {
    const [qv] = await embed([q]);
    const t0 = performance.now();
    const r = await hybridSearch(qv, q, 10);
    const ms = Math.round(performance.now() - t0);
    const box = $('results');
    box.innerHTML = '';
    (r.results || []).forEach((item, idx) => {
      const div = document.createElement('div');
      div.className = 'result';
      const meta = document.createElement('div');
      meta.className = 'meta';
      meta.textContent = '#' + (idx + 1) + ' · id=' + item.id + ' · 距离 ' + (item.distance == null ? '-' : item.distance.toFixed(4)) + ' · 检索耗时 ' + ms + 'ms';
      const doc = document.createElement('div');
      doc.className = 'doc';
      doc.textContent = item.document || '';
      div.appendChild(meta); div.appendChild(doc); box.appendChild(div);
    });
    if (!(r.results || []).length) box.innerHTML = '<div class=muted>无结果</div>';
    setStatus('');
  } catch (err) {
    setStatus('检索失败: ' + err.message);
  }
}

$('import').addEventListener('click', onImport);
$('search').addEventListener('click', onSearch);
$('dtype').addEventListener('change', () => location.reload());
boot();