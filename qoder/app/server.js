'use strict';

const http = require('http');
const path = require('path');

const { loadConfig } = require('./src/config');
const { createStore } = require('./src/store');
const { createRoutes } = require('./src/routes');
const { serveStatic } = require('./src/static');
const { AppError } = require('./src/errors');

const MAX_BODY_BYTES = 1024 * 1024;

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) {
        reject(new AppError(413, 'payload_too_large', '请求体过大。'));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf8').trim();
      if (!raw) {
        resolve({});
        return;
      }
      try {
        const parsed = JSON.parse(raw);
        resolve(parsed && typeof parsed === 'object' ? parsed : {});
      } catch (error) {
        reject(new AppError(400, 'invalid_json', '请求体不是合法 JSON。'));
      }
    });
    req.on('error', reject);
  });
}

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload === undefined ? null : payload);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body)
  });
  res.end(body);
}

function start() {
  const config = loadConfig(process.env);
  const store = createStore(config);
  const routes = createRoutes({ store: store, config: config });
  const publicDir = path.join(__dirname, 'public');

  const server = http.createServer((req, res) => {
    const requestUrl = new URL(req.url, 'http://' + (req.headers.host || 'localhost'));
    const pathname = decodeURIComponent(requestUrl.pathname);

    // 允许静态站点（Qoder Sites）从另一个源调用本后端；token 只在服务端使用。
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

    if (req.method === 'OPTIONS') {
      res.writeHead(204);
      res.end();
      return;
    }

    const route = routes.find((item) => item.method === req.method && item.path === pathname);
    const run = async () => {
      if (route) {
        const body = req.method === 'POST' ? await readJsonBody(req) : {};
        const result = await route.handler({ body: body, query: requestUrl.searchParams, req: req, res: res });
        sendJson(res, 200, result);
        return;
      }
      if (pathname.indexOf('/api/') === 0) {
        sendJson(res, 404, {
          error: { code: 'not_found', message: '未知接口：' + pathname, details: null }
        });
        return;
      }
      await serveStatic(res, publicDir, pathname);
    };

    run().catch((error) => {
      if (res.headersSent) {
        res.end();
        return;
      }
      if (error instanceof AppError) {
        sendJson(res, error.status, error.toJSON());
        return;
      }
      console.error('[memcoach] 未预期错误：', error);
      sendJson(res, 500, {
        error: {
          code: 'internal_error',
          message: '服务内部错误：' + (error && error.message ? error.message : String(error)),
          details: null
        }
      });
    });
  });

  server.on('error', (error) => {
    if (error && error.code === 'EADDRINUSE') {
      console.error('端口 ' + config.port + ' 已被占用。请换一个端口启动，例如：PORT=8899 node server.js');
    } else {
      console.error('服务启动失败：', error);
    }
    process.exit(1);
  });

  server.listen(config.port, () => {
    console.log('MemCoach 已启动：http://127.0.0.1:' + config.port);
    console.log('运行模式：' + config.mode + '（' + config.reason + '）');
    if (config.mode === 'live') {
      console.log('PowerContext：' + (config.baseUrl || '(未配置)') + '  scope=' + (config.scopeId || '(未配置)'));
    }
    console.log('Qoder 开发记录建议：本进程打印的启动日志可作为「运行状态」证据，接口自测命令见 qoder/VERIFICATION.md。');
  });

  return server;
}

if (require.main === module) {
  start();
}

module.exports = { start: start };
