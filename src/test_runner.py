"""
End-to-end test harness for the Gitea MCP Server.

Every backend interaction goes through the MCP server (Streamable HTTP JSON-RPC).
No direct Gitea API calls are made here.
"""

import asyncio
import base64
import json
import os
import sys
import time
import uuid
from typing import Any

import httpx
from toon_mcp import toon_to_json

from .client import TOOL_SPECS

MCP_SERVER_PORT = os.environ.get("MCP_SERVER_PORT", "")
API_KEY = os.environ.get("API_KEY", "")
MCP_URL = f"http://localhost:{MCP_SERVER_PORT}/mcp"
TARGET_USER = os.environ.get("GITEA_TEST_USER", "amanda")

MCP_HEADERS = {"Authorization": f"Bearer {API_KEY}"}

rid = uuid.uuid4().hex[:8]
FUTURE = "2030-01-01T00:00:00+00:00"
SSH_PUB = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM4BO+Dunv9YgnPxFu+SEuhMDK+9UZA7gHhAtZzWel22 gitea-mcp-test"

results: list[dict[str, Any]] = []
called: set[str] = set()
state: dict[str, Any] = {}


# =============================================================================
# MCP Session
# =============================================================================


class MCPSession:
    def __init__(self, url: str, headers: dict[str, str]):
        self.url = url
        self.base_headers = {
            **headers,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self.headers = dict(self.base_headers)
        self.client = httpx.AsyncClient(timeout=120.0)
        self._request_id = 0
        self._session_id: str | None = None

    def _capture_session(self, response) -> None:
        sid = response.headers.get("mcp-session-id")
        if sid:
            self._session_id = sid
            self.headers = {**self.base_headers, "mcp-session-id": sid}

    async def __aenter__(self):
        await self._initialize()
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    async def _send_notification(self, method: str, params: dict | None = None) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        if params:
            payload["params"] = params
        response = await self.client.post(self.url, headers=self.headers, json=payload)
        self._capture_session(response)
        if response.status_code not in (200, 202):
            response.raise_for_status()

    async def _send(self, method: str, params: dict | None = None) -> dict:
        self._request_id += 1
        payload = {"jsonrpc": "2.0", "id": self._request_id, "method": method}
        if params:
            payload["params"] = params
        response = await self.client.post(self.url, headers=self.headers, json=payload)
        if response.status_code == 202:
            return {}
        response.raise_for_status()
        self._capture_session(response)
        data = response.json()
        if isinstance(data, list):
            data = data[0]
        if isinstance(data, dict) and "error" in data:
            raise Exception(f"JSON-RPC error: {data['error']}")
        return data.get("result", {})

    async def _initialize(self) -> dict:
        result = await self._send(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "gitea-test-runner", "version": "1.0"},
            },
        )
        await self._send_notification("notifications/initialized")
        return result

    async def list_tools(self) -> list[dict]:
        result = await self._send("tools/list")
        return result.get("tools", result)

    async def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        params = {"name": name}
        if arguments:
            params["arguments"] = arguments
        return await self._send("tools/call", params)


# =============================================================================
# Helpers
# =============================================================================


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def is_error(result: dict[str, Any]) -> str | None:
    if "error" in result:
        err = result["error"]
        return err.get("message", str(err))
    if result.get("isError"):
        for c in result.get("content", []):
            if c.get("type") == "text":
                txt = c["text"]
                if txt.startswith("Error calling tool"):
                    return txt.split(":", 1)[1].strip() if ":" in txt else txt
                return txt
    return None


def extract_content(result: dict[str, Any]) -> Any:
    if result.get("isError"):
        return {}
    for c in result.get("content", []):
        if c.get("type") == "text":
            try:
                return json.loads(c["text"])
            except json.JSONDecodeError:
                try:
                    return toon_to_json(c["text"])
                except Exception:
                    return c["text"]
    return result.get("structuredContent", {})


def list_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return v
            if isinstance(v, str):
                try:
                    parsed = toon_to_json(v)
                except Exception:
                    continue
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict):
                    for vv in parsed.values():
                        if isinstance(vv, list):
                            return vv
    return []


def b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


async def run(
    session: MCPSession, label: str, tool: str, params: dict | None = None
) -> Any:
    if params is None:
        params = {}
    called.add(tool)
    result = await session.call_tool(tool, params)
    err = is_error(result)
    if err:
        results.append(
            {"label": label, "tool": tool, "status": "FAILED", "reason": err}
        )
        log(f"  FAIL {label}: {err}")
        return None
    data = extract_content(result)
    results.append({"label": label, "tool": tool, "status": "PASSED", "data": data})
    log(f"  PASS {label}")
    return data


def capture(tool: str, args: dict, data: Any) -> None:
    if not isinstance(data, dict):
        return
    if "id" in data:
        state[f"{tool}_id"] = data["id"]
    if "index" in data:
        state[f"{tool}_index"] = data["index"]
    if tool == "user_get_current":
        state["owner"] = data.get("login") or data.get("username") or state.get("owner")
    elif tool == "create_current_user_repo":
        state["repo"] = args.get("name")
        state["repo_id"] = data.get("id")
        if data.get("owner"):
            state["owner"] = data["owner"].get("login", state.get("owner"))
    elif tool == "repo_create_branch":
        if args.get("new_branch_name") == state.get("test_branch"):
            state["branch"] = args.get("new_branch_name")
        else:
            state["extra_branch"] = args.get("new_branch_name")
    elif tool == "repo_rename_branch":
        state["renamed_branch"] = args.get("name")
    elif tool == "repo_create_file":
        commit = data.get("commit") or {}
        content = data.get("content") or {}
        state["sha"] = commit.get("sha") or content.get("sha") or state.get("sha")
        state["file_sha"] = content.get("sha")
        if not state.get("test_file_sha"):
            state["test_file_sha"] = content.get("sha")
        tree = commit.get("tree") or {}
        state["tree_sha"] = tree.get("sha")
    elif tool == "repo_update_file":
        content = data.get("content") or {}
        if content.get("sha"):
            state["file2_sha"] = content.get("sha")
    elif tool == "repo_create_tag":
        state["tag"] = args.get("tag_name")
        state["tag_sha"] = data.get("id")
    elif tool == "repo_create_wiki_page":
        state["wiki_title"] = data.get("title") or args.get("title")
        state["wiki_page"] = data.get("sub_url") or data.get("title") or args.get("title")
    elif tool == "repo_edit_wiki_page":
        state["wiki_page"] = data.get("sub_url") or state.get("wiki_page")
    elif tool in ("issue_create_label",):
        state["label_id"] = data.get("id")
    elif tool == "org_create_label":
        state["org_label_id"] = data.get("id")
    elif tool == "issue_create_milestone":
        state["milestone_id"] = data.get("id")
    elif tool == "issue_create_issue":
        count = state.get("_issue_count", 0) + 1
        state["_issue_count"] = count
        idx = data.get("number") or data.get("index")
        if count == 1:
            state["issue_index"] = idx
            state["issue_id"] = data.get("id")
        elif count == 2:
            state["issue2_index"] = idx
            state["issue2_id"] = data.get("id")
        elif count == 3:
            state["issue3_index"] = idx
            state["issue3_id"] = data.get("id")
    elif tool == "issue_create_comment":
        state["comment_id"] = data.get("id")
    elif tool == "repo_create_pull_request":
        state["pr_index"] = data.get("number") or data.get("index")
        state["pr_id"] = data.get("id")
        head = data.get("head") or {}
        state["pr_head_sha"] = head.get("sha") or state.get("sha")
    elif tool == "repo_create_pull_review":
        if not state.get("review_id"):
            state["review_id"] = data.get("id")
        else:
            state["last_review_id"] = data.get("id")
    elif tool == "repo_get_pull_review_comments":
        items = list_items(data)
        if items:
            state["review_comment_id"] = items[0].get("id")
    elif tool == "repo_create_status":
        state["status_id"] = data.get("id")
    elif tool == "repo_create_release":
        state["release_id"] = data.get("id")
    elif tool == "issue_add_time":
        state["time_id"] = data.get("id")
    elif tool == "issue_tracked_times":
        items = list_items(data)
        if items:
            state["time_id"] = items[0].get("id")
    elif tool == "repo_create_branch_protection":
        state["branch_protection_name"] = (
            data.get("rule_name") or data.get("branch_name") or args.get("branch_name")
        )
        state["branch_protection_id"] = data.get("id")
    elif tool == "repo_create_tag_protection":
        state["tag_protection_id"] = data.get("id")
    elif tool == "repo_create_key":
        state["key_id"] = data.get("id")
    elif tool == "repo_create_project":
        state["project_id"] = data.get("id")
    elif tool == "repo_create_project_column":
        state["column_id"] = data.get("id")
    elif tool == "repo_create_project_workflow":
        state["workflow_id"] = data.get("id")
    elif tool == "org_create":
        state["org"] = args.get("username")
    elif tool == "rename_org":
        state["org"] = data.get("username") or args.get("new_name") or state.get("org")
    elif tool == "org_create_team":
        state["team_id"] = data.get("id")
        state["team_name"] = data.get("name") or args.get("name")
    elif tool == "org_create_project":
        state["org_project_id"] = data.get("id")
    elif tool == "org_create_project_column":
        state["org_column_id"] = data.get("id")
    elif tool == "org_create_project_workflow":
        state["org_workflow_id"] = data.get("id")
    elif tool == "user_current_create_project":
        state["user_project_id"] = data.get("id")
    elif tool == "user_current_create_project_column":
        state["user_column_id"] = data.get("id")
    elif tool == "user_current_create_project_workflow":
        state["user_workflow_id"] = data.get("id")
    elif tool == "repo_migrate":
        state["mirror_repo"] = args.get("repo_name")
    elif tool == "generate_repo":
        state["gen_repo"] = args.get("name")
    elif tool == "create_fork":
        state["fork_repo"] = data.get("name")
    elif tool == "upload_generic_package":
        state["pkg_name"] = args.get("package_name")
        state["pkg_version"] = args.get("version")
    elif tool == "notify_get_list":
        items = list_items(data)
        if items:
            state["thread_id"] = items[0].get("id")


