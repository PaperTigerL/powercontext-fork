"""通过 Dify App API 复跑五轮验证场景，并记录回答、账本与（可选）节点级执行记录。

用法：
    set DIFY_APP_API_KEY=app-...
    set POWERCONTEXT_CLIENT_API_TOKEN=...
    python scripts/run_scenario.py --user nightshift-demo-04 --out evidence/scenario_run.json

可选环境变量：
    DIFY_BASE_URL            默认 http://127.0.0.1:8088
    POWERCONTEXT_URL         默认 http://127.0.0.1:8000
    DIFY_APP_ID              用于从 Dify 数据库抓 workflow_run_id / 节点执行
    DIFY_DB_CONTAINER        默认 dify-deploy-db-1（仅当 DIFY_APP_ID 存在时使用）

仅使用 Python 标准库。
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SESSION_A = [
    ("A1 恶作剧", "我把货架上的布丁按颜色排成彩虹了，还给价目表画了两撇胡子。"),
    ("A2 示好", "给你带了根猫条，还有热豆浆。"),
    ("A3 改名", "以后你就叫小笼包吧。"),
]
SESSION_B = [
    ("B1 翻旧账", "你还记得我上次干了什么吗？"),
    ("B2 新话题", "我今天有点困，站了一天。"),
]

KEEP_NODES = {"start", "http_scope", "http_ledger", "code_ledger", "if_write",
              "http_remember", "if_route", "code_reply_recall", "code_reply_chat",
              "answer_recall", "answer_chat"}


def http_json(url: str, method: str = "GET", headers: dict[str, str] | None = None,
              payload: dict[str, Any] | None = None, timeout: int = 600) -> tuple[int, Any]:
    body = None
    head = {"Accept": "application/json"}
    if headers:
        head.update(headers)
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        head["Content-Type"] = "application/json"
    req = Request(url, data=body, headers=head, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw.strip() else None
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, raw


def psql_json(container: str, sql: str) -> Any:
    out = subprocess.run(
        ["docker", "exec", container, "psql", "-U", "postgres", "-d", "dify", "-At", "-c", sql],
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    text = (out.stdout or "").strip()
    if not text or text == "NULL":
        return None
    return json.loads(text)


def latest_run(container: str, app_id: str) -> dict[str, Any]:
    return psql_json(container, (
        "select json_build_object('run_id', r.id, 'status', r.status, 'elapsed', r.elapsed_time) "
        "from workflow_runs r join workflows w on w.id = r.workflow_id "
        "where w.app_id = '%s' order by r.created_at desc limit 1;" % app_id
    )) or {}


def node_trace(container: str, run_id: str) -> list[dict[str, Any]]:
    rows = psql_json(container, (
        "select coalesce(json_agg(json_build_object("
        "'node_id', node_id, 'title', title, 'status', status, "
        "'elapsed_ms', round(elapsed_time * 1000)::int, 'outputs', outputs::jsonb) "
        "order by index), '[]'::json) from workflow_node_executions "
        "where workflow_run_id = '%s';" % run_id
    )) or []
    result = []
    for row in rows:
        if row.get("node_id") not in KEEP_NODES:
            continue
        out = row.get("outputs") or {}
        if row["node_id"] == "http_ledger":
            try:
                parsed = json.loads(out.get("body") or "{}")
                out = {"status_code": out.get("status_code"),
                       "entry_count": len(parsed.get("entries") or []),
                       "entries": parsed.get("entries")}
            except Exception:
                out = {"status_code": out.get("status_code")}
        elif row["node_id"] == "http_scope":
            out = {"status_code": out.get("status_code"), "body": str(out.get("body"))[:400]}
        elif row["node_id"] == "http_remember":
            out = {"status_code": out.get("status_code"), "body": str(out.get("body"))[:300]}
        elif row["node_id"] == "code_ledger":
            out = {k: out.get(k) for k in ("intent", "npc_name", "status_line", "ledger_digest")}
        elif row["node_id"] in ("code_reply_recall", "code_reply_chat"):
            out = {k: out.get(k) for k in ("text", "options")}
        elif row["node_id"] in ("answer_recall", "answer_chat"):
            out = {"answer": str(out.get("answer") or "")[:600]}
        elif row["node_id"] in ("if_write", "if_route"):
            out = {"selected_case": out.get("selected_case") or out}
        else:
            out = {}
        result.append({"node_id": row["node_id"], "title": row.get("title"),
                       "status": row.get("status"), "elapsed_ms": row.get("elapsed_ms"),
                       "outputs": out})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="复跑夜班 NPC 五轮场景")
    parser.add_argument("--user", default="", help="Dify 终端用户 id；默认带时间戳的新用户")
    parser.add_argument("--out", default="evidence/scenario_run.json")
    parser.add_argument("--dify-url", default=os.environ.get("DIFY_BASE_URL", "http://127.0.0.1:8088"))
    parser.add_argument("--app-key", default=os.environ.get("DIFY_APP_API_KEY", ""))
    parser.add_argument("--pc-url", default=os.environ.get("POWERCONTEXT_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--pc-token", default=os.environ.get("POWERCONTEXT_CLIENT_API_TOKEN", ""))
    parser.add_argument("--app-id", default=os.environ.get("DIFY_APP_ID", ""))
    parser.add_argument("--db-container", default=os.environ.get("DIFY_DB_CONTAINER", "dify-deploy-db-1"))
    args = parser.parse_args()

    if not args.app_key:
        print("缺少 DIFY_APP_API_KEY（Dify 应用「访问 API」里的 key）")
        return 1
    user = args.user.strip() or "nightshift-demo-%d" % int(time.time())
    dify = args.dify_url.rstrip("/")
    pc = args.pc_url.rstrip("/")
    pc_headers = {"Authorization": f"Bearer {args.pc_token}"} if args.pc_token.strip() else {}

    def chat(query: str, conversation_id: str) -> tuple[int, dict[str, Any], float]:
        started = time.time()
        code, body = http_json(
            f"{dify}/v1/chat-messages", "POST",
            {"Authorization": f"Bearer {args.app_key.strip()}"},
            {"inputs": {}, "query": query, "response_mode": "blocking",
             "user": user, "conversation_id": conversation_id or ""},
        )
        elapsed = round(time.time() - started, 1)
        return code, body if isinstance(body, dict) else {"raw": str(body)[:800]}, elapsed

    def scopes() -> list[dict[str, Any]]:
        _, body = http_json(f"{pc}/v1/scopes?limit=100", headers=pc_headers, timeout=30)
        return (body or {}).get("items", []) if isinstance(body, dict) else []

    def scope_id() -> str:
        for item in scopes():
            if str(item.get("title", "")).endswith("·" + user):
                return item.get("scope_id", "")
        return ""

    def ledger(sid: str) -> list[dict[str, Any]]:
        if not sid:
            return []
        _, body = http_json(f"{pc}/v1/memory/entries/list", "POST",
                            {"Content-Type": "application/json", **pc_headers},
                            {"scope_id": sid}, timeout=30)
        return (body or {}).get("entries", []) if isinstance(body, dict) else []

    record: dict[str, Any] = {
        "user": user,
        "scope_existed_before": bool(scope_id()),
        "scope_id": "",
        "ledger_before": ledger(scope_id()),
        "environment": {"dify": dify, "powercontext": pc, "app_id": args.app_id or None},
        "turns": [],
    }
    print(f"user={user} scope_existed_before={record['scope_existed_before']}")

    conv_a = ""
    for label, query in SESSION_A:
        code, body, elapsed = chat(query, conv_a)
        conv_a = body.get("conversation_id", conv_a)
        run_id = ""
        trace: list[dict[str, Any]] = []
        if args.app_id:
            run = latest_run(args.db_container, args.app_id)
            run_id = run.get("run_id", "")
            trace = node_trace(args.db_container, run_id) if run_id else []
        record["turns"].append({
            "session": "A", "label": label, "query": query, "status": code,
            "elapsed_s": elapsed, "conversation_id": conv_a,
            "message_id": body.get("message_id"), "task_id": body.get("task_id"),
            "workflow_run_id": run_id, "answer": body.get("answer", ""),
            "node_trace": trace,
        })
        print(f"{label}: HTTP {code}, {elapsed}s, run={run_id or '-'}")

    sid = scope_id()
    record["scope_id"] = sid
    record["ledger_after_session_a"] = ledger(sid)

    conv_b = ""
    for label, query in SESSION_B:
        code, body, elapsed = chat(query, conv_b)
        conv_b = body.get("conversation_id", conv_b)
        run_id = ""
        trace = []
        if args.app_id:
            run = latest_run(args.db_container, args.app_id)
            run_id = run.get("run_id", "")
            trace = node_trace(args.db_container, run_id) if run_id else []
        record["turns"].append({
            "session": "B", "label": label, "query": query, "status": code,
            "elapsed_s": elapsed, "conversation_id": conv_b,
            "message_id": body.get("message_id"), "task_id": body.get("task_id"),
            "workflow_run_id": run_id, "answer": body.get("answer", ""),
            "node_trace": trace,
        })
        print(f"{label}: HTTP {code}, {elapsed}s, run={run_id or '-'}")

    record["ledger_after"] = ledger(sid)
    record["conversations"] = {"A": conv_a, "B": conv_b}

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
