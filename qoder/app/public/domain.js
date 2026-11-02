/*
 * MemCoach 共享领域逻辑。
 * 浏览器与 Node 共用同一份实现（UMD 包装），保证「演示模式」与「实时模式」行为一致。
 *
 * 记忆条目的正文格式（小而稳，便于全文检索命中，也便于人直接读）：
 *   card=<标题> | type=<concept|decision|pitfall|fact> | points=<要点1> ; <要点2> | tags=<t1,t2> | src=<出处>
 *   review=<被复习的 entry_id> | verdict=<strong|weak> | note=<备注> | at=<ISO 时间>
 */
(function (root, factory) {
  'use strict';
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.MemCoachDomain = factory();
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const CARD_KIND = 'study-card';
  const REVIEW_KIND = 'review-outcome';
  const FIELD_SEP = ' | ';
  const POINT_SEP = ' ; ';
  const MAX_TEXT_BYTES = 8192;

  const CARD_TYPES = ['concept', 'decision', 'pitfall', 'fact'];
  const VERDICTS = ['strong', 'weak'];

  const TYPE_LABELS = {
    concept: '概念',
    decision: '决策',
    pitfall: '踩坑',
    fact: '事实'
  };

  const VERDICT_LABELS = {
    strong: '已掌握',
    weak: '需加强'
  };

  const encoder = new TextEncoder();

  /** UTF-8 字节数：PowerContext 对 memory 正文上限 8192 字节（NFC 规范化并 trim 后）。 */
  function utf8Bytes(value) {
    return encoder.encode(String(value == null ? '' : value)).length;
  }

  /** 清洗用户输入：去掉换行，把字段分隔符 | 换成 /，避免破坏正文格式。 */
  function clean(value) {
    return String(value == null ? '' : value)
      .replace(/\r\n?/g, ' ')
      .replace(/\|/g, '/')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function cleanPoint(value) {
    return clean(value).replace(/;/g, '，');
  }

  function cleanTag(value) {
    return clean(value).replace(/,/g, ' ');
  }

  function normalizeText(value) {
    return String(value == null ? '' : value).normalize('NFC').trim();
  }

  function parseEntryText(text) {
    const fields = {};
    String(text == null ? '' : text)
      .split(FIELD_SEP)
      .forEach((segment) => {
        const index = segment.indexOf('=');
        if (index <= 0) {
          return;
        }
        const key = segment.slice(0, index).trim();
        const value = segment.slice(index + 1).trim();
        if (key) {
          fields[key] = value;
        }
      });
    return fields;
  }

  function splitList(value, separator, fallback) {
    if (!value || value === '(none)') {
      return fallback;
    }
    return value
      .split(separator)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  /** 把一张学习卡片序列化成 PowerContext memory 正文。 */
  function formatCard(card) {
    const source = card || {};
    const title = clean(source.title);
    const type = CARD_TYPES.indexOf(source.type) >= 0 ? source.type : 'concept';
    const points = (source.points || []).map(cleanPoint).filter(Boolean);
    const tags = (source.tags || []).map(cleanTag).filter(Boolean);
    const src = clean(source.source);
    return [
      'card=' + (title || '(未命名卡片)'),
      'type=' + type,
      'points=' + (points.length ? points.join(POINT_SEP) : '(none)'),
      'tags=' + (tags.length ? tags.join(',') : '(none)'),
      'src=' + (src || '(unknown)')
    ].join(FIELD_SEP);
  }

  /** 把一次复习结果序列化成 PowerContext memory 正文。 */
  function formatReview(review) {
    const source = review || {};
    const cardId = clean(source.cardId);
    const verdict = VERDICTS.indexOf(source.verdict) >= 0 ? source.verdict : 'weak';
    const note = clean(source.note);
    const at = source.at || new Date().toISOString();
    return [
      'review=' + (cardId || '(unknown)'),
      'verdict=' + verdict,
      'note=' + (note || '(none)'),
      'at=' + at
    ].join(FIELD_SEP);
  }

  /** 把 PowerContext 返回的 memory entry 解析成前端用的卡片结构。 */
  function toCard(entry) {
    const raw = entry || {};
    const fields = parseEntryText(raw.text);
    const citation = raw.citation || {};
    return {
      id: citation.entry_id || '',
      version: raw.version || 1,
      entryVersionId: citation.entry_version_id || '',
      memoryRef: citation.memory_ref || null,
      kind: raw.kind || '',
      state: raw.state || 'active',
      title: fields.card || '(未命名卡片)',
      type: CARD_TYPES.indexOf(fields.type) >= 0 ? fields.type : 'concept',
      points: splitList(fields.points, POINT_SEP, []),
      tags: splitList(fields.tags, ',', []),
      source: fields.src && fields.src !== '(unknown)' ? fields.src : '',
      text: raw.text || '',
      sourceRefs: raw.source_refs || [],
      artifactRefs: raw.artifact_refs || []
    };
  }

  /** 复习题由规则确定性生成（不依赖任何大模型，保证评审可复现）。 */
  function buildQuestions(card) {
    const target = card || {};
    const title = target.title || '(未命名卡片)';
    const questions = [];
    if (target.type === 'pitfall') {
      questions.push('「' + title + '」踩过哪些坑？请说清触发条件与规避方式。');
    } else if (target.type === 'decision') {
      questions.push('为什么当初决定「' + title + '」？当时的约束条件是什么？');
    } else if (target.type === 'fact') {
      questions.push('复述「' + title + '」的关键事实与数值。');
    } else {
      questions.push('用一句话解释「' + title + '」。');
    }
    (target.points || []).forEach((point) => {
      questions.push('围绕「' + title + '」：' + point + ' —— 这条你还记得吗？');
    });
    return questions.map((prompt, index) => ({
      id: (target.id || 'card') + '-q' + index,
      prompt: prompt
    }));
  }

  /** 从 review-outcome 条目里还原每张卡片的掌握情况（同一条目取 at 最新的一次）。 */
  function summarizeMastery(entries) {
    const mastery = {};
    (entries || [])
      .filter((entry) => entry && entry.kind === REVIEW_KIND)
      .forEach((entry) => {
        const fields = parseEntryText(entry.text);
        const cardId = fields.review;
        if (!cardId || cardId === '(unknown)') {
          return;
        }
        const previous = mastery[cardId];
        const at = fields.at || '';
        if (!previous || String(at) > String(previous.at)) {
          mastery[cardId] = {
            verdict: VERDICTS.indexOf(fields.verdict) >= 0 ? fields.verdict : 'unknown',
            note: fields.note === '(none)' ? '' : fields.note || '',
            at: at,
            entryId: (entry.citation || {}).entry_id || ''
          };
        }
      });
    return mastery;
  }

  function masteryPriority(mastery) {
    if (!mastery) {
      return 1;
    }
    if (mastery.verdict === 'weak') {
      return 0;
    }
    if (mastery.verdict === 'strong') {
      return 2;
    }
    return 1;
  }

  /**
   * 组装一次复习会话。
   * cards：卡片数组；hits：检索命中（entryId/score/matchedBy）；mastery：掌握情况。
   * items 的排序即为「记忆被复用」的直接体现：需加强的排最前，其次没复习过的，最后已掌握的。
   */
  function buildReviewSession(cards, hits, mastery) {
    const hitById = {};
    (hits || []).forEach((hit) => {
      if (hit && hit.entryId) {
        hitById[hit.entryId] = hit;
      }
    });
    const items = (cards || []).map((card) => {
      const hit = hitById[card.id] || null;
      const state = (mastery || {})[card.id] || null;
      return {
        cardId: card.id,
        title: card.title,
        type: card.type,
        typeLabel: TYPE_LABELS[card.type] || card.type,
        points: card.points,
        tags: card.tags,
        source: card.source,
        version: card.version,
        entryVersionId: card.entryVersionId,
        hit: hit ? { score: hit.score, matchedBy: hit.matchedBy, text: hit.text } : null,
        mastery: state
          ? { verdict: state.verdict, verdictLabel: VERDICT_LABELS[state.verdict] || state.verdict, note: state.note, at: state.at }
          : null,
        questions: buildQuestions(card)
      };
    });
    items.sort((left, right) => {
      const byPriority = masteryPriority(left.mastery) - masteryPriority(right.mastery);
      if (byPriority !== 0) {
        return byPriority;
      }
      const leftScore = left.hit ? left.hit.score : 0;
      const rightScore = right.hit ? right.hit.score : 0;
      if (leftScore !== rightScore) {
        return rightScore - leftScore;
      }
      return String(left.cardId).localeCompare(String(right.cardId));
    });
    return { items: items, count: items.length };
  }

  /** 把检索命中统一成前端结构。 */
  function toHit(hit) {
    const raw = hit || {};
    const citation = raw.citation || {};
    return {
      entryId: citation.entry_id || '',
      entryVersionId: citation.entry_version_id || '',
      text: raw.text || '',
      score: typeof raw.score === 'number' ? raw.score : 0,
      matchedBy: raw.matched_by || [],
      memoryRef: citation.memory_ref || null,
      citation: citation
    };
  }

  /** 从一组条目直接组装复习会话（服务端与浏览器共用，保证两种模式结果一致）。 */
  function buildSession(entries, query, hits) {
    const cards = (entries || []).filter((entry) => entry.kind === CARD_KIND).map(toCard);
    const mastery = summarizeMastery(entries);
    const hitIds = (hits || []).map((hit) => hit.entryId);
    const selected = query ? cards.filter((card) => hitIds.indexOf(card.id) >= 0) : cards;
    return buildReviewSession(selected, hits, mastery);
  }

  /** 学习足迹统计（服务端与浏览器共用）。 */
  function computeStats(entries) {
    const list = entries || [];
    const cards = list.filter((entry) => entry.kind === CARD_KIND).map(toCard);
    const reviews = list.filter((entry) => entry.kind === REVIEW_KIND);
    const mastery = summarizeMastery(list);
    const byType = {};
    CARD_TYPES.forEach((type) => {
      byType[type] = 0;
    });
    let strong = 0;
    let weak = 0;
    let unseen = 0;
    cards.forEach((card) => {
      byType[card.type] = (byType[card.type] || 0) + 1;
      const state = mastery[card.id];
      if (!state) {
        unseen += 1;
      } else if (state.verdict === 'strong') {
        strong += 1;
      } else {
        weak += 1;
      }
    });
    return {
      totals: { entries: list.length, cards: cards.length, reviews: reviews.length },
      by_type: byType,
      mastery: { strong: strong, weak: weak, unseen: unseen }
    };
  }

  /** 关键词切分：中文按用户输入的空格/标点切，最小 Server 的全文检索也是按词命中。 */
  function extractKeywords(query) {
    const text = String(query == null ? '' : query).toLowerCase().trim();
    if (!text) {
      return [];
    }
    const parts = text.split(/[\s,，、。;；:：!！?？/\\|()（）\[\]"'“”‘’]+/).filter(Boolean);
    const keywords = [];
    parts.forEach((part) => {
      if (keywords.indexOf(part) < 0) {
        keywords.push(part);
      }
    });
    return keywords;
  }

  function scoreText(query, text) {
    const keywords = extractKeywords(query);
    if (!keywords.length) {
      return 0;
    }
    const haystack = String(text == null ? '' : text).toLowerCase();
    let matched = 0;
    keywords.forEach((keyword) => {
      if (haystack.indexOf(keyword) >= 0) {
        matched += 1;
      }
    });
    return matched / keywords.length;
  }

  return {
    CARD_KIND: CARD_KIND,
    REVIEW_KIND: REVIEW_KIND,
    FIELD_SEP: FIELD_SEP,
    POINT_SEP: POINT_SEP,
    MAX_TEXT_BYTES: MAX_TEXT_BYTES,
    CARD_TYPES: CARD_TYPES,
    VERDICTS: VERDICTS,
    TYPE_LABELS: TYPE_LABELS,
    VERDICT_LABELS: VERDICT_LABELS,
    utf8Bytes: utf8Bytes,
    clean: clean,
    normalizeText: normalizeText,
    parseEntryText: parseEntryText,
    formatCard: formatCard,
    formatReview: formatReview,
    toCard: toCard,
    toHit: toHit,
    buildQuestions: buildQuestions,
    summarizeMastery: summarizeMastery,
    buildReviewSession: buildReviewSession,
    buildSession: buildSession,
    computeStats: computeStats,
    extractKeywords: extractKeywords,
    scoreText: scoreText
  };
});