# =============================================================================
# Setup fixtures
# =============================================================================


async def setup(session: MCPSession) -> None:
    log("\n=== Setup Fixtures ===")
    for key in (
        "issue_index", "issue_id", "issue2_index", "issue2_id", "issue3_index",
        "comment_id", "label_id", "milestone_id", "pr_index", "pr_id",
        "review_id", "review_comment_id", "project_id", "column_id", "workflow_id",
        "org_project_id", "org_column_id", "org_workflow_id", "user_project_id",
        "user_column_id", "user_workflow_id", "team_id", "key_id",
        "tag_protection_id", "thread_id", "pkg_name", "pkg_version",
    ):
        state.setdefault(key, 0)
    state.setdefault("sha", "")
    state.setdefault("pr_head_sha", "")
    state.setdefault("comment_id", 0)
    state.setdefault("org", f"t{rid}org")
    data = await run(session, "S001 get_version", "get_version")
    capture("get_version", {}, data)
    data = await run(session, "S002 user_get_current", "user_get_current")
    capture("user_get_current", {}, data)

    state["repo"] = f"t{rid}-repo"
    state["base"] = "main"
    state["test_branch"] = f"t{rid}-branch"
    state["rename_branch"] = f"t{rid}-rename"
    state["file_branch"] = f"t{rid}-filebranch"
    state["file2_path"] = "update-delete.txt"
    state["filepath"] = "test.txt"
    state["tag"] = f"v{rid}"
    state["wiki_page"] = f"t{rid}-wiki"
    state["src_repo"] = f"t{rid}-src"
    state["mirror_repo"] = f"t{rid}-mirror"
    state["template_repo"] = f"t{rid}-tmpl"
    state["gen_repo"] = f"t{rid}-gen"
    state["org"] = f"t{rid}org"
    state["pkg_name"] = f"t{rid}-pkg"
    state["pkg_version"] = "1.0.0"

    data = await run(
        session,
        "S003 create_repo",
        "create_current_user_repo",
        {
            "name": state["repo"],
            "description": f"test repo {rid}",
            "auto_init": True,
            "private": False,
        },
    )
    capture("create_current_user_repo", {"name": state["repo"]}, data)

    data = await run(
        session,
        "S004 create_branch",
        "repo_create_branch",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "new_branch_name": state["test_branch"],
            "old_branch_name": state["base"],
        },
    )
    capture("repo_create_branch", {"new_branch_name": state["test_branch"]}, data)

    data = await run(
        session,
        "S004b rename_branch_fixture",
        "repo_create_branch",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "new_branch_name": state["rename_branch"],
            "old_branch_name": state["base"],
        },
    )

    await run(
        session,
        "S004c file_branch_fixture",
        "repo_create_branch",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "new_branch_name": state["file_branch"],
            "old_branch_name": state["base"],
        },
    )

    data = await run(
        session,
        "S005 create_file",
        "repo_create_file",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "filepath": state["filepath"],
            "content": "hello from gitea mcp test\n",
            "message": "add test file",
            "branch": state["test_branch"],
        },
    )
    capture("repo_create_file", {"filepath": state["filepath"]}, data)

    data = await run(
        session,
        "S005b diff_file",
        "repo_create_file",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "filepath": f"diff-{rid}.txt",
            "content": "old\n",
            "message": "diff fixture",
            "branch": state["file_branch"],
        },
    )

    data = await run(
        session,
        "S005c update_delete_file",
        "repo_create_file",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "filepath": state["file2_path"],
            "content": "update me\n",
            "message": "file fixture",
            "branch": state["file_branch"],
        },
    )
    if isinstance(data, dict):
        c = data.get("content") or {}
        state["file2_sha"] = c.get("sha")

    data = await run(
        session,
        "S006 create_tag",
        "repo_create_tag",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "tag_name": state["tag"],
            "message": "annotated test tag",
            "target": state["test_branch"],
        },
    )
    capture("repo_create_tag", {"tag_name": state["tag"]}, data)

    data = await run(
        session,
        "S006b create_release",
        "repo_create_release",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "tag_name": state["tag"],
            "name": f"t{rid}-release",
            "body": "test release body",
            "draft": False,
            "prerelease": False,
        },
    )
    capture("repo_create_release", {}, data)
    data = await run(
        session,
        "S006c create_release2",
        "repo_create_release",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "tag_name": f"v{rid}-del",
            "name": f"t{rid}-release2",
            "body": "second release",
            "draft": False,
            "prerelease": False,
        },
    )
    if isinstance(data, dict):
        state["release2_id"] = data.get("id")

    data = await run(
        session,
        "S007 create_wiki",
        "repo_create_wiki_page",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "title": state["wiki_page"],
            "content": "wiki content one\n",
            "message": "create wiki",
        },
    )
    capture("repo_create_wiki_page", {"title": state["wiki_page"]}, data)
    data = await run(
        session,
        "S008 edit_wiki",
        "repo_edit_wiki_page",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "pageName": state["wiki_page"],
            "title": state.get("wiki_title") or state["wiki_page"],
            "content": "wiki content two\n",
            "message": "update wiki",
        },
    )
    capture("repo_edit_wiki_page", {}, data)

    data = await run(
        session,
        "S009 create_label",
        "issue_create_label",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "name": f"t{rid}-label",
            "color": "#a6cee3",
            "description": "test label",
        },
    )
    capture("issue_create_label", {}, data)

    data = await run(
        session,
        "S010 create_milestone",
        "issue_create_milestone",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "title": f"t{rid}-ms",
            "description": "test milestone",
            "due_on": FUTURE,
        },
    )
    capture("issue_create_milestone", {}, data)

    data = await run(
        session,
        "S011 create_issue",
        "issue_create_issue",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "title": f"t{rid}-issue-one",
            "body": "first test issue",
        },
    )
    capture("issue_create_issue", {}, data)
    data = await run(
        session,
        "S012 create_issue_two",
        "issue_create_issue",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "title": f"t{rid}-issue-two",
            "body": "second test issue",
        },
    )
    capture("issue_create_issue", {}, data)
    data3 = await run(
        session,
        "S012b create_issue_three",
        "issue_create_issue",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "title": f"t{rid}-issue-three",
            "body": "third test issue",
        },
    )
    if isinstance(data3, dict):
        state["issue3_index"] = data3.get("number") or data3.get("index") or 0

    data = await run(
        session,
        "S013 create_comment",
        "issue_create_comment",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["issue_index"],
            "body": "test comment",
        },
    )
    capture("issue_create_comment", {}, data)
    data = await run(
        session,
        "S013b create_comment2",
        "issue_create_comment",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["issue_index"],
            "body": "second test comment",
        },
    )
    if isinstance(data, dict):
        state["comment2_id"] = data.get("id")

    await run(
        session,
        "S014 comment_reaction",
        "issue_post_comment_reaction",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "id": state["comment_id"],
            "content": "+1",
        },
    )
    await run(
        session,
        "S015 issue_reaction",
        "issue_post_issue_reaction",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["issue_index"],
            "content": "+1",
        },
    )
    await run(
        session,
        "S016 add_label",
        "issue_add_label",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["issue_index"],
            "labels": [state["label_id"]],
        },
    )
    await run(
        session,
        "S017b add_assignee",
        "issue_add_assignees",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["issue_index"],
            "assignees": [TARGET_USER],
        },
    )
    await run(
        session,
        "S018 add_time",
        "issue_add_time",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["issue_index"],
            "time": 3600,
        },
    )
    await run(
        session,
        "S018b add_time2",
        "issue_add_time",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["issue_index"],
            "time": 1800,
        },
    )
    await run(
        session,
        "S019 start_stopwatch",
        "issue_start_stop_watch",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["issue_index"],
        },
    )
    await run(
        session,
        "S020 add_subscription",
        "issue_add_subscription",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["issue_index"],
            "user": state["owner"],
        },
    )
    await run(
        session,
        "S021 add_dependency",
        "issue_create_issue_dependencies",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": str(state["issue_index"]),
            "body_index": state["issue2_index"],
            "body_owner": state["owner"],
            "body_repo": state["repo"],
        },
    )
    await run(
        session,
        "S022 add_block",
        "issue_create_issue_blocking",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": str(state["issue_index"]),
            "body_index": state.get("issue3_index", 0),
            "body_owner": state["owner"],
            "body_repo": state["repo"],
        },
    )
    await run(
        session,
        "S023 deadline",
        "issue_edit_issue_deadline",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["issue_index"],
            "due_date": FUTURE,
        },
    )
    await run(
        session,
        "S024 pin_issue",
        "pin_issue",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["issue_index"],
        },
    )
    await run(
        session,
        "S025 lock_issue",
        "issue_lock_issue",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["issue_index"],
        },
    )

    await run(
        session,
        "S026 add_collaborator",
        "repo_add_collaborator",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "collaborator": TARGET_USER,
            "permission": "write",
        },
    )

    data = await run(
        session,
        "S027 create_pr",
        "repo_create_pull_request",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "head": state["test_branch"],
            "base": state["base"],
            "title": f"t{rid}-pr",
            "body": "test pull request",
            "reviewers": [TARGET_USER],
        },
    )
    capture("repo_create_pull_request", {}, data)

    await run(
        session,
        "S027b base_advance",
        "repo_create_file",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "filepath": f"base-{rid}.txt",
            "content": "base advance\n",
            "message": "advance base",
            "branch": state["base"],
        },
    )

    data = await run(
        session,
        "S028 create_status",
        "repo_create_status",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "sha": state.get("pr_head_sha") or state.get("sha") or "",
            "state": "pending",
            "status_context": "gitea-mcp-check",
            "status_description": "pending test status",
        },
    )
    capture("repo_create_status", {}, data)


    data = await run(
        session,
        "S029 create_review",
        "repo_create_pull_review",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["pr_index"],
            "review_event": "COMMENT",
            "review_body": "review body",
            "comment_path": state["filepath"],
            "comment_body": "line comment",
            "comment_new_position": 1,
        },
    )
    capture("repo_create_pull_review", {}, data)
    data = await run(
        session,
        "S029b pending_review",
        "repo_create_pull_review",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["pr_index"],
            "review_event": "PENDING",
            "review_body": "pending review",
        },
    )
    if isinstance(data, dict):
        state["pending_review_id"] = data.get("id")
    data = await run(
        session,
        "S029c approved_review",
        "repo_create_pull_review",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["pr_index"],
            "review_event": "APPROVED",
            "review_body": "approved review",
            "sudo": TARGET_USER,
        },
    )
    if isinstance(data, dict):
        state["approved_review_id"] = data.get("id")
    data = await run(
        session,
        "S029d changes_review",
        "repo_create_pull_review",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state["pr_index"],
            "review_event": "REQUEST_CHANGES",
            "review_body": "changes review",
            "sudo": TARGET_USER,
        },
    )
    if isinstance(data, dict):
        state["changes_review_id"] = data.get("id")

    data = await run(
        session,
        "S030 review_comments",
        "repo_get_pull_review_comments",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state.get("pr_index", 0),
            "id": state.get("review_id", 0),
        },
    )
    capture("repo_get_pull_review_comments", {}, data)

    await run(
        session,
        "S031 request_reviewers",
        "repo_create_pull_review_requests",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state.get("pr_index", 0),
            "reviewers": [TARGET_USER],
        },
    )

    data = await run(
        session,
        "S032 branch_protection",
        "repo_create_branch_protection",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "branch_name": state["base"],
            "required_approvals": 0,
            "enable_push": True,
            "enable_status_check": True,
            "status_check_contexts": ["gitea-mcp-check"],
        },
    )
    capture("repo_create_branch_protection", {}, data)
    await run(
        session,
        "S028a update_pr_branch",
        "repo_update_pull_request",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state.get("pr_index", 0),
        },
    )
    data = await run(
        session,
        "S028a1 refresh_pr_head",
        "repo_get_pull_request",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state.get("pr_index", 0),
            "include_all_fields": True,
        },
    )
    if isinstance(data, dict):
        head = data.get("head") or {}
        if head.get("sha"):
            state["pr_head_sha"] = head.get("sha")
    await asyncio.sleep(3)
    await run(
        session,
        "S028b schedule_auto_merge",
        "repo_merge_pull_request",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state.get("pr_index", 0),
            "do": "merge",
            "merge_when_checks_succeed": True,
        },
    )
    await run(
        session,
        "S028c cancel_auto_merge",
        "repo_cancel_scheduled_auto_merge",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "index": state.get("pr_index", 0),
        },
    )

    data = await run(
        session,
        "S033 tag_protection",
        "repo_create_tag_protection",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "name_pattern": f"v{rid}-prot*",
            "whitelist_usernames": [TARGET_USER],
        },
    )
    capture("repo_create_tag_protection", {}, data)

    data = await run(
        session,
        "S034 deploy_key",
        "repo_create_key",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "public_key": SSH_PUB,
            "title": f"t{rid}-key",
        },
    )
    capture("repo_create_key", {}, data)

    data = await run(
        session,
        "S040 create_org",
        "org_create",
        {
            "username": state["org"],
            "description": "test organization",
            "full_name": "Test Org",
            "visibility": "public",
            "email": f"{state['org']}@example.com",
        },
    )
    capture("org_create", {"username": state["org"]}, data)
    data = await run(
        session,
        "S041 org_label",
        "org_create_label",
        {
            "org": state["org"],
            "name": f"t{rid}-orglabel",
            "color": "#b2df8a",
            "description": "org label",
        },
    )
    capture("org_create_label", {}, data)
    data = await run(
        session,
        "S042 org_team",
        "org_create_team",
        {
            "org": state["org"],
            "name": f"t{rid}-team",
            "permission": "write",
            "description": "test team",
            "includes_all_repositories": False,
            "units": ["repo.code", "repo.issues", "repo.pulls", "repo.releases", "repo.wiki", "repo.projects", "repo.packages", "repo.actions"],
        },
    )
    capture("org_create_team", {}, data)
    data = await run(
        session,
        "S042b org_team2",
        "org_create_team",
        {
            "org": state["org"],
            "name": f"t{rid}-team2",
            "permission": "write",
            "description": "second test team",
            "includes_all_repositories": False,
            "units": ["repo.code", "repo.issues", "repo.pulls", "repo.releases", "repo.wiki", "repo.projects", "repo.packages", "repo.actions"],
        },
    )
    if isinstance(data, dict):
        state["team2_id"] = data.get("id")
        state["team2_name"] = data.get("name")
    data = await run(
        session,
        "S042c org_team3",
        "org_create_team",
        {
            "org": state["org"],
            "name": f"t{rid}-team3",
            "permission": "read",
            "description": "third test team",
            "includes_all_repositories": False,
            "units": ["repo.code", "repo.issues", "repo.pulls", "repo.releases", "repo.wiki", "repo.projects", "repo.packages", "repo.actions"],
        },
    )
    if isinstance(data, dict):
        state["team3_id"] = data.get("id")
        state["team3_name"] = data.get("name")
    await run(
        session,
        "S043 team_member",
        "org_add_team_member",
        {
            "id": state["team_id"],
            "username": TARGET_USER,
        },
    )
    data = await run(
        session,
        "S044a org_repo",
        "create_org_repo",
        {
            "org": state["org"],
            "name": f"t{rid}-orgrepo",
            "description": "org repository",
            "auto_init": True,
            "private": False,
        },
    )
    if isinstance(data, dict):
        state["org_repo"] = data.get("name") or f"t{rid}-orgrepo"
    data = await run(
        session,
        "S044a2 org_issue",
        "issue_create_issue",
        {
            "owner": state["org"],
            "repo": state.get("org_repo", f"t{rid}-orgrepo"),
            "title": f"t{rid}-orgissue",
            "body": "org project issue",
        },
    )
    if isinstance(data, dict):
        state["org_issue_id"] = data.get("id")
    await run(
        session,
        "S044 team_repo",
        "org_add_team_repository",
        {
            "id": state["team_id"],
            "org": state["org"],
            "repo": state.get("org_repo", f"t{rid}-orgrepo"),
        },
    )
    await run(
        session,
        "S044b team2_repo",
        "org_add_team_repository",
        {
            "id": state.get("team2_id", 0),
            "org": state["org"],
            "repo": state.get("org_repo", f"t{rid}-orgrepo"),
        },
    )
    await run(
        session,
        "S045 public_member",
        "org_publicize_member",
        {
            "org": state["org"],
            "username": TARGET_USER,
        },
    )

    data = await run(
        session,
        "S053a repo_project",
        "repo_create_project",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "title": f"t{rid}-project",
            "description": "repo project",
        },
    )
    capture("repo_create_project", {}, data)
    data = await run(
        session,
        "S053b repo_project_column",
        "repo_create_project_column",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "id": state["project_id"],
            "title": f"t{rid}-column",
        },
    )
    capture("repo_create_project_column", {}, data)
    data = await run(
        session,
        "S053b2 repo_project_column2",
        "repo_create_project_column",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "id": state["project_id"],
            "title": f"t{rid}-column2",
        },
    )
    if isinstance(data, dict):
        state["column2_id"] = data.get("id")
    await run(
        session,
        "S053c repo_project_issue",
        "repo_add_issue_to_project_column",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "id": state["project_id"],
            "column_id": state["column_id"],
            "issue_id": state["issue_id"],
        },
    )

    data = await run(
        session,
        "S053d org_project",
        "org_create_project",
        {
            "org": state["org"],
            "title": f"t{rid}-orgproject",
            "description": "org project",
        },
    )
    capture("org_create_project", {}, data)
    data = await run(
        session,
        "S053e org_project_column",
        "org_create_project_column",
        {
            "org": state["org"],
            "id": state["org_project_id"],
            "title": f"t{rid}-orgcolumn",
        },
    )
    capture("org_create_project_column", {}, data)
    data = await run(
        session,
        "S053e2 org_project_column2",
        "org_create_project_column",
        {
            "org": state["org"],
            "id": state["org_project_id"],
            "title": f"t{rid}-orgcolumn2",
        },
    )
    if isinstance(data, dict):
        state["org_column2_id"] = data.get("id")
    await run(
        session,
        "S053f org_project_issue",
        "org_add_issue_to_project_column",
        {
            "org": state["org"],
            "id": state["org_project_id"],
            "column_id": state["org_column_id"],
            "issue_id": state.get("org_issue_id", 0),
        },
    )

    data = await run(
        session,
        "S053g user_project",
        "user_current_create_project",
        {
            "title": f"t{rid}-userproject",
            "description": "user project",
        },
    )
    capture("user_current_create_project", {}, data)
    data = await run(
        session,
        "S053h user_project_column",
        "user_current_create_project_column",
        {
            "id": state["user_project_id"],
            "title": f"t{rid}-usercolumn",
        },
    )
    capture("user_current_create_project_column", {}, data)
    data = await run(
        session,
        "S053h2 user_project_column2",
        "user_current_create_project_column",
        {
            "id": state["user_project_id"],
            "title": f"t{rid}-usercolumn2",
        },
    )
    if isinstance(data, dict):
        state["user_column2_id"] = data.get("id")
    await run(
        session,
        "S053i user_project_issue",
        "user_current_add_issue_to_project_column",
        {
            "id": state["user_project_id"],
            "column_id": state["user_column_id"],
            "issue_id": state["issue_id"],
        },
    )

    await run(
        session, "S054 follow", "user_current_put_follow", {"username": TARGET_USER}
    )
    await run(
        session,
        "S055 subscribe_repo",
        "user_current_put_subscription",
        {
            "owner": state["owner"],
            "repo": state["repo"],
        },
    )

    data = await run(
        session,
        "S056 upload_package",
        "upload_generic_package",
        {
            "owner": state["owner"],
            "package_name": state["pkg_name"],
            "version": state["pkg_version"],
            "filename": "test.txt",
            "content": "hello package\n",
        },
    )
    capture(
        "upload_generic_package",
        {"package_name": state["pkg_name"], "version": state["pkg_version"]},
        data,
    )
    await run(
        session,
        "S057 link_package",
        "link_package",
        {
            "owner": state["owner"],
            "type": "generic",
            "name": state["pkg_name"],
            "repo_name": state["repo"],
        },
    )

    data = await run(
        session,
        "S058 notification_issue",
        "issue_create_issue",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "title": f"t{rid}-notify",
            "body": "notification fixture",
            "assignee": state["owner"],
            "sudo": TARGET_USER,
        },
    )
    capture("issue_create_issue_sudo", {}, data)
    await asyncio.sleep(2)
    data = await run(session, "S059 notifications", "notify_get_list", {"all": True})
    capture("notify_get_list", {}, data)

    # Migration/mirror fixture
    data = await run(
        session,
        "S060 create_source_repo",
        "create_current_user_repo",
        {
            "name": state["src_repo"],
            "description": "mirror source",
            "auto_init": True,
            "private": False,
        },
    )
    capture("create_source_repo", {"name": state["src_repo"]}, data)
    await run(
        session,
        "S061 source_file",
        "repo_create_file",
        {
            "owner": state["owner"],
            "repo": state["src_repo"],
            "filepath": "source.txt",
            "content": "source one\n",
            "message": "source one",
        },
    )
    data = await run(
        session,
        "S062 migrate_mirror",
        "repo_migrate",
        {
            "clone_addr": f"http://localhost:3000/{state['owner']}/{state['src_repo']}.git",
            "repo_name": state["mirror_repo"],
            "description": "mirror copy",
            "mirror": True,
            "private": False,
            "repo_owner": state["owner"],
        },
    )
    capture("repo_migrate", {"repo_name": state["mirror_repo"]}, data)
    await run(
        session,
        "S063 source_file_two",
        "repo_create_file",
        {
            "owner": state["owner"],
            "repo": state["src_repo"],
            "filepath": "source2.txt",
            "content": "source two\n",
            "message": "source two",
        },
    )

    # Template/generate fixture
    data = await run(
        session,
        "S064 create_template",
        "create_current_user_repo",
        {
            "name": state["template_repo"],
            "description": "template repo",
            "auto_init": True,
            "private": False,
            "template": True,
        },
    )
    capture("create_template", {"name": state["template_repo"]}, data)
    data = await run(
        session,
        "S065 generate_repo",
        "generate_repo",
        {
            "template_owner": state["owner"],
            "template_repo": state["template_repo"],
            "owner": state["owner"],
            "name": state["gen_repo"],
            "description": "generated repo",
            "private": False,
            "git_content": True,
        },
    )
    capture("generate_repo", {"name": state["gen_repo"]}, data)

    # Fork fixture (into org)
    data = await run(
        session,
        "S066 fork_repo",
        "create_fork",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "organization": state["org"],
        },
    )
    capture("create_fork", {}, data)
    await run(
        session,
        "S066b fork_upstream_commit",
        "repo_create_file",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "filepath": f"fork-{rid}.txt",
            "content": "fork upstream\n",
            "message": "fork upstream commit",
            "branch": state["base"],
        },
    )

    # Topics fixture
    await run(
        session,
        "S067 add_topic",
        "repo_add_topic",
        {
            "owner": state["owner"],
            "repo": state["repo"],
            "topic": f"t{rid}topic",
        },
    )


