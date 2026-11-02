// 生成演示/评测语料：中文短文档 + 查询集（含期望命中，用于量化前后质量对比）
import { writeFile, mkdir } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'web', 'public', 'eval-corpus.json');

const TOPICS = [
  { key: 'seekdb', docs: [
    'seekdb 是 OceanBase 团队推出的 AI 原生搜索数据库，统一支持向量、全文与结构化检索。',
    'seekdb 兼容 MySQL 协议，默认监听 2881 端口，可用标准客户端连接执行 SQL。',
    'seekdb 提供嵌入式与服务器两种部署模式，嵌入式模式适合端侧与桌面应用。',
    'seekdb 的向量索引支持 HNSW 与 IVF 系列算法，可配置距离度量与图参数。',
    'seekdb 通过遥测文件记录部署实例的 UUID，用于赛事提测与使用统计。',
    'seekdb 支持近似向量检索，在 ORDER BY 距离函数后加 APPROXIMATE 关键字启用。',
  ]},
  { key: 'vector', docs: [
    '向量检索将文本编码为稠密向量，通过距离度量找到语义相近的文档。',
    '常用的向量距离度量包括余弦距离、欧氏距离与内积，选型影响检索效果。',
    'HNSW 是一种基于分层可导航小世界图的近似最近邻索引，查询快且召回高。',
    'IVF 系列索引通过倒排聚类缩小搜索范围，适合超大规模向量集合。',
    '嵌入向量通常需要 L2 归一化，归一化后余弦距离与内积检索结果一致。',
    '近似最近邻检索以少量召回损失换取数量级的延迟下降。',
  ]},
  { key: 'embedding', docs: [
    'bge-small-zh-v1.5 是适合中文检索的小型 embedding 模型，输出 512 维向量。',
    'all-MiniLM-L6-v2 是经典的英文句向量模型，体积小、速度快，适合端侧部署。',
    'embedding 模型把变长文本映射为固定维度的稠密向量，保留语义信息。',
    '端侧推理指模型在用户设备本地计算，不依赖云端 API，保护数据隐私。',
    '句向量模型通常采用均值池化汇聚 token 表示，再归一化输出。',
    '跨语言检索需要选择支持多语言的嵌入模型才能保证召回质量。',
  ]},
  { key: 'quant', docs: [
    'INT8 量化把模型权重从浮点压缩到 8 位整数，体积约减半且精度损失很小。',
    'FP16 半精度浮点在 GPU 上吞吐更高，是 WebGPU 后端的常用推理精度。',
    'ONNX 是一种开放模型格式，onnxruntime-web 可在浏览器中运行 ONNX 模型。',
    'Transformers.js 让我们在浏览器里直接运行 Transformer 模型，无需服务端。',
    '模型量化后的检索质量通常用 Recall@K 指标衡量，对比量化前后变化。',
    'WASM 是 WebGPU 不可用时的降级推理后端，兼容性最好但速度较慢。',
  ]},
  { key: 'webgpu', docs: [
    'WebGPU 是新一代浏览器图形与通用计算 API，可加速神经网络推理。',
    '浏览器端模型加载需要把 ONNX 权重与 tokenizer 一起打包到静态资源。',
    'ONNX Runtime Web 支持 WebGPU、WASM 与 WebGL 多种执行后端。',
    '端侧应用应检测运行环境，在不支持 WebGPU 时自动降级并提示用户。',
    '模型文件体积直接影响首屏加载速度，压缩与缓存是常见优化手段。',
    'Vite 可以把 npm 依赖打包为静态资源，适合构建纯前端 AI 应用。',
  ]},
  { key: 'fts', docs: [
    '全文检索基于分词与倒排索引，对关键词精确匹配的查询效果很好。',
    'MySQL 的 MATCH AGAINST 语法用于在全文索引列上执行自然语言检索。',
    '混合检索融合向量语义匹配与全文关键词匹配，兼顾理解与精确。',
    'RRF 倒数排名融合是一种稳定的多路检索结果融合算法。',
    'seekdb 支持在同一个集合上同时建立向量索引与全文索引。',
    '检索结果的融合排序由数据库执行，避免客户端自行拼合两路结果。',
  ]},
  { key: 'powercontext', docs: [
    'PowerContext 为大模型应用提供记忆与上下文管理能力。',
    'PowerContext 通过 Source 抽象保存采集到的原始证据，支持检索引用回查。',
    'PowerContext 的 Runtime 负责持久化，投影为检索流程提供内容表示。',
    'PowerContext 支持 CSV、Pi 会话、PDF 等多种来源的行级与页级采集。',
    'PowerContext 提供 HTTP API，方便 Dify 等平台接入记忆能力。',
    'PowerContext 的记忆处理可按新增来源条目数量触发，控制计算成本。',
  ]},
  { key: 'oceanbase', docs: [
    'OceanBase 是蚂蚁集团开源的分布式关系型数据库，支持 HTAP 混合负载。',
    'OceanBase 使用 PGA 日志与 Multi-Paxos 共识保证事务持久性与高可用。',
    'OceanBase 的 SQL 引擎兼容 MySQL 协议，迁移成本较低。',
    '分布式数据库通过分片与副本在多个节点间扩展存储与计算能力。',
    'LSM 树结构把随机写转换为顺序写，提升写入吞吐。',
    'compaction 负责合并 LSM 树的层级文件，控制读放大与空间放大。',
  ]},
];

const documents = [];
for (const t of TOPICS) {
  t.docs.forEach((text, i) => {
    documents.push({ id: t.key + '-' + (i + 1), topic: t.key, text });
  });
}

const queries = [
  { q: 'seekdb 是什么数据库', expect: ['seekdb'] },
  { q: '如何连接 seekdb', expect: ['seekdb'] },
  { q: '向量检索的原理', expect: ['vector'] },
  { q: 'HNSW 索引的优点', expect: ['vector'] },
  { q: '中文 embedding 模型有哪些', expect: ['embedding'] },
  { q: '什么是端侧推理', expect: ['embedding', 'webgpu'] },
  { q: 'INT8 量化的效果', expect: ['quant'] },
  { q: 'WebGPU 加速推理', expect: ['webgpu', 'quant'] },
  { q: '全文检索和向量检索的区别', expect: ['fts', 'vector'] },
  { q: '混合检索如何融合结果', expect: ['fts'] },
  { q: 'PowerContext 的记忆能力', expect: ['powercontext'] },
  { q: 'OceanBase 的架构特点', expect: ['oceanbase'] },
];

await mkdir(dirname(OUT), { recursive: true });
await writeFile(OUT, JSON.stringify({ documents, queries }, null, 2));
console.log('documents=' + documents.length + ' queries=' + queries.length + ' -> ' + OUT);