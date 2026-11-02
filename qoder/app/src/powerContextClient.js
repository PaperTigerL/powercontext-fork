'use strict';

const { AppError } = require('./errors');

/**
 * PowerContext HTTP API 客户端。
 *
 * 只使用 OpenAPI 契约里真实存在的路径与方法（见仓库 openapi/powercontext.yaml）：
 *   POST /v1/memory/remember        写入一条记忆
 *   POST /v1/memory/search          在同一个 scope 内检索活跃记忆
 *   POST /v1/memory/entries/list    列出同一个 scope 内的活跃记忆条目
 *   GET  /v1/scopes                 按标题查找已有 Scope
 *   POST /v1/scopes                 创建 Scope（幂等键固定）
 *   GET  /health/live               健康检查
 */
function createClient(options) {
  const baseUrl = String((options && options.baseUrl) || '').replace(/\/+$/, '');
  const token = (options && options.token) || '';
  const timeoutMs = (options && options.timeoutMs) || 15000;

  function authHeaders() {
    const headers = { Accept: 'application/json', 'Content-Type': 'application/json' };
    if (token) {
      headers.Authorization = 'Bearer ' + token;
    }
    return headers;
  }

  function buildUrl(path, query) {
    const url = baseUrl + path;
    if (!query) {
      return url;
    }
    const parts = [];
    Object.keys(query).forEach((key) => {
      const value = query[key];
      if (value === undefined || value === null || value === '') {
        return;
      }
      parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(String(value)));
    });
    return parts.length ? url + '?' + parts.join('&') : url;
  }

  function wrapFailure(error, url) {
    if (error instanceof AppError) {
      return error;
    }
    return new AppError(502, 'powercontext_unreachable', '无法连接 PowerContext Server（' + url + '）：' + error.message, { url: url });
  }

  function handleError(response, body, requestId, url) {
    const upstream = (body && body.error) || {};
    const status = response.status;
    let code = upstream.code || 'powercontext_error';
    let message = upstream.message || ('PowerContext 返回 HTTP ' + status);
    if (status === 401) {
      code = 'powercontext_unauthorized';
      message = 'PowerContext 拒绝了这次调用（401）：请检查 Bearer token 是否正确（环境变量 POWERCONTEXT_TOKEN）。';
    } else if (status === 403) {
      code = 'powercontext_forbidden';
      message = 'PowerContext 拒绝了这次调用（403）：当前身份无权访问该 scope。';
    } else if (status === 404) {
      code = 'powercontext_not_found';
      message = 'PowerContext 返回 404：目标对象不存在，最常见的原因是 scope_id 写错。';
    } else if (status === 409) {
      code = 'powercontext_conflict';
      message = 'PowerContext 返回 409：请求与当前状态冲突（并发修改或期望版本不一致）。';
    } else if (status === 422) {
      code = 'invalid_request';
      message = 'PowerContext 返回 422：请求体不符合契约。' + (upstream.message ? ' ' + upstream.message : '');
    } else if (status >= 500) {
      code = 'powercontext_server_error';
      message = 'PowerContext 返回 HTTP ' + status + '：' + message;
    }
    return new AppError(status >= 500 ? 502 : status, code, message, {
      upstream_status: status,
      upstream_code: upstream.code || null,
      upstream_details: upstream.details || null,
      request_id: requestId || null,
      url: url
    });
  }

  async function post(path, payload, query) {
    if (!baseUrl) {
      throw new AppError(503, 'powercontext_not_configured', '未配置 POWERCONTEXT_URL，无法访问 PowerContext Server。请设置环境变量后重启服务。');
    }
    const url = buildUrl(path, query);
    let response;
    try {
      response = await fetch(url, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(payload === undefined ? {} : payload),
        signal: AbortSignal.timeout(timeoutMs)
      });
    } catch (error) {
      throw wrapFailure(error, url);
    }
    return readResponse(response, url);
  }

  async function get(path, query) {
    if (!baseUrl) {
      throw new AppError(503, 'powercontext_not_configured', '未配置 POWERCONTEXT_URL，无法访问 PowerContext Server。请设置环境变量后重启服务。');
    }
    const url = buildUrl(path, query);
    let response;
    try {
      response = await fetch(url, {
        method: 'GET',
        headers: authHeaders(),
        signal: AbortSignal.timeout(timeoutMs)
      });
    } catch (error) {
      throw wrapFailure(error, url);
    }
    return readResponse(response, url);
  }

  async function readResponse(response, url) {
    const raw = await response.text();
    const requestId = response.headers.get('x-powercontext-request-id') || '';
    let body = null;
    if (raw && raw.trim() !== '') {
      try {
        body = JSON.parse(raw);
      } catch (error) {
        body = null;
      }
    }
    if (!response.ok) {
      throw handleError(response, body, requestId, url);
    }
    return { body: body || {}, requestId: requestId };
  }

  return {
    baseUrl: baseUrl,
    post: post,
    get: get
  };
}

module.exports = { createClient: createClient };
