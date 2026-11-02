"""初始化 PowerContext 存档（Scope），并输出要填进 Dify 环境变量的值。

作品《打烊之后·便利店夜班 NPC》用一个 PowerContext Scope 作为"一份存档"：
同一个 scope 里的所有 Memory 条目，就是 NPC 的那本小本子。

用法：
    python scripts/init_scope.py --base-url http://127.0.0.1:8000
    python scripts/init_scope.py --base-url http://127.0.0.1:8000 --token <bearer token>

脚本会：
1. 探测 /health/live，确认 Server 在跑；
2. 按标题查找已存在的 Scope，没有就创建一个（幂等键固定，多次运行不会重复创建）；
3. 打印 scope_id 以及可直接粘贴到 Dify「环境变量」里的三行配置。

仅使用 Python 标准库。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_TITLE = "夜灯便利店·夜班存档"
DEFAULT_SUMMARY = "Dify 生态赛题作品《打烊之后·便利店夜班 NPC》的长期记忆存档。NPC 的小本子、玩家偏好与剧情进展都存在这个 Scope 的 Memory 里。"
DEFAULT_IDEMPOTENCY_KEY = "dify-night-store-npc"


def request(
    base_url: str,
    path: str,
    token: str | None,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    query: dict[str, str] | None = None,
    timeout: int = 15,
) -> Any:
    url = f"{base_url.rstrip('/')}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"

    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} 返回 HTTP {exc.code}：{detail}") from exc
    if not body.strip():
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


def main() -> int:
    parser = argparse.ArgumentParser(description="创建/复用 PowerContext Scope")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("POWERCONTEXT_URL", "http://127.0.0.1:8000"),
        help="PowerContext Server 基地址，默认 http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("POWERCONTEXT_CLIENT_API_TOKEN", ""),
        help="Bearer token（Server 开启鉴权时必填），也可用环境变量 POWERCONTEXT_CLIENT_API_TOKEN",
    )
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--summary", default=DEFAULT_SUMMARY)
    parser.add_argument("--idempotency-key", default=DEFAULT_IDEMPOTENCY_KEY)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    token = args.token.strip() or None

    try:
        health = request(base_url, "/health/live", token)
        print(f"[1/3] Server 可用：{base_url} -> {health}")
    except Exception as exc:  # noqa: BLE001
        print(f"[1/3] 无法连接 PowerContext Server：{exc}")
        print("      请先启动：powercontext server run --env-file .env")
        return 1

    scope_id = ""
    try:
        page = request(
            base_url,
            "/v1/scopes",
            token,
            query={"query": args.title, "query_field": "title", "limit": "100"},
        )
        for item in (page or {}).get("items", []):
            if item.get("title") == args.title:
                scope_id = item.get("scope_id", "")
                break
        if scope_id:
            print(f"[2/3] 复用已存在的 Scope：{scope_id}")
        else:
            created = request(
                base_url,
                "/v1/scopes",
                token,
                method="POST",
                payload={
                    "title": args.title,
                    "summary": args.summary,
                    "idempotency_key": args.idempotency_key,
                },
            )
            scope_id = (created or {}).get("scope_id", "")
            print(f"[2/3] 已创建 Scope：{scope_id}")
    except Exception as exc:  # noqa: BLE001
        print(f"[2/3] Scope 准备失败：{exc}")
        return 1

    if not scope_id:
        print("[2/3] 没有拿到 scope_id，请检查上面的错误信息")
        return 1

    print("[3/3] 请在 Dify 应用的「环境变量」中填入以下三项（导入 DSL 后在界面右上角「环境变量」处设置）：")
    print()
    print(f"    PC_BASE_URL   = {base_url}")
    print(f"    PC_SCOPE_ID   = {scope_id}")
    print(f"    PC_AUTH_TOKEN = {token or ''}")
    print()
    print("注意：Dify 以 Docker 部署时，PC_BASE_URL 要填 Dify 容器能访问到的地址：")
    print("  - PowerContext 与 Dify 在同一个 compose 网络：填 http://powercontext:8000")
    print("  - PowerContext 跑在宿主机上：填 http://host.docker.internal:8000")
    print("  - Dify 原生部署（不在容器里）：填 http://127.0.0.1:8000")
    print()
    print("接着可以先跑一遍记忆闭环自检：")
    print(f"    python scripts/verify_memory_api.py --base-url {base_url}"
          + (f" --token {token}" if token else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
