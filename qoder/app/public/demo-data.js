/*
 * MemCoach 演示模式的样例数据。
 * 内置 5 张学习卡片 + 1 条复习结果，保证评审在没有任何后端的情况下也能完整走一遍
 * 「录入 → 记忆库 → 检索 → 复习出题 → 记录掌握度 → 影响下次复习排序」。
 */
(function (root, factory) {
  'use strict';
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./domain.js'));
  } else {
    root.MemCoachDemoData = factory(root.MemCoachDomain);
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function (D) {
  'use strict';

  const CARDS = [
    {
      id: 'demo-entry-1',
      card: {
        title: '倒排索引与向量索引的区别',
        type: 'concept',
        points: [
          '倒排索引从词项映射到文档列表，靠字面命中',
          '向量索引用嵌入向量做近似最近邻，靠语义相似',
          '混合检索用两路召回加融合排序兜底'
        ],
        tags: ['检索', 'RAG', '索引'],
        source: '《信息检索导论》第 3 章'
      }
    },
    {
      id: 'demo-entry-2',
      card: {
        title: '幂等键必须绑定业务主键',
        type: 'pitfall',
        points: [
          '同一个幂等键换业务参数会污染上一次的结果',
          '幂等键要带上租户维度，否则跨租户串号',
          '命中已有幂等键时应回放旧结果而不是重新执行'
        ],
        tags: ['幂等', '后端', '事故复盘'],
        source: '线上事故复盘 2026-09'
      }
    },
    {
      id: 'demo-entry-3',
      card: {
        title: '统一用 UTC 存储时间，展示层再转本地时区',
        type: 'decision',
        points: [
          '避免夏令时导致的时间歧义',
          '跨时区协作时日志与数据库能对齐'
        ],
        tags: ['时间', '后端', '架构'],
        source: '架构评审纪要 2026-08'
      }
    },
    {
      id: 'demo-entry-4',
      card: {
        title: 'OceanBase 读多写少场景选 RC 隔离级别',
        type: 'decision',
        points: [
          'RC 能减少锁冲突，读多写少时吞吐更高',
          '需要跨行快照一致性时才用 RR',
          '压测结论要和业务一致性问题分开验证'
        ],
        tags: ['数据库', 'OceanBase', '事务'],
        source: 'OceanBase 压测报告 2026-07'
      }
    },
    {
      id: 'demo-entry-5',
      card: {
        title: '待确认事实：OceanBase 单表分区数量上限',
        type: 'fact',
        points: [
          '具体上限与版本相关，必须查当前版本文档确认',
          '不要凭印象写进方案，先核对官方文档'
        ],
        tags: ['数据库', 'OceanBase', '待核对'],
        source: '待办清单 2026-10'
      }
    }
  ];

  const REVIEWS = [
    {
      id: 'demo-entry-6',
      cardId: 'demo-entry-2',
      verdict: 'weak',
      note: '只记住了结论，没记住触发条件',
      at: '2026-10-28T09:15:00.000Z'
    }
  ];

  function makeEntry(id, kind, text, revision) {
    return {
      citation: {
        memory_ref: { family: 'memory', artifact_id: 'demo-memory', revision: 'demo-rev-' + revision },
        entry_id: id,
        entry_version_id: id + '@v1'
      },
      version: 1,
      kind: kind,
      text: text,
      state: 'active',
      source_refs: [],
      artifact_refs: []
    };
  }

  /** 返回一份全新的种子条目副本（每次调用都独立，避免演示模式之间互相污染）。 */
  function seedEntries() {
    const entries = [];
    CARDS.forEach((item, index) => {
      entries.push(makeEntry(item.id, D.CARD_KIND, D.formatCard(item.card), index + 1));
    });
    REVIEWS.forEach((item, index) => {
      const text = D.formatReview({ cardId: item.cardId, verdict: item.verdict, note: item.note, at: item.at });
      entries.push(makeEntry(item.id, D.REVIEW_KIND, text, CARDS.length + index + 1));
    });
    return entries;
  }

  return {
    seedEntries: seedEntries,
    cardCount: CARDS.length,
    reviewCount: REVIEWS.length
  };
});
