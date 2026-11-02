'use strict';

/**
 * 统一的业务异常：携带 HTTP 状态码与机器可读的 error code。
 * 与 PowerContext 的错误信封保持同构，便于前端与评审直接读懂。
 */
class AppError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.name = 'AppError';
    this.status = status;
    this.code = code;
    this.details = details === undefined ? null : details;
  }

  toJSON() {
    return {
      error: {
        code: this.code,
        message: this.message,
        details: this.details
      }
    };
  }
}

module.exports = { AppError: AppError };
