"""DSL 结构校验器（仅依赖标准库 + PyYAML）。

用途：
1. 校验 dify/dsl/night-store-npc.yml 是否符合 Dify DSL 的结构约定（节点、边、变量引用）。
2. 把 Code 节点的 Python 真正跑一遍，确认它能执行、返回的键与声明的输出一致。
3. 用样例对话验证"记忆写入 -> 下一轮从长期记忆重建状态"的闭环。

用法：
    python scripts/validate_dsl.py [dsl/night-store-npc.yml]

退出码 0 表示全部检查通过。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DSL = REPO_ROOT / "dsl" / "night-store-npc.yml"

VARIABLE_PATTERN = re.compile(r"\{\{#([a-zA-Z0-9_]{1,50}(?:\.[a-zA-Z_][a-zA-Z0-9_]{0,29}){1,10})#\}\}")

# 各节点类型允许被引用的输出变量
NODE_OUTPUTS: dict[str, set[str]] = {
    "code": set(),          # 运行时由 data.outputs 决定
    "llm": {"text", "usage", "finish_reason", "files"},
    "http-request": {"body", "status_code", "headers", "files"},
    "template-transform": {"output"},
    "start": set(),
    "if-else": set(),
    "answer": set(),
}

SYSTEM_VARIABLES = {
    "sys.query",
    "sys.files",
    "sys.conversation_id",
    "sys.user_id",
    "sys.dialogue_count",
    "sys.app_id",
    "sys.workflow_id",
    "sys.workflow_run_id",
}

# Dify 0.1.x DSL 中的节点种类（data.type）
NODE_KINDS = {
    "start",
    "end",
    "llm",
    "answer",
    "code",
    "if-else",
    "http-request",
    "template-transform",
    "variable-aggregator",
    "question-classifier",
    "agent",
    "tool",
    "iteration",
    "loop",
    "parameter-extractor",
    "document-extractor",
    "list-operator",
}

errors: list[str] = []
checks: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def ok(message: str) -> None:
    checks.append(message)


def collect_strings(value: Any, path: str = "") -> list[tuple[str, str]]:
    """递归收集所有字符串值及其路径。"""
    found: list[tuple[str, str]] = []
    if isinstance(value, str):
        found.append((path, value))
    elif isinstance(value, dict):
        for key, item in value.items():
            found.extend(collect_strings(item, f"{path}.{key}" if path else str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(collect_strings(item, f"{path}[{index}]"))
    return found


def check_top_level(doc: dict[str, Any]) -> None:
    for key in ("version", "kind", "app", "workflow"):
        if key not in doc:
            fail(f"顶层缺少必需字段：{key}")
    if doc.get("version") != "0.1.5":
        fail(f"version 应为 0.1.5，实际为 {doc.get('version')!r}")
    if doc.get("kind") != "app":
        fail(f"kind 应为 app，实际为 {doc.get('kind')!r}")

    app = doc.get("app") or {}
    for key in ("name", "mode", "description"):
        if not app.get(key):
            fail(f"app 段缺少必需字段：{key}")
    if app.get("mode") not in ("advanced-chat", "workflow"):
        fail(f"app.mode 非法：{app.get('mode')!r}（Dify 中 Chatflow 的 mode 取值为 advanced-chat）")

    workflow = doc.get("workflow") or {}
    for key in ("graph", "features", "environment_variables", "conversation_variables"):
        if key not in workflow:
            fail(f"workflow 段缺少必需字段：{key}")

    graph = workflow.get("graph") or {}
    for key in ("nodes", "edges"):
        if key not in graph:
            fail(f"workflow.graph 缺少必需字段：{key}")

    for var in workflow.get("environment_variables") or []:
        for key in ("name", "value", "value_type"):
            if key not in var:
                fail(f"环境变量 {var.get('name')!r} 缺少字段 {key}")
        if var.get("value_type") != "string":
            fail(f"环境变量 {var.get('name')!r} 的 value_type 应为 string")
    ok("顶层结构、app 段、workflow 段字段齐备")


def check_nodes(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes = graph.get("nodes") or []
    by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_id = node.get("id")
        if not node_id:
            fail("存在没有 id 的节点")
            continue
        if node_id in by_id:
            fail(f"节点 id 重复：{node_id}")
        by_id[node_id] = node
        for key in ("type", "data", "position"):
            if key not in node:
                fail(f"节点 {node_id} 缺少字段 {key}")
        data = node.get("data") or {}
        if not data.get("title"):
            fail(f"节点 {node_id} 的 data.title 为空")
        # 顶层 type 是前端画布类型（custom），data.type 才是节点种类
        if data.get("type") not in NODE_KINDS:
            fail(f"节点 {node_id} 的 data.type 不是已知的 Dify 节点类型：{data.get('type')!r}")
        if node.get("type") != "custom":
            fail(f"节点 {node_id} 的顶层 type 应为 custom，实际为 {node.get('type')!r}")
    ok(f"节点 id 唯一，共 {len(by_id)} 个节点")
    return by_id


def check_edges(graph: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> None:
    edges = graph.get("edges") or []
    if not edges:
        fail("图中没有任何边")
    for edge in edges:
        edge_id = edge.get("id", "<no id>")
        source = edge.get("source")
        target = edge.get("target")
        if source not in by_id:
            fail(f"边 {edge_id} 的 source 节点不存在：{source}")
            continue
        if target not in by_id:
            fail(f"边 {edge_id} 的 target 节点不存在：{target}")
            continue
        source_type = (by_id[source].get("data") or {}).get("type")
        target_type = (by_id[target].get("data") or {}).get("type")
        if (edge.get("data") or {}).get("sourceType") != source_type:
            fail(f"边 {edge_id} 的 data.sourceType 与源节点类型不一致")
        if (edge.get("data") or {}).get("targetType") != target_type:
            fail(f"边 {edge_id} 的 data.targetType 与目标节点类型不一致")
        if edge.get("targetHandle") != "target":
            fail(f"边 {edge_id} 的 targetHandle 应为 target，实际为 {edge.get('targetHandle')!r}")

        source_handle = edge.get("sourceHandle")
        if source_type == "if-else":
            if source_handle not in ("true", "false"):
                fail(f"边 {edge_id} 引用了非法的 if-else 分支句柄：{source_handle!r}")
        elif source_handle != "source":
            fail(f"边 {edge_id} 的 sourceHandle 应为 source，实际为 {source_handle!r}")

        # 每个 if-else 都应同时具备 true / false 两条出边
    for node_id, node in by_id.items():
        if (node.get("data") or {}).get("type") != "if-else":
            continue
        handles = {
            edge.get("sourceHandle")
            for edge in edges
            if edge.get("source") == node_id
        }
        if handles != {"true", "false"}:
            fail(f"if-else 节点 {node_id} 的出边句柄应为 true 与 false，实际为 {sorted(handles)}")
    ok(f"边引用完整，共 {len(edges)} 条边，if-else 分支句柄齐备")


def check_node_schemas(doc: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> None:
    """按 Dify 各节点实体的必填字段做一次 schema 符合性检查。

    字段来源（Dify 1.0.0）：
      api/core/workflow/nodes/code/entities.py
      api/core/workflow/nodes/http_request/entities.py
      api/core/workflow/nodes/llm/entities.py
      api/core/workflow/nodes/if_else/entities.py
      api/core/workflow/nodes/answer/entities.py
      api/core/workflow/nodes/start/entities.py
    """
    required_by_kind = {
        "code": ["code", "code_language", "variables", "outputs"],
        "http-request": ["method", "url", "authorization", "headers", "params", "body"],
        "llm": ["model", "prompt_template", "context"],
        "if-else": ["cases"],
        "answer": ["answer"],
        "start": ["variables"],
    }

    for node_id, node in by_id.items():
        data = node.get("data") or {}
        kind = data.get("type")
        for key in required_by_kind.get(kind, []):
            if key not in data:
                fail(f"节点 {node_id}（{kind}）缺少实体必填字段 {key}")

        if kind == "llm":
            model = data.get("model") or {}
            for key in ("provider", "name", "mode"):
                if not model.get(key):
                    fail(f"LLM 节点 {node_id} 的 model 缺少 {key}")
            if model.get("mode") != "chat":
                fail(f"LLM 节点 {node_id} 的 model.mode 应为 chat")
            if not isinstance(data.get("prompt_template"), list) or not data.get("prompt_template"):
                fail(f"LLM 节点 {node_id} 的 prompt_template 应为非空列表")
            for index, message in enumerate(data.get("prompt_template") or []):
                if not isinstance(message, dict):
                    fail(f"LLM 节点 {node_id} 的 prompt_template[{index}] 不是映射")
                    continue
                if message.get("role") not in ("system", "user", "assistant"):
                    fail(f"LLM 节点 {node_id} 的 prompt_template[{index}].role 非法：{message.get('role')!r}")
                if not isinstance(message.get("text"), str) or not message.get("text"):
                    fail(f"LLM 节点 {node_id} 的 prompt_template[{index}].text 应为非空字符串")

        if kind == "http-request":
            if (data.get("authorization") or {}).get("type") not in ("no-auth", "api-key"):
                fail(f"HTTP 节点 {node_id} 的 authorization.type 非法")
            if not str(data.get("url") or ""):
                fail(f"HTTP 节点 {node_id} 的 url 为空")
            if data.get("method") not in (
                "get", "post", "put", "patch", "delete", "head", "options",
                "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS",
            ):
                fail(f"HTTP 节点 {node_id} 的 method 非法：{data.get('method')!r}")
            if not isinstance(data.get("headers"), str):
                fail(f"HTTP 节点 {node_id} 的 headers 应为字符串")
            if not isinstance(data.get("params"), str):
                fail(f"HTTP 节点 {node_id} 的 params 应为字符串")

        if kind == "if-else":
            cases = data.get("cases") or []
            if not cases:
                fail(f"if-else 节点 {node_id} 的 cases 为空")
            for case in cases:
                if not case.get("case_id"):
                    fail(f"if-else 节点 {node_id} 存在没有 case_id 的分支")
                if case.get("logical_operator") not in ("and", "or"):
                    fail(f"if-else 节点 {node_id} 的分支 logical_operator 非法")
                for condition in case.get("conditions") or []:
                    if not condition.get("variable_selector"):
                        fail(f"if-else 节点 {node_id} 的条件缺少 variable_selector")
                    if not condition.get("comparison_operator"):
                        fail(f"if-else 节点 {node_id} 的条件缺少 comparison_operator")

        if kind == "code":
            for output_name, output in (data.get("outputs") or {}).items():
                if output.get("type") not in (
                    "string", "number", "object", "array[string]", "array[number]", "array[object]",
                ):
                    fail(f"Code 节点 {node_id} 的输出 {output_name} 的 type 非法：{output.get('type')!r}")

    ok("各节点类型的实体必填字段符合 Dify 节点 schema")


def check_variable_references(doc: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> None:
    workflow = doc.get("workflow") or {}
    env_names = {var.get("name") for var in workflow.get("environment_variables") or []}

    # 记录每个 code 节点声明的输出
    code_outputs: dict[str, set[str]] = {}
    for node_id, node in by_id.items():
        data = node.get("data") or {}
        if data.get("type") == "code":
            code_outputs[node_id] = set((data.get("outputs") or {}).keys())

    seen: set[str] = set()
    for path, text in collect_strings(workflow):
        for raw in VARIABLE_PATTERN.findall(text):
            selector = raw.replace(".", ".")
            seen.add(selector)
            head, _, tail = selector.partition(".")
            if head == "sys":
                if selector not in SYSTEM_VARIABLES:
                    fail(f"{path} 引用了未知系统变量 {selector}")
                continue
            if head == "env":
                if tail not in env_names:
                    fail(f"{path} 引用了未声明的环境变量 env.{tail}")
                continue
            if head == "env":
                continue
            if head not in by_id:
                fail(f"{path} 引用了不存在的节点 {head}")
                continue
            node_type = (by_id[head].get("data") or {}).get("type")
            if node_type == "code":
                if tail not in code_outputs.get(head, set()):
                    fail(f"{path} 引用了 code 节点 {head} 未声明的输出 {tail}")
            elif node_type in NODE_OUTPUTS:
                if tail not in NODE_OUTPUTS[node_type]:
                    fail(f"{path} 引用了 {node_type} 节点 {head} 不存在的输出 {tail}")
    ok(f"变量引用检查通过，共引用 {len(seen)} 个不同变量")


def check_http_bodies(doc: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> None:
    """把 HTTP 节点 body 中的环境变量替换为占位值，确认能构成合法 JSON。"""
    env_values = {
        var.get("name"): (var.get("value") or "PLACEHOLDER")
        for var in (doc.get("workflow") or {}).get("environment_variables") or []
    }
    for node_id, node in by_id.items():
        data = node.get("data") or {}
        if data.get("type") != "http-request":
            continue
        body = data.get("body") or {}
        if body.get("type") != "json":
            fail(f"HTTP 节点 {node_id} 的 body.type 应为 json")
            continue
        items = body.get("data") or []
        if len(items) != 1:
            fail(f"HTTP 节点 {node_id} 的 json body 必须恰好包含一项，实际 {len(items)} 项")
            continue
        raw = items[0].get("value") or ""
        # body 整体是一个变量引用时，运行时才成形，改查它引用的 code 节点输出是否为合法 JSON
        whole_reference = VARIABLE_PATTERN.fullmatch(raw.strip())
        if whole_reference:
            selector = whole_reference.group(1)
            head, _, tail = selector.partition(".")
            if head not in by_id:
                fail(f"HTTP 节点 {node_id} 的 body 引用了不存在的节点 {head}")
            else:
                code_node = by_id[head]
                if (code_node.get("data") or {}).get("type") != "code":
                    fail(f"HTTP 节点 {node_id} 的 body 引用了非 code 节点 {head}")
                elif tail not in ((code_node.get("data") or {}).get("outputs") or {}):
                    fail(f"HTTP 节点 {node_id} 的 body 引用了 {head} 未声明的输出 {tail}")
            continue
        substituted = VARIABLE_PATTERN.sub(
            lambda m: env_values.get(m.group(1).split(".")[-1], "PLACEHOLDER")
            if m.group(1).split(".")[0] == "env"
            else "PLACEHOLDER",
            raw,
        )
        try:
            json.loads(substituted)
        except json.JSONDecodeError as exc:
            fail(f"HTTP 节点 {node_id} 的 body 替换环境变量后不是合法 JSON：{exc}")
        if not str(data.get("url") or "").startswith("{{#env.PC_BASE_URL#}}"):
            fail(f"HTTP 节点 {node_id} 的 url 应以 {{#env.PC_BASE_URL#}} 开头")
        if "Authorization: Bearer {{#env.PC_AUTH_TOKEN#}}" not in str(data.get("headers") or ""):
            fail(f"HTTP 节点 {node_id} 的 headers 缺少 Bearer token 头")
    ok("HTTP 节点的 body / url / headers 结构检查通过")


def run_code_node(doc: dict[str, Any], by_id: dict[str, dict[str, Any]], inputs: dict[str, str]):
    """执行 Code 节点的 Python 代码，返回它产出的输出字典。"""
    node = next(
        node for node in by_id.values() if (node.get("data") or {}).get("type") == "code"
    )
    data = node["data"]
    namespace: dict[str, Any] = {}
    exec(compile(data["code"], "<dify-code-node>", "exec"), namespace)
    main = namespace["main"]
    return main(**inputs)


def check_code_node(doc: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> None:
    node = next(node for node in by_id.values() if (node.get("data") or {}).get("type") == "code")
    data = node["data"]
    declared = set((data.get("outputs") or {}).keys())
    if data.get("code_language") != "python3":
        fail(f"Code 节点语言应为 python3，实际为 {data.get('code_language')!r}")

    result = run_code_node(
        doc,
        by_id,
        {"player_input": "我把布丁按颜色排成彩虹了", "ledger_json": "{}", "scope_id": "scope-demo"},
    )
    if set(result.keys()) != declared:
        fail(
            "Code 节点返回的键与声明的输出不一致："
            f"多出 {sorted(set(result) - declared)}，缺少 {sorted(declared - set(result))}"
        )
    for key, value in result.items():
        if not isinstance(value, str):
            fail(f"Code 节点输出 {key} 应为字符串，实际为 {type(value).__name__}")
    ok(f"Code 节点可执行，返回 {len(result)} 个字符串输出，与声明一致")


def check_round_trip(doc: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> None:
    """端到端验证：恶作剧 -> 写入记忆 -> 下一轮从记忆重建状态 -> 翻账本能引用旧事。"""
    scope = "scope-demo"

    first = run_code_node(
        doc,
        by_id,
        {
            "player_input": "我把货架上的布丁按颜色排成彩虹了，还给价目表画了两撇胡子。",
            "ledger_json": "{}",
            "scope_id": scope,
        },
    )
    if first["intent"] != "prank":
        fail(f"意图判定错误：期望 prank，实际 {first['intent']}")
    if first["grudge"] != "2" or first["warmth"] != "-1":
        fail(f"恶作剧状态增量错误：warmth={first['warmth']} grudge={first['grudge']}")
    payload = json.loads(first["remember_payload"])
    if payload["scope_id"] != scope or payload["kind"] != "npc-event":
        fail(f"写回请求体结构错误：{payload}")
    if "彩虹" not in payload["text"]:
        fail(f"写回请求体丢失了玩家原话：{payload['text']}")

    # 模拟下一轮：把刚写入的条目作为账本读回来
    ledger = {
        "entries": [
            {"kind": "npc-event", "text": payload["text"], "state": "active"},
        ]
    }
    second = run_code_node(
        doc,
        by_id,
        {
            "player_input": "你还记得我上次干了什么吗？",
            "ledger_json": json.dumps(ledger, ensure_ascii=False),
            "scope_id": scope,
        },
    )
    if second["intent"] != "recall":
        fail(f"意图判定错误：期望 recall，实际 {second['intent']}")
    if second["grudge"] != "2" or second["warmth"] != "-1":
        fail(f"从长期记忆重建状态失败：warmth={second['warmth']} grudge={second['grudge']}")
    if "彩虹" not in second["ledger_digest"]:
        fail(f"账本摘要没有包含上一轮的记忆：{second['ledger_digest']!r}")
    if second["remember_payload"] != "":
        fail("recall 轮次不应写入新记忆")

    # 改名轮
    renamed = run_code_node(
        doc,
        by_id,
        {
            "player_input": "以后你就叫小笼包吧。",
            "ledger_json": "{}",
            "scope_id": scope,
        },
    )
    if renamed["intent"] != "rename":
        fail(f"意图判定错误：期望 rename，实际 {renamed['intent']}")
    rename_payload = json.loads(renamed["remember_payload"])
    if rename_payload["kind"] != "npc-name" or rename_payload["text"] != "name=小笼包":
        fail(f"改名写回内容错误：{rename_payload}")
    if renamed["npc_name"] != "小笼包":
        fail(f"改名后 NPC 名字未更新：{renamed['npc_name']}")

    # 示好轮
    gifted = run_code_node(
        doc,
        by_id,
        {
            "player_input": "给你带了根猫条，还有热豆浆。",
            "ledger_json": json.dumps(ledger, ensure_ascii=False),
            "scope_id": scope,
        },
    )
    if gifted["intent"] != "gift":
        fail(f"意图判定错误：期望 gift，实际 {gifted['intent']}")
    if gifted["warmth"] != "1" or gifted["grudge"] != "2":
        fail(f"示好后的累积状态错误：warmth={gifted['warmth']} grudge={gifted['grudge']}")

    # 闲聊轮不应写入记忆
    chatted = run_code_node(
        doc,
        by_id,
        {
            "player_input": "今天外面下雪了。",
            "ledger_json": json.dumps(ledger, ensure_ascii=False),
            "scope_id": scope,
        },
    )
    if chatted["intent"] != "smalltalk":
        fail(f"意图判定错误：期望 smalltalk，实际 {chatted['intent']}")
    if chatted["remember_payload"] != "":
        fail("闲聊轮次不应写入新记忆")
    ok("端到端闭环验证通过：写入 -> 读取 -> 重建状态 -> 翻账本复用旧记忆")


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DSL
    if not path.exists():
        print(f"找不到 DSL 文件：{path}")
        return 2

    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        print("DSL 顶层不是映射")
        return 2

    check_top_level(doc)
    by_id = check_nodes(doc["workflow"]["graph"])
    check_edges(doc["workflow"]["graph"], by_id)
    check_node_schemas(doc, by_id)
    check_variable_references(doc, by_id)
    check_http_bodies(doc, by_id)
    check_code_node(doc, by_id)
    check_round_trip(doc, by_id)

    for line in checks:
        print(f"[OK]   {line}")
    for line in errors:
        print(f"[FAIL] {line}")
    print(f"\n通过 {len(checks)} 项，失败 {len(errors)} 项")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