# =============================================================================
# Generic argument builder
# =============================================================================


def path_value(tool: str, name: str) -> Any:
    if name == "owner":
        return state.get("owner", "")
    if name == "repo":
        return state.get("repo", "")
    if name == "template_owner":
        return state.get("owner", "")
    if name == "template_repo":
        return state.get("template_repo", "")
    if name == "org":
        return state.get("org", "")
    if name == "branch":
        return state.get("branch", state.get("base"))
    if name == "tag":
        return state.get("tag", "")
    if name == "sha":
        if tool == "get_annotated_tag":
            return state.get("tag_sha", state.get("sha", ""))
        if tool == "repo_get_commit_pull_request":
            return state.get("pr_head_sha", state.get("sha", ""))
        return state.get("sha", "")
    if name == "ref":
        if tool == "repo_list_git_refs":
            return f"heads/{state.get('base', 'main')}"
        return state.get("base", "main")
    if name == "filepath":
        return state.get("filepath", "test.txt")
    if name == "pageName":
        return state.get("wiki_page", "")
    if name == "position":
        return 2
    if name == "compare_range":
        return f"{state.get('base', 'main')}...{state.get('branch', 'main')}"
    if name == "base":
        return state.get("base", "main")
    if name == "head":
        return state.get("branch", "main")
    if name == "index":
        if "pull" in tool or "review" in tool:
            return state.get("pr_index", 1)
        return state.get("issue_index", 1)
    if name == "team":
        return state.get("team_name", "")
    if name == "name":
        if "branch_protection" in tool:
            return state.get("branch_protection_name", "")
        if "package" in tool:
            return state.get("pkg_name", "")
        return state.get(f"{tool}_name", "")
    if name in ("id", "team_id"):
        if tool == "repo_get_by_id":
            return state.get("repo_id", 0)
        if tool == "issue_delete_time":
            return state.get("time_id", 0)
        if tool in ("notify_get_thread", "notify_read_thread"):
            return state.get("thread_id", 0)
        if "team" in tool:
            return state.get("team_id", 0)
        if "tag_protection" in tool:
            return state.get("tag_protection_id", 0)
        if "branch_protection" in tool:
            return state.get("branch_protection_name", "")
        if "key" in tool:
            return state.get("key_id", 0)
        if "label" in tool:
            return state.get(
                "org_label_id" if tool.startswith("org_") else "label_id", 0
            )
        if "milestone" in tool:
            return state.get("milestone_id", 0)
        if "release" in tool:
            return state.get("release_id", 0)
        if "review" in tool and "comment" in tool:
            return state.get("review_comment_id", 0)
        if "review" in tool:
            return state.get("review_id", 0)
        if "comment" in tool:
            return state.get("comment_id", 0)
        if "workflow" in tool:
            return state.get("workflow_id", 0)
        if "column" in tool:
            if tool.startswith("org_"):
                return state.get("org_column_id", 0)
            if tool.startswith("user_current_"):
                return state.get("user_column_id", 0)
            return state.get("column_id", 0)
        if "project" in tool:
            if tool.startswith("org_"):
                return state.get("org_project_id", 0)
            if tool.startswith("user_current_"):
                return state.get("user_project_id", 0)
            return state.get("project_id", 0)
        if "issue" in tool:
            return state.get("issue_id", 0)
        return state.get(f"{tool}_id", 0)
    if name == "column_id":
        return state.get("column_id", 0)
    if name == "workflow_id":
        return state.get("workflow_id", 0)
    if name == "issue_id":
        return state.get("issue_id", 0)
    if name == "project_id":
        return state.get("project_id", 0)
    if name == "repo_name":
        return state.get("repo", "")
    if name == "name":
        return state.get("pkg_name", f"t{rid}-pkg")
    if name == "version":
        return state.get("pkg_version", "1.0.0")
    if name == "type":
        return "generic"
    if name == "username":
        if tool in (
            "user_check_following",
            "user_list_following",
            "user_list_followers",
        ):
            return state.get("owner", "")
        if tool == "org_get_user_permissions" or tool == "org_list_user_orgs":
            return TARGET_USER
        return TARGET_USER
    if name == "target":
        return TARGET_USER
    if name == "collaborator":
        return TARGET_USER
    if name == "assignee":
        return TARGET_USER
    if name == "user":
        return TARGET_USER
    if name in ("secretname", "variablename", "token"):
        return "test"
    if name == "runner_id":
        return 0
    if name == "diffType":
        return "diff"
    if name == "archive":
        return "zip"
    return state.get(f"{tool}_{name}", f"t{rid}-{name}")


