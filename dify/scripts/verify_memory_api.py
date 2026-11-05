"""PowerContext 记忆闭环探针：验证 DSL 实际使用的两个写入/读取接口。

DSL《打烊之后·便利店夜班 NPC》只依赖：
  1. POST /v1/memory/remember      —— 追加一条记忆
  2. POST /v1/memory/entries/list  —— 读回账本

本脚本在一个独立的“探针 scope”里跑一遍（不会污染玩家的存档），
也可以指定 --scope-id 对某个已有 scope 做读回检查。

用法：
    python scripts/verify_memory_api.py --token <bearer>
    python scripts/verify_memory_api.py --token <bearer> --scope-id <scope_id>

仅使用 Python 标准库。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PROBE_TITLE = "夜灯便利店·探针存档"
PROBE_KEY = "dify-nightstore-probe"
PROBE_TEXT = "type=prank; warmth=-1; grudge=2; say=PowerContext 探针条目"


def call(base_url: str, path: str, token: str, method: str = "GET",
         payload: dict[str, Any] | None = None, timeout: int = 20) -> Any:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(f"{base_url.rstrip('/')}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc
    return json.loads(body) if body.strip() else None


def find_probe_scope(base_url: str, token: str) -> str:
    page = call(base_url, "/v1/scopes?limit=100", token)
    for item in (page or {}).get("items", []):
        if item.get("title") == PROBE_TITLE:
            return item.get("scope_id", "")
    created = call(base_url, "/v1/scopes", token, "POST", {
        "title": PROBE_TITLE,
        "summary": "PowerContext 读写探针，不属于任何玩家存档。",
        "idempotency_key": PROBE_KEY,
    })
    return (created or {}).get("scope_id", "")


def main() -> int:
    parser = argparse.ArgumentParser(description="PowerContext remember -> entries/list 自检")
    parser.add_argument("--base-url", default=os.environ.get("POWERCONTEXT_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.environ.get("POWERCONTEXT_CLIENT_API_TOKEN", ""))
    parser.add_argument("--scope-id", default="", help="留空则使用独立的探针 scope")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    token = args.token.strip()

    try:
        health = call(base_url, "/health/ready", token)
        print(f"[1/4] 健康检查：{json.dumps(health, ensure_ascii=False)}")
    except Exception as exc:  # noqa: BLE001
        print(f"[1/4] 无法连接 PowerContext：{exc}")
        return 1

    try:
        scope_id = args.scope_id.strip() or find_probe_scope(base_url, token)
    except Exception as exc:  # noqa: BLE001
        print(f"[2/4] 准备 scope 失败：{exc}")
        return 1
    if not scope_id:
        print("[2/4] 没有拿到 scope_id")
        return 1
    print(f"[2/4] 使用 scope：{scope_id}")

    try:
        before = call(base_url, "/v1/memory/entries/list", token, "POST", {"scope_id": scope_id})
        before_entries = (before or {}).get("entries", [])
        print(f"[3/4] 写入前账本条目数：{len(before_entries)}")
        call(base_url, "/v1/memory/remember", token, "POST", {
            "scope_id": scope_id,
            "kind": "npc-event",
            "text": PROBE_TEXT,
            "reason": "verify_memory_api.py 自检",
        })
        after = call(base_url, "/v1/memory/entries/list", token, "POST", {"scope_id": scope_id})
        after_entries = (after or {}).get("entries", [])
        hit = next((e for e in after_entries if e.get("text") == PROBE_TEXT), None)
        print(f"[4/4] 写入后账本条目数：{len(after_entries)}；探针条目存在：{bool(hit)}")
        if hit:
            print(f"      kind={hit.get('kind')}")
            print(f"      entry_id={hit.get('citation', {}).get('entry_id')}")
    except Exception as exc:  # noqa: BLE001
        print(f"[3/4] 写入/读回失败：{exc}")
        return 1

    if not hit:
        print("自检失败：写入的条目没有出现在 entries/list 中。")
        return 1
    print("自检通过：remember -> entries/list 闭环正常。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
