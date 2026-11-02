"""PowerContext 记忆闭环自检：验证 DSL 实际使用的三个 HTTP 接口。

DSL《打烊之后·便利店夜班 NPC》只用到 PowerContext 的三个接口：
  1. POST /v1/memory/entries/list  —— 读回整本"小本子"
  2. POST /v1/memory/remember      —— 把这轮互动写进小本子
  3. POST /v1/memory/search        —— （可选）验证这些记忆可被检索命中

本脚本按同样的顺序跑一遍，用来在配置 Dify 之前先确认 PowerContext 侧一切正常。

用法：
    python scripts/verify_memory_api.py --base-url http://127.0.0.1:8000 --scope-id <scope_id>

仅使用 Python 标准库。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def post(
    base_url: str,
    path: str,
    payload: dict[str, Any],
    token: str | None,
    timeout: int = 15,
) -> Any:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(f"{base_url.rstrip('/')}{path}", data=data, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {path} 返回 HTTP {exc.code}：{detail}") from exc
    return json.loads(body) if body.strip() else None


def main() -> int:
    parser = argparse.ArgumentParser(description="PowerContext 记忆闭环自检")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("POWERCONTEXT_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument("--token", default=os.environ.get("POWERCONTEXT_CLIENT_API_TOKEN", ""))
    parser.add_argument("--scope-id", required=True, help="要自检的 scope_id")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="自检结束后保留写入的记忆条目（默认保留，方便你接着在 Dify 里验证）",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    token = args.token.strip() or None
    scope_id = args.scope_id.strip()
    marker = f"difydslselftest{uuid.uuid4().hex[:10]}"

    failures: list[str] = []

    print(f"[1/3] 写入一条测试记忆（kind=npc-event）")
    text = f"type=prank; warmth=-1; grudge=2; say={marker} 自检条目"
    try:
        saved = post(
            base_url,
            "/v1/memory/remember",
            {
                "scope_id": scope_id,
                "kind": "npc-event",
                "text": text,
                "reason": "Dify DSL 自检",
            },
            token,
        )
        entry = (saved or {}).get("entry") or {}
        print(f"      写入成功，返回条目 {entry.get('citation', {}).get('entry_id', '(无)')}")
    except Exception as exc:  # noqa: BLE001
        print(f"      写入失败：{exc}")
        failures.append("remember")
        text = ""

    print("[2/3] 读回账本（entries/list），确认条目在里面")
    try:
        listed = post(base_url, "/v1/memory/entries/list", {"scope_id": scope_id}, token)
        entries = (listed or {}).get("entries") or []
        hit = next((e for e in entries if marker in str(e.get("text", ""))), None)
        if hit:
            print(f"      找到 {len(entries)} 条活跃条目，其中包含自检条目：kind={hit.get('kind')}")
            print(f"      正文：{hit.get('text')}")
        else:
            print(f"      未找到自检条目（共 {len(entries)} 条）")
            failures.append("entries/list")
    except Exception as exc:  # noqa: BLE001
        print(f"      读取失败：{exc}")
        failures.append("entries/list")

    print("[3/3] 检索命中（memory/search，mode=fts）")
    try:
        found = post(
            base_url,
            "/v1/memory/search",
            {"scope_id": scope_id, "query": marker, "limit": 5, "mode": "fts"},
            token,
        )
        hits = (found or {}).get("hits") or []
        if hits:
            print(f"      检索命中 {len(hits)} 条，首条：{hits[0].get('text')}")
        else:
            print("      没有命中（最小 Server 使用全文检索，若 Server 未配置检索索引可能为空）")
            failures.append("memory/search")
    except Exception as exc:  # noqa: BLE001
        print(f"      检索失败：{exc}")
        failures.append("memory/search")

    print()
    if failures:
        print(f"自检未完全通过，失败环节：{', '.join(failures)}")
        print("说明：DSL 只依赖 entries/list 与 remember 两步；memory/search 仅用于交叉验证。")
        return 1
    print("自检通过：remember -> entries/list -> memory/search 三步闭环正常。")
    print(f"自检条目已保留在 scope {scope_id} 中（可用 /v1/memory/entries/revise 或 retire 清理）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