def required_value(tool: str, name: str) -> Any:
    mapping = {
        "description": f"t{rid}-description",
        "title": f"t{rid}-{tool}",
        "body": f"t{rid}-body",
        "name": f"t{rid}-{tool}",
        "color": "#a6cee3",
        "tag_name": state.get("tag", f"v{rid}"),
        "new_branch_name": f"t{rid}-newbranch",
        "head": state.get("branch", "main"),
        "base": state.get("base", "main"),
        "public_key": SSH_PUB,
        "content": "content\n",
        "content": "content\n",
        "message": "test message",
        "sha": state.get("sha", ""),
        "state": "success",
        "do": "merge",
        "event": "item_added_to_project",
        "time": 3600,
        "operation": "create",
        "path": state.get("filepath", "test.txt"),
        "review_event": "COMMENT",
        "review_body": "test review",
        "username": f"t{rid}org",
        "permission": "write",
        "labels": [state.get("label_id", 0)],
        "assignees": [TARGET_USER],
        "reviewers": [TARGET_USER],
        "due_date": FUTURE,
        "due_on": FUTURE,
        "email": f"{tool}@example.com",
        "full_name": f"t{rid} Full",
        "visibility": "public",
        "repo_name": state.get("repo", ""),
        "clone_addr": f"http://localhost:3000/{state.get('owner', '')}/{state.get('src_repo', '')}.git",
        "org": state.get("org", ""),
        "user": TARGET_USER,
        "topic": f"t{rid}topic",
        "name_pattern": f"v{rid}*",
        "branch_name": state.get("base", "main"),
        "from_path": state.get("filepath", "test.txt"),
        "old_branch_name": state.get("base", "main"),
        "old_ref_name": state.get("base", "main"),
    }
    if name in mapping:
        return mapping[name]
    return f"t{rid}-{name}"


