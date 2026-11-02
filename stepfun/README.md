# 端侧迷你知识库（阶跃星辰生态赛题）

浏览器本地完成文档向量化（Transformers.js · WebGPU/WASM · FP16/INT8 量化），
向量与原文写入 **seekdb**，查询时由 **seekdb 执行向量+全文混合检索**（RRF 融合）。
全程无云端推理 API 调用。

## 架构

```
浏览器（Chrome/Edge 最新版）
  ├─ Transformers.js + 本地 ONNX 模型（bge-small-zh-v1.5, 512 维）
  │    文档/查询向量均在本地计算；优先 WebGPU(FP16)，自动降级 WASM(INT8/FP16)
  └─ fetch /api/*  ──►  本地 Node 服务（server/index.mjs，仅作传输与参数校验）
                          └─► seekdb-js ──► seekdb（2881 端口）
                                集合 edge_kb：向量索引(hnsw,cosine) + 全文索引(ik 中文分词)
                                混合检索由数据库执行（query 全文 + knn 向量 + RRF）
```

## 快速开始

```bash
# 1. 安装依赖
npm install --legacy-peer-deps

# 2. 准备 seekdb（任选其一）
docker run -d -p 2881:2881 --name seekdb --restart unless-stopped oceanbase/seekdb

# 3. 下载模型（默认走 hf-mirror 镜像；HF_ENDPOINT 可覆盖）
npm run download-models

# 4. 生成演示语料（可选，用于一键体验）
npm run gen-corpus

# 5a. 生产模式：构建前端并启动（http://127.0.0.1:8787）
npm run build && npm start

# 5b. 开发模式：Vite DevServer(:5173，/api 与 /models 代理到 :8787)
npm start        # 终端 1：API+静态服务
npm run dev      # 终端 2：Vite
```

打开页面 → 粘贴或导入文本（每行一条）→ 「向量化并写入 seekdb」→ 输入查询 → 「检索」。
页面右上角会显示当前推理后端（WebGPU 或 WASM 降级）、模型与已索引条数。

## 复现实验数据

```bash
npm run bench         # Node 侧全链路基准：两档量化各自的 Recall@10 / 嵌入延迟 / 检索延迟
npm run size-report   # 模型体积与压缩比
```

结果写入 `test-results/`（benchmark.json、size-report.json），技术说明见 [技术说明.md](技术说明.md)。

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| SEEKDB_HOST / SEEKDB_PORT / SEEKDB_USER / SEEKDB_PASSWORD / SEEKDB_DATABASE | 127.0.0.1 / 2881 / root / 空 / test | seekdb 连接 |
| KB_COLLECTION | edge_kb | 集合名 |
| PORT | 8787 | 本地服务端口 |
| HF_ENDPOINT | https://hf-mirror.com | 模型下载端点 |