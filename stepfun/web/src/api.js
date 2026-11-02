// 与本地服务端通信：文档写入 / 混合检索 / 集合状态

async function request(path, options) {
  const resp = await fetch(path, Object.assign({
    headers: { 'Content-Type': 'application/json' },
  }, options));
  if (!resp.ok) {
    let detail = '';
    try { detail = (await resp.json()).error || ''; } catch (e) { detail = resp.statusText; }
    throw new Error('请求失败 ' + resp.status + ': ' + detail);
  }
  return resp.json();
}

export function getInfo() {
  return request('/api/info');
}

// items: [{ id, text, vector, metadata }]
export function addDocuments(items) {
  return request('/api/documents', {
    method: 'POST',
    body: JSON.stringify({ items }),
  });
}

// vector: number[]（浏览器本地算好的查询向量）；text: 查询原文（走数据库全文分支）
export function hybridSearch(vector, text, limit) {
  return request('/api/search', {
    method: 'POST',
    body: JSON.stringify({ vector, text, limit: limit || 10 }),
  });
}