def build_args(tool: str, spec: dict) -> dict:
    args: dict[str, Any] = {}
    path_params = set(spec.get("path_params", []))
    path_types = spec.get("path_types", {})
    for p in path_params:
        v = path_value(tool, p)
        pt = path_types.get(p)
        if pt == "string" and isinstance(v, int):
            v = str(v)
        elif pt == "integer" and isinstance(v, str) and v.isdigit():
            v = int(v)
        args[p] = v
    for p in spec.get("required", []):
        if p in path_params:
            continue
        if p in spec.get("body_params", []) or p in spec.get("query_params", []):
            args[p] = required_value(tool, p)
    # targeted overrides
    overrides = {
        "repo_edit": {"description": f"updated {rid}"},
        "repo_get_contents": {"ref": state.get("test_branch", "")},
        "repo_update_file": {
            "filepath": state.get("file2_path", "update-delete.txt"),
            "content": "updated file\n",
            "sha": state.get("file2_sha") or state.get("sha", ""),
            "message": "update file",
            "branch": state.get("file_branch", ""),
        },
        "repo_delete_file": {
            "filepath": state.get("file2_path", "update-delete.txt"),
            "sha": state.get("file2_sha") or state.get("sha", ""),
            "message": "delete file",
            "branch": state.get("file_branch", ""),
        },
        "repo_delete_branch": {"branch": state.get("renamed_branch") or state.get("rename_branch", "")},
        "repo_delete_release": {"id": state.get("release2_id", 0)},
        "repo_delete_tag": {"tag": state.get("tag", "")},
        "repo_delete_topic": {"topic": f"t{rid}topic"},
        "issue_replace_labels": {"labels": [state.get("label_id", 0)]},
        "issue_delete_issue_reaction": {"content": "+1"},
        "issue_delete_comment_reaction": {"content": "+1"},
        "repo_update_branch_protection_priorities": {"protection_ids": []},
        "notify_read_repo_list": {"all": "true", "to_status": "read"},
        "repo_list_teams": {"owner": state.get("org", ""), "repo": state.get("org_repo", "")},
        "repo_check_team": {
            "owner": state.get("org", ""),
            "repo": state.get("org_repo", ""),
            "team": state.get("team_name", ""),
        },
        "repo_add_team": {
            "owner": state.get("org", ""),
            "repo": state.get("org_repo", ""),
            "team": state.get("team3_name", ""),
        },
        "repo_delete_team": {
            "owner": state.get("org", ""),
            "repo": state.get("org_repo", ""),
            "team": state.get("team_name", ""),
        },
        "repo_merge_upstream": {
            "owner": state.get("org", ""),
            "repo": state.get("fork_repo", ""),
            "branch": state.get("base", "main"),
        },
        "org_remove_team_repository": {
            "id": state.get("team2_id", 0),
            "org": state.get("org", ""),
            "repo": state.get("org_repo", ""),
        },
        "org_delete_team": {"id": state.get("team2_id", 0)},
        "org_list_team_repo": {
            "org": state.get("org", ""),
            "repo": state.get("org_repo", ""),
        },

        "repo_rename_branch": {"branch": state.get("rename_branch", ""), "name": f"t{rid}-renamed"},
        "issue_edit_issue": {"title": f"t{rid}-issue-updated", "assignees": [TARGET_USER]},
        "issue_edit_comment": {"body": "updated comment"},
        "issue_edit_comment_deprecated": {"id": state.get("comment2_id", 0), "body": "updated comment"},
        "issue_delete_comment_deprecated": {"id": state.get("comment2_id", 0)},
        "issue_edit_label": {"name": f"t{rid}-label-updated"},
        "org_edit_label": {"name": f"t{rid}-orglabel-updated"},
        "org_edit_team": {"name": state.get("team_name", ""), "description": f"updated team {rid}"},
        "issue_edit_milestone": {"title": f"t{rid}-ms-updated"},
        "repo_edit_release": {"name": f"t{rid}-release-updated"},
        "repo_edit_pull_request": {"title": f"t{rid}-pr-updated"},
        "repo_create_project_column": {
            "id": state.get("project_id", 0),
            "title": f"t{rid}-column2",
        },
        "repo_create_project_workflow": {
            "id": state.get("project_id", 0),
            "event": "item_added_to_project",
        },
        "org_create_project_column": {
            "id": state.get("org_project_id", 0),
            "title": f"t{rid}-orgcol2",
        },
        "org_create_project_workflow": {
            "id": state.get("org_project_id", 0),
            "event": "item_added_to_project",
        },
        "user_current_create_project_column": {
            "id": state.get("user_project_id", 0),
            "title": f"t{rid}-usercol2",
        },
        "user_current_create_project_workflow": {
            "id": state.get("user_project_id", 0),
            "event": "item_added_to_project",
        },
        "repo_edit_project": {"title": f"t{rid}-project-updated", "description": "updated repo project"},
        "repo_edit_project_column": {"title": f"t{rid}-column-updated"},
        "repo_move_project_columns": {"column_ids": [state.get("column2_id", 0), state.get("column_id", 0)]},
        "repo_move_project_issue": {"column_id": state.get("column2_id", 0)},
        "repo_set_default_project_column": {"column_id": state.get("column2_id", 0)},
        "repo_remove_issue_from_project_column": {"column_id": state.get("column2_id", 0), "issue_id": state.get("issue_id", 0)},
        "repo_update_branch": {"new_commit_id": state.get("sha"), "force": True},
        "issue_add_assignees": {"assignees": [TARGET_USER]},
        "issue_remove_assignees": {"assignees": [TARGET_USER]},
        "org_edit_project": {"title": f"t{rid}-orgproject-updated", "description": "updated org project"},
        "org_edit_project_column": {"title": f"t{rid}-orgcolumn-updated"},
        "org_move_project_columns": {"column_ids": [state.get("org_column2_id", 0), state.get("org_column_id", 0)]},
        "org_move_project_issue": {"column_id": state.get("org_column2_id", 0), "issue_id": state.get("org_issue_id", 0)},
        "org_set_default_project_column": {"column_id": state.get("org_column2_id", 0)},
        "org_remove_issue_from_project_column": {"column_id": state.get("org_column2_id", 0), "issue_id": state.get("org_issue_id", 0)},
        "user_current_edit_project": {"title": f"t{rid}-userproject-updated", "description": "updated user project"},
        "user_current_edit_project_column": {"title": f"t{rid}-usercolumn-updated"},
        "user_current_move_project_columns": {"column_ids": [state.get("user_column2_id", 0), state.get("user_column_id", 0)]},
        "user_current_move_project_issue": {"column_id": state.get("user_column2_id", 0)},
        "user_current_set_default_project_column": {"column_id": state.get("user_column2_id", 0)},
        "user_current_remove_issue_from_project_column": {"column_id": state.get("user_column2_id", 0), "issue_id": state.get("issue_id", 0)},
        "repo_create_branch": {"new_branch_name": f"t{rid}-extra"},
        "repo_create_tag": {"tag_name": f"v{rid}-extra"},
        "repo_create_release": {
            "tag_name": f"v{rid}-extra",
            "name": f"t{rid}-extra-release",
            "body": "release",
        },
        "repo_create_wiki_page": {
            "title": f"t{rid}-wiki2",
            "content": "wiki2\n",
        },
        "repo_create_file": {
            "filepath": f"t{rid}-extra.txt",
            "content": "extra\n",
            "message": "extra file",
            "branch": state.get("file_branch", ""),
        },
        "repo_change_files": {
            "operation": "create",
            "path": f"t{rid}-bulk.txt",
            "content": "bulk\n",
            "message": "bulk",
            "branch": state.get("file_branch", ""),
        },
        "repo_apply_diff_patch": {
            "branch": state.get("file_branch", ""),
            "patch": f"diff --git a/diff-{rid}.txt b/diff-{rid}.txt\n--- a/diff-{rid}.txt\n+++ b/diff-{rid}.txt\n@@ -1 +1 @@\n-old\n+new\n",
        },
        "repo_update_topics": {"topics": [f"t{rid}topic"]},
        "repo_create_pull_review": {
            "index": state.get("pr_index"),
            "review_event": "COMMENT",
            "review_body": "review two",
        },
        "repo_submit_pull_review": {
            "index": state.get("pr_index"),
            "id": state.get("pending_review_id", 0),
            "review_event": "COMMENT",
            "review_body": "submitted",
        },
        "repo_create_pull_review_comment_reply": {
            "index": state.get("pr_index"),
            "id": state.get("review_comment_id"),
            "body": "reply",
        },
        "repo_resolve_pull_review_comment": {"id": state.get("review_comment_id")},
        "repo_unresolve_pull_review_comment": {"id": state.get("review_comment_id")},
        "repo_dismiss_pull_review": {
            "index": state.get("pr_index"),
            "id": state.get("approved_review_id", 0),
            "dismiss_message": "dismiss",
        },
        "repo_un_dismiss_pull_review": {
            "index": state.get("pr_index"),
            "id": state.get("approved_review_id", 0),
        },
        "repo_create_pull_review_requests": {
            "index": state.get("pr_index"),
            "reviewers": [TARGET_USER],
        },
        "repo_delete_pull_review_requests": {
            "index": state.get("pr_index"),
            "reviewers": [TARGET_USER],
        },
        "repo_create_status": {
            "sha": state.get("sha"),
            "state": "success",
            "status_context": "gitea-mcp-test",
        },
        "repo_create_branch_protection": {
            "branch_name": f"t{rid}-prot",
            "required_approvals": 0,
            "enable_push": True,
        },
        "repo_create_tag_protection": {"name_pattern": f"v{rid}-prot*"},
        "repo_create_key": {"public_key": SSH_PUB, "title": f"t{rid}-key2"},
        "repo_create_deploy_token": {"title": f"t{rid}-token2"},
        "issue_create_issue": {"title": f"t{rid}-issue3", "body": "third test issue"},
        "issue_create_label": {
            "name": f"t{rid}-label2",
            "color": "#33a02c",
            "description": "label2",
        },
        "org_create_label": {
            "name": f"t{rid}-orglabel2",
            "color": "#33a02c",
            "description": "org label2",
        },
        "issue_create_milestone": {
            "title": f"t{rid}-ms2",
            "description": "milestone2",
            "due_on": FUTURE,
        },
        "org_create": {
            "username": f"t{rid}org2",
            "description": "org two",
            "visibility": "public",
        },
        "org_create_team": {
            "name": f"t{rid}-team2",
            "permission": "write",
            "description": "team2",
        },
        "repo_create_project": {"title": f"t{rid}-project2", "description": "project2"},
        "org_create_project": {
            "title": f"t{rid}-orgproject2",
            "description": "org project2",
        },
        "user_current_create_project": {
            "title": f"t{rid}-userproject2",
            "description": "user project2",
        },
        "repo_migrate": {
            "clone_addr": f"http://localhost:3000/{state.get('owner', '')}/{state.get('src_repo', '')}.git",
            "repo_name": f"t{rid}-mirror2",
            "description": "mirror2",
            "mirror": True,
            "private": False,
            "repo_owner": state.get("owner"),
        },
        "generate_repo": {
            "template_owner": state.get("owner"),
            "template_repo": state.get("template_repo"),
            "owner": state.get("owner"),
            "name": f"t{rid}-gen2",
            "description": "generated2",
            "private": False,
        },
        "create_fork": {"organization": state.get("org")},
        "link_package": {
            "type": "generic",
            "name": state.get("pkg_name"),
            "repo_name": state.get("repo"),
        },
        "issue_delete_stop_watch": {"index": state.get("issue2_index", 0)},
        "issue_stop_stop_watch": {"index": state.get("issue_index", 0)},
        "issue_remove_issue_blocking": {
            "index": str(state.get("issue_index", 0)),
            "body_index": state.get("issue3_index", 0),
            "body_owner": state.get("owner", ""),
            "body_repo": state.get("repo", ""),
        },
        "issue_remove_issue_dependencies": {
            "index": str(state.get("issue_index", 0)),
            "body_index": state.get("issue2_index", 0),
            "body_owner": state.get("owner", ""),
            "body_repo": state.get("repo", ""),
        },
        "unlink_package": {"type": "generic", "name": state.get("pkg_name")},
        "notify_read_list": {"all": "true", "to_status": "read"},
        "notify_read_thread": {"to_status": "read"},
        "user_current_put_follow": {"username": TARGET_USER},
        "user_current_delete_follow": {"username": TARGET_USER},
        "user_current_check_following": {"username": TARGET_USER},
        "issue_add_subscription": {"user": TARGET_USER},
        "issue_delete_subscription": {"user": state.get("owner", "")},
        "repo_create_pull_request": {
            "head": state.get("branch"),
            "base": state.get("base"),
            "title": f"t{rid}-pr2",
            "body": "second pr",
            "reviewers": [TARGET_USER],
        },
    }
    # tool-name-specific path id overrides
    if (
        tool.startswith("repo_")
        and "project_column" in tool
        and tool not in ("repo_create_project_column",)
    ):
        overrides.setdefault(tool, {})["id"] = state.get("project_id", 0)
    if (
        tool.startswith("org_")
        and "project_column" in tool
        and tool != "org_create_project_column"
    ):
        overrides.setdefault(tool, {})["id"] = state.get("org_project_id", 0)
    if (
        tool.startswith("user_current_")
        and "project_column" in tool
        and tool != "user_current_create_project_column"
    ):
        overrides.setdefault(tool, {})["id"] = state.get("user_project_id", 0)
    if "project_workflow" in tool and "create_project_workflow" not in tool:
        if tool.startswith("org_"):
            overrides.setdefault(tool, {})["id"] = state.get("org_project_id", 0)
            overrides.setdefault(tool, {})["workflow_id"] = state.get(
                "org_workflow_id", 0
            )
        elif tool.startswith("user_current_"):
            overrides.setdefault(tool, {})["id"] = state.get("user_project_id", 0)
            overrides.setdefault(tool, {})["workflow_id"] = state.get(
                "user_workflow_id", 0
            )
        else:
            overrides.setdefault(tool, {})["id"] = state.get("project_id", 0)
            overrides.setdefault(tool, {})["workflow_id"] = state.get("workflow_id", 0)
    if tool.startswith("org_") and "project" in tool:
        if "id" in path_params:
            args["id"] = state.get("org_project_id", 0)
        if "column_id" in path_params:
            args["column_id"] = state.get("org_column_id", 0)
        if "workflow_id" in path_params:
            args["workflow_id"] = state.get("org_workflow_id", 0)
    if tool.startswith("user_current_") and "project" in tool:
        if "id" in path_params:
            args["id"] = state.get("user_project_id", 0)
        if "column_id" in path_params:
            args["column_id"] = state.get("user_column_id", 0)
        if "workflow_id" in path_params:
            args["workflow_id"] = state.get("user_workflow_id", 0)
    if tool in overrides:
        args.update({k: v for k, v in overrides[tool].items() if v is not None})
    return args


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    print(f"# Test Report — Gitea MCP Server")
    print(f"\n**Date**: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    print(f"**Server**: {MCP_URL}")
    print(f"**Run ID**: {rid}\n")

    async with MCPSession(MCP_URL, MCP_HEADERS) as session:
        tools_list = await session.list_tools()
        tool_names = [t["name"] for t in tools_list]
        results.append(
            {
                "label": "T000 tool_discovery",
                "tool": "tools/list",
                "status": "PASSED",
                "data": {"count": len(tool_names), "tools": sorted(tool_names)},
            }
        )
        log(f"Discovered {len(tool_names)} tools")

        await setup(session)

        # All remaining GET tools
        log("\n=== Remaining GET tools ===")
        for tool in sorted(tool_names):
            if tool in called or tool not in TOOL_SPECS:
                continue
            spec = TOOL_SPECS[tool]
            if spec["method"] != "GET":
                continue
            if tool in ("repo_pull_request_is_merged", "repo_get_commit_pull_request"):
                continue
            data = await run(session, f"GET {tool}", tool, build_args(tool, spec))
            if data is not None:
                capture(tool, build_args(tool, spec), data)

        # All remaining mutations
        log("\n=== Remaining mutation tools ===")
        mutations = [
            t
            for t in tool_names
            if t in TOOL_SPECS
            and t not in called
            and t not in ("repo_merge_pull_request", "rename_org")
            and TOOL_SPECS[t]["method"] in ("POST", "PUT", "PATCH")
        ]

        def mut_key(t):
            if t == "repo_merge_pull_request":
                return (2, t)
            if t == "repo_cancel_scheduled_auto_merge":
                return (1, t)
            return (0, t)

        mutations.sort(key=mut_key)
        for tool in mutations:
            spec = TOOL_SPECS[tool]
            data = await run(session, f"MUT {tool}", tool, build_args(tool, spec))
            if data is not None:
                capture(tool, build_args(tool, spec), data)

        # Start a stopwatch on issue 2 so delete_stop_watch has a live fixture
        await run(
            session, "PRE start_stopwatch_issue2", "issue_start_stop_watch",
            {
                "owner": state.get("owner", ""),
                "repo": state.get("repo", ""),
                "index": state.get("issue2_index", 0),
            },
        )

        # Deletes (repo_delete last)
        log("\n=== Delete tools ===")
        deletes = [
            t
            for t in tool_names
            if t in TOOL_SPECS
            and t not in called
            and t != "repo_delete"
            and t not in ("org_delete_team", "org_delete_repos", "org_delete")
            and TOOL_SPECS[t]["method"] == "DELETE"
        ]

        def del_key(t):
            if t == "repo_delete_team":
                return (0, t)
            if t == "issue_delete":
                return (9, t)
            if t in (
                "issue_remove_label", "issue_delete_comment_reaction",
                "issue_delete_issue_reaction", "issue_delete_stop_watch",
                "issue_delete_subscription", "issue_delete_time",
                "repo_remove_issue_from_project_column", "repo_delete_project_column",
                "org_remove_issue_from_project_column", "org_delete_project_column",
                "user_current_remove_issue_from_project_column",
                "user_current_delete_project_column", "delete_package_version",
            ):
                return (0, t)
            if t in ("repo_delete_project", "org_delete_project", "user_current_delete_project", "delete_package"):
                return (2, t)
            if t in (
                "issue_clear_labels", "issue_reset_time",
                "issue_remove_issue_blocking", "issue_remove_issue_dependencies",
                "unpin_issue", "issue_unlock_issue", "issue_delete_milestone",
            ):
                return (1, t)
            if t == "issue_delete_label":
                return (2, t)
            if t in ("issue_delete_comment", "issue_delete_comment_deprecated"):
                return (3, t)
            return (1, t)

        deletes.sort(key=del_key)
        for tool in deletes:
            spec = TOOL_SPECS[tool]
            data = await run(session, f"DEL {tool}", tool, build_args(tool, spec))
            if data is not None:
                capture(tool, build_args(tool, spec), data)

        # Final actions: org cleanup, success status, merge, merged-PR checks, then repo delete
        await run(
            session, "FINAL delete_team2", "org_delete_team",
            {"id": state.get("team2_id", 0)},
        )
        await run(
            session, "FINAL delete_team1", "org_delete_team",
            {"id": state.get("team_id", 0)},
        )
        await run(
            session, "FINAL delete_team3", "org_delete_team",
            {"id": state.get("team3_id", 0)},
        )
        await run(
            session, "FINAL delete_org_repos", "org_delete_repos",
            {"org": state.get("org", "")},
        )
        for _ in range(15):
            remaining = await run(
                session, "FINAL wait_org_repos", "org_list_repos",
                {"org": state.get("org", "")},
            )
            if not list_items(remaining):
                break
            await asyncio.sleep(1)
        data = await run(
            session, "FINAL rename_org", "rename_org",
            {"org": state.get("org", ""), "new_name": f"t{rid}-new_name"},
        )
        if isinstance(data, dict):
            state["org"] = data.get("username") or data.get("name") or f"t{rid}-new_name"
        await run(
            session, "FINAL delete_org", "org_delete",
            {"org": state.get("org", "")},
        )
        if "repo_cancel_scheduled_auto_merge" not in called:
            await run(
                session, "FINAL cancel_auto_merge", "repo_cancel_scheduled_auto_merge",
                build_args("repo_cancel_scheduled_auto_merge", TOOL_SPECS["repo_cancel_scheduled_auto_merge"]),
            )
        await run(
            session, "FINAL status_success", "repo_create_status",
            {
                "owner": state.get("owner", ""),
                "repo": state.get("repo", ""),
                "sha": state.get("pr_head_sha") or state.get("sha") or "",
                "state": "success",
                "status_context": "gitea-mcp-check",
                "status_description": "success status",
            },
        )
        await asyncio.sleep(3)
        await run(
            session, "FINAL merge_pull_request", "repo_merge_pull_request",
            {
                "owner": state.get("owner", ""),
                "repo": state.get("repo", ""),
                "index": state.get("pr_index", 0),
                "do": "merge",
            },
        )
        data = await run(
            session, "FINAL get_merged_pr", "repo_get_pull_request",
            {
                "owner": state.get("owner", ""),
                "repo": state.get("repo", ""),
                "index": state.get("pr_index", 0),
                "include_all_fields": True,
            },
        )
        if isinstance(data, dict):
            state["merge_sha"] = data.get("merge_commit_sha")
        await run(
            session, "FINAL is_merged", "repo_pull_request_is_merged",
            {
                "owner": state.get("owner", ""),
                "repo": state.get("repo", ""),
                "index": state.get("pr_index", 0),
            },
        )
        if state.get("merge_sha"):
            await run(
                session, "FINAL commit_pull", "repo_get_commit_pull_request",
                {
                    "owner": state.get("owner", ""),
                    "repo": state.get("repo", ""),
                    "sha": state.get("merge_sha"),
                },
            )
        await run(session, "FINAL delete_repo", "repo_delete", build_args("repo_delete", TOOL_SPECS["repo_delete"]))

        # Cleanup extra repositories created for migration/template tests
        for repo_name in (
            state.get("src_repo", ""),
            state.get("mirror_repo", ""),
            state.get("template_repo", ""),
            state.get("gen_repo", ""),
        ):
            if repo_name:
                await run(
                    session, f"CLEANUP delete_{repo_name}", "repo_delete",
                    {"owner": state.get("owner", ""), "repo": repo_name},
                )

        # Leak detection
        repos_data = await run(
            session, "CLEANUP list_repos", "user_current_list_repos", {"limit": 50}
        )
        repo_leaks = [
            r.get("name", "") for r in list_items(repos_data)
            if str(r.get("name", "")).startswith(f"t{rid}")
        ]
        packages_data = await run(
            session, "CLEANUP list_packages", "list_packages",
            {"owner": state.get("owner", "")},
        )
        pkg_leaks = [
            p.get("name", "") for p in list_items(packages_data)
            if str(p.get("name", "")).startswith(f"t{rid}")
        ]
        org_leaks = []
        org_repo_leaks = []
        orgs_data = await run(session, "CLEANUP list_orgs", "org_get_all", {"limit": 50})
        for o in list_items(orgs_data):
            oname = o.get("username") or o.get("name")
            if oname and str(oname).startswith(f"t{rid}"):
                org_leaks.append(oname)
                odata = await run(
                    session, f"CLEANUP list_org_repos_{oname}", "org_list_repos",
                    {"org": oname},
                )
                org_repo_leaks.extend(
                    r.get("name") for r in list_items(odata)
                    if str(r.get("name", "")).startswith(f"t{rid}")
                )
        if repo_leaks or pkg_leaks or org_leaks or org_repo_leaks:
            results.append({
                "label": "CLEANUP leak_detection", "tool": "leak_detection",
                "status": "FAILED",
                "reason": f"Leaked repos={repo_leaks} packages={pkg_leaks} orgs={org_leaks} org_repos={org_repo_leaks}",
            })
        else:
            results.append({
                "label": "CLEANUP leak_detection", "tool": "leak_detection",
                "status": "PASSED", "data": {"leaks": []},
            })

        # Coverage guard
        missing = sorted(set(tool_names) - called)
        if missing:
            results.append(
                {
                    "label": "COVERAGE guard",
                    "tool": "coverage",
                    "status": "FAILED",
                    "reason": f"{len(missing)} tools not tested: {', '.join(missing[:40])}",
                }
            )
            log(f"COVERAGE MISSING: {missing}")
        else:
            results.append(
                {
                    "label": "COVERAGE guard",
                    "tool": "coverage",
                    "status": "PASSED",
                    "data": {"tools_tested": len(called)},
                }
            )
            log("COVERAGE OK")

        passed = sum(1 for r in results if r["status"] == "PASSED")
        failed = sum(1 for r in results if r["status"] == "FAILED")
        print(f"\n## Summary\n")
        print("| Status | Count |")
        print("|--------|-------|")
        print(f"| PASSED | {passed} |")
        print(f"| FAILED | {failed} |")
        if failed:
            print(f"\n## FAILED ({failed})\n")
            for r in results:
                if r["status"] == "FAILED":
                    print(f"### {r['label']}")
                    print(f"- **Tool**: `{r['tool']}`")
                    print(f"- **Error**: {r['reason']}\n")
        print(
            f"\n---\n**Total tests:** {len(results)} | **PASSED:** {passed} | **FAILED:** {failed}"
        )
        print("\n**ALL TESTS PASS**" if failed == 0 else "\n**TESTS FAILING**")


if __name__ == "__main__":
    asyncio.run(main())
