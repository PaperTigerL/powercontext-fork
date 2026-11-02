'use strict';

const { createClient } = require('./powerContextClient');
const { createLiveStore } = require('./powerContextStore');
const { createDemoStore } = require('../public/demo-store.js');

/**
 * 按配置选择存储实现。
 * 两种实现返回的数据结构完全一致，所以上层业务（卡片、检索、复习会话）不需要区分模式。
 */
function createStore(config) {
  if (config.mode === 'live') {
    const client = createClient({
      baseUrl: config.baseUrl,
      token: config.token,
      timeoutMs: config.timeoutMs
    });
    return createLiveStore({ client: client, config: config });
  }
  const store = createDemoStore();
  store.scopeId = async function () {
    return 'demo-scope';
  };
  return store;
}

module.exports = { createStore: createStore };
