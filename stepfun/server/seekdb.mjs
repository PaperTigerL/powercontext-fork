// seekdb 客户端封装：集合管理 / 写入 / 数据库内混合检索 / 索引刷新
// 全文索引使用 ik 中文分词（默认 space 分词对中文无效）。
import { SeekdbClient, Schema, FulltextIndexConfig, VectorIndexConfig } from 'seekdb';

export const COLLECTION_NAME = process.env.KB_COLLECTION || 'edge_kb';
export const DIMENSION = Number(process.env.KB_DIMENSION || 512); // bge-small-zh-v1.5

const connection = {
  host: process.env.SEEKDB_HOST || '127.0.0.1',
  port: Number(process.env.SEEKDB_PORT || 2881),
  user: process.env.SEEKDB_USER || 'root',
  password: process.env.SEEKDB_PASSWORD || '',
  database: process.env.SEEKDB_DATABASE || 'test',
};

const cache = new Map(); // collectionName -> Collection

function buildSchema() {
  // 显式创建：全文索引(ik 中文分词) + 向量索引(hnsw, cosine, 512 维)
  // embeddingFunction 传 null：向量由浏览器本地生成，不需要服务端嵌入函数
  // （否则 SDK 会尝试加载未安装的 default-embed 包）。
  return new Schema({
    fulltextIndex: new FulltextIndexConfig('ik'),
    vectorIndex: new VectorIndexConfig({ hnsw: { dimension: DIMENSION, distance: 'cosine' } }),
  });
}

export async function getCollection(name) {
  const collectionName = name || COLLECTION_NAME;
  if (cache.has(collectionName)) return cache.get(collectionName);
  const client = new SeekdbClient(connection);
  const collection = await client.getOrCreateCollection({
    name: collectionName,
    schema: buildSchema(),
    embeddingFunction: null,
  });
  cache.set(collectionName, collection);
  return collection;
}

// items: [{ id, text, vector, metadata }]
export async function addDocuments(items, collectionName) {
  const col = await getCollection(collectionName);
  await col.add({
    ids: items.map((it) => it.id),
    documents: items.map((it) => it.text),
    embeddings: items.map((it) => it.vector),
    metadatas: items.map((it) => it.metadata || {}),
  });
  // 刷新向量索引，使新写入立即可检索（题目要求的索引刷新语义）
  if (typeof col.refresh_index === 'function') {
    await col.refresh_index();
  }
  return col.count();
}

// 混合检索完全在 seekdb 内完成：query=全文分支，knn=向量分支，RRF 融合
export async function hybridSearch(vector, text, limit, collectionName) {
  const col = await getCollection(collectionName);
  const res = await col.hybridSearch({
    query: { whereDocument: { $contains: text }, nResults: limit },
    knn: { queryEmbeddings: [vector], nResults: limit },
    rank: { rrf: { rankWindowSize: 60, rankConstant: 60 } },
    nResults: limit,
    include: ['documents', 'metadatas', 'distances'],
  });
  const ids = (res.ids && res.ids[0]) || [];
  const docs = (res.documents && res.documents[0]) || [];
  const metas = (res.metadatas && res.metadatas[0]) || [];
  const dists = (res.distances && res.distances[0]) || [];
  return ids.map((id, i) => ({
    id,
    document: docs[i] ?? null,
    metadata: metas[i] ?? null,
    distance: dists[i] ?? null,
  }));
}