"""按 Dify 终端用户查看 PowerContext 存档与账本（只读，不写任何记忆）。

用法：
    python scripts/inspect_memory.py --user nightshift-demo-04
    python scripts/inspect_memory.py --user nightshift-demo-04 --token <bearer>

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


def main() -> int:
    parser = argparse.ArgumentParser(description="查看某个 Dify 用户的 PowerContext 账本")
    parser.add_argument("--base-url", default=os.environ.get("POWERCONTEXT_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.environ.get("POWERCONTEXT_CLIENT_API_TOKEN", ""))
    parser.add_argument("--user", required=True, help="Dify 终端用户 id（sys.user_id）")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    token = args.token.strip()
    suffix = "·" + args.user

    try:
        page = call(base_url, "/v1/scopes?limit=100", token)
    except Exception as exc:  # noqa: BLE001
        print(f"无法读取 scopes：{exc}")
        return 1

    matches = [s for s in (page or {}).get("items", []) if str(s.get("title", "")).endswith(suffix)]
    if not matches:
        print(f"没有找到用户 {args.user} 的存档。第一轮对话会自动创建。")
        return 2

    for scope in matches:
        scope_id = scope.get("scope_id", "")
        print(f"scope_id : {scope_id}")
        print(f"title    : {scope.get('title', '')}")
        try:
            listed = call(base_url, "/v1/memory/entries/list", token, "POST", {"scope_id": scope_id})
        except Exception as exc:  # noqa: BLE001
            print(f"读取账本失败：{exc}")
            return 1
        entries = [e for e in (listed or {}).get("entries", []) if e.get("state") in (None, "active")]
        print(f"entries  : {len(entries)}")
        for index, entry in enumerate(entries, 1):
            print(f"  {index}. [{entry.get('kind')}] {entry.get('text')}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
