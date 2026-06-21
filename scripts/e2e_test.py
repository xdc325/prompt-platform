"""End-to-end test script for Prompt Platform.

Tests all major flows: register, login, projects, prompts, versions
(create, submit, publish, diff, delete), playground.

Usage: python scripts/e2e_test.py
"""

import json
import sys
import time
import urllib.request
import urllib.error

BASE = "http://localhost:8000/api/v1"
PASS = 0
FAIL = 0
TOKEN = None
USER_ID = None


def request(method, path, body=None):
    """Make an HTTP request to the API."""
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"success": False, "error": body}


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")


def test_register_and_login():
    """Test user registration and login."""
    global TOKEN, USER_ID
    print("\n=== 1. Auth ===")

    ts = int(time.time())
    email = f"e2e-{ts}@test.com"
    password = "testpassword123"
    display_name = "E2E Tester"

    # Register
    resp = request("POST", "/auth/register", {
        "email": email,
        "password": password,
        "display_name": display_name,
    })
    check("注册成功", resp.get("success"), resp.get("error", ""))
    if resp.get("success"):
        TOKEN = resp["data"]["access_token"]
        USER_ID = resp["data"]["user"]["id"]
        check("注册返回 token", bool(TOKEN))
        check("注册返回用户信息", resp["data"]["user"]["email"] == email)
    else:
        print(f"    [ERROR] 注册失败: {resp}")
        return False

    # Me
    resp = request("GET", "/auth/me")
    check("获取个人信息成功", resp.get("success"))
    check("个人信息邮箱正确", resp.get("data", {}).get("email") == email)

    # Login
    TOKEN = None
    resp = request("POST", "/auth/login", {"email": email, "password": password})
    check("登录成功", resp.get("success"))
    if resp.get("success"):
        TOKEN = resp["data"]["access_token"]
        check("登录返回 token", bool(TOKEN))

    # Register duplicate
    resp2 = request("POST", "/auth/register", {
        "email": email, "password": "newpass123",
        "display_name": "Another",
    })
    check("重复注册被拒绝", not resp2.get("success"))

    return True


def test_projects():
    """Test project CRUD."""
    global PROJECT_ID
    print("\n=== 2. Projects ===")

    # Create project
    resp = request("POST", "/projects", {
        "name": "E2E 测试项目",
        "description": "自动化测试用项目",
    })
    check("创建项目成功", resp.get("success"), resp.get("error", ""))
    if resp.get("success"):
        PROJECT_ID = resp["data"]["id"]
        check("项目名称正确", resp["data"]["name"] == "E2E 测试项目")
    else:
        print(f"    [ERROR] 创建项目失败: {resp}")
        return False

    # List projects
    resp = request("GET", "/projects")
    check("项目列表成功", resp.get("success"))
    items = resp.get("data", {}).get("items", [])
    check("项目列表包含新项目", any(p["id"] == PROJECT_ID for p in items))

    # Get single project
    resp = request("GET", f"/projects/{PROJECT_ID}")
    check("获取单个项目成功", resp.get("success"))
    check("项目描述正确", resp.get("data", {}).get("description") == "自动化测试用项目")

    return True


def test_prompts():
    """Test prompt CRUD."""
    global PROMPT_ID
    print("\n=== 3. Prompts ===")

    # Create prompt
    resp = request("POST", f"/projects/{PROJECT_ID}/prompts", {
        "name": "E2E 测试提示词",
        "description": "用于测试的提示词",
    })
    check("创建提示词成功", resp.get("success"), resp.get("error", ""))
    if resp.get("success"):
        PROMPT_ID = resp["data"]["id"]
    else:
        print(f"    [ERROR] 创建提示词失败: {resp}")
        return False

    # List prompts
    resp = request("GET", f"/projects/{PROJECT_ID}/prompts")
    check("提示词列表成功", resp.get("success"))
    items = resp.get("data", {}).get("items", [])
    check("提示词列表包含新提示词", any(p["id"] == PROMPT_ID for p in items))

    # Get single prompt
    resp = request("GET", f"/prompts/{PROMPT_ID}")
    check("获取提示词成功", resp.get("success"))
    check("提示词当前版本为空", resp.get("data", {}).get("current_version_id") is None)

    return True


def test_versions():
    """Test version lifecycle: create → submit → publish → diff → delete."""
    global VERSION_ID, VERSION_ID2
    print("\n=== 4. Version Lifecycle ===")

    # Create draft v1
    resp = request("POST", f"/prompts/{PROMPT_ID}/versions", {
        "content": "你是一个{{role}}助手，请用{{language}}回答用户的问题。\n用户问题：{{question}}",
        "variables": [],
        "changelog": "初始版本",
    })
    check("创建草稿 v1 成功", resp.get("success"), resp.get("error", ""))
    if resp.get("success"):
        VERSION_ID = resp["data"]["id"]
        check("v1 状态为 draft", resp["data"]["status"] == "draft")
        check("v1 版本号正确", resp["data"]["version_number"] == 1)
    else:
        print(f"    [ERROR] 创建草稿失败: {resp}")
        return False

    # Submit for review
    resp = request("POST", f"/prompts/{PROMPT_ID}/versions/{VERSION_ID}/submit")
    check("提交审核成功", resp.get("success"), resp.get("error", ""))
    check("状态变为 pending_review", resp.get("data", {}).get("status") == "pending_review")

    # Publish v1
    resp = request("POST", f"/prompts/{PROMPT_ID}/versions/{VERSION_ID}/publish")
    check("发布 v1 成功", resp.get("success"), resp.get("error", ""))
    check("v1 状态变为 published", resp.get("data", {}).get("status") == "published")

    # Verify prompt.current_version_id updated
    resp = request("GET", f"/prompts/{PROMPT_ID}")
    prompt_data = resp.get("data", {})
    check("提示词当前版本更新为 v1", prompt_data.get("current_version_id") == VERSION_ID,
          f"expected {VERSION_ID}, got {prompt_data.get('current_version_id')}")

    # Create draft v2
    resp = request("POST", f"/prompts/{PROMPT_ID}/versions", {
        "content": "你是一个{{role}}专家，请用{{language}}以{{tone}}的语气回答。\n用户问题：{{question}}",
        "variables": [],
        "changelog": "新增语气变量",
    })
    check("创建草稿 v2 成功", resp.get("success"), resp.get("error", ""))
    if resp.get("success"):
        VERSION_ID2 = resp["data"]["id"]
        check("v2 版本号正确", resp["data"]["version_number"] == 2)

    # Submit & publish v2
    resp = request("POST", f"/prompts/{PROMPT_ID}/versions/{VERSION_ID2}/submit")
    check("提交 v2 审核成功", resp.get("success"), resp.get("error", ""))
    resp = request("POST", f"/prompts/{PROMPT_ID}/versions/{VERSION_ID2}/publish")
    check("发布 v2 成功", resp.get("success"), resp.get("error", ""))

    # Verify v1 is auto-archived
    resp = request("GET", f"/prompts/{PROMPT_ID}/versions")
    versions = resp.get("data", {}).get("items", [])
    v1_after = next((v for v in versions if v["id"] == VERSION_ID), None)
    check("v1 自动归档", v1_after and v1_after["status"] == "archived",
          f"status={v1_after['status'] if v1_after else 'not found'}")

    # Prompt current_version_id now points to v2
    resp = request("GET", f"/prompts/{PROMPT_ID}")
    check("提示词当前版本更新为 v2", resp.get("data", {}).get("current_version_id") == VERSION_ID2)

    return True


def test_diff():
    """Test version diff."""
    print("\n=== 5. Diff ===")
    resp = request("GET", f"/prompts/{PROMPT_ID}/versions/{VERSION_ID}/diff/{VERSION_ID2}")
    check("Diff 成功", resp.get("success"), resp.get("error", ""))
    changes = resp.get("data", {}).get("changes", [])
    check("Diff 有变更结果", len(changes) > 0)
    has_replaced = any(c["type"] == "replaced" for c in changes)
    check("Diff 检测到修改", has_replaced)


def test_rollback():
    """Test rollback to previous version."""
    print("\n=== 6. Rollback ===")

    resp = request("POST", f"/prompts/{PROMPT_ID}/rollback?version_id={VERSION_ID}")
    check("回滚到 v1 成功", resp.get("success"), resp.get("error", ""))

    resp = request("GET", f"/prompts/{PROMPT_ID}")
    check("回滚后当前版本为 v1",
          resp.get("data", {}).get("current_version_id") == VERSION_ID)

    # Roll back to v2
    resp = request("POST", f"/prompts/{PROMPT_ID}/rollback?version_id={VERSION_ID2}")
    check("再次回滚到 v2 成功", resp.get("success"), resp.get("error", ""))


def test_playground():
    """Test playground."""
    print("\n=== 7. Playground ===")
    resp = request("POST", f"/prompts/{PROMPT_ID}/playground", {
        "version_id": VERSION_ID2,
        "input": "How do I write unit tests?",
        "model": "gpt-3.5-turbo",
    })
    # Playground may fail if OPENAI_API_KEY is not set — that's OK
    if resp.get("success"):
        check("Playground 运行成功", True)
        check("Playground 有输出", bool(resp.get("data", {}).get("output")))
    else:
        print(f"  ~ Playground skipped (likely no API key): {resp.get('error', '')[:80]}")


def test_delete_version():
    """Test version deletion, including FK constraint scenarios."""
    print("\n=== 8. Delete Version ===")

    # Create a draft v3 (not published, safe to delete)
    resp = request("POST", f"/prompts/{PROMPT_ID}/versions", {
        "content": "这是要删除的测试版本",
        "variables": [],
        "changelog": "将被删除",
    })
    check("创建草稿 v3（待删除）成功", resp.get("success"), resp.get("error", ""))
    v3_id = resp.get("data", {}).get("id") if resp.get("success") else None

    if v3_id:
        # Delete draft v3
        resp = request("DELETE", f"/prompts/{PROMPT_ID}/versions/{v3_id}")
        check("删除草稿 v3 成功", resp.get("success"), resp.get("error", ""))

        # Verify deleted
        resp = request("GET", f"/prompts/{PROMPT_ID}/versions")
        versions = resp.get("data", {}).get("items", [])
        v3_ids = [v["id"] for v in versions]
        check("v3 已不再版本列表中", v3_id not in v3_ids)

    # Delete current version (v2) — should work now that we clear FK refs
    resp = request("DELETE", f"/prompts/{PROMPT_ID}/versions/{VERSION_ID2}")
    check("删除当前版本 v2 成功（FK 已清理）", resp.get("success"), resp.get("error", ""))

    # Verify prompt.current_version_id is cleared
    resp = request("GET", f"/prompts/{PROMPT_ID}")
    check("v2 删除后提示词当前版本清空",
          resp.get("data", {}).get("current_version_id") is None,
          f"got {resp.get('data', {}).get('current_version_id')}")


def test_errors():
    """Test error handling."""
    print("\n=== 9. Error Handling ===")

    # Access non-existent prompt
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = request("GET", f"/prompts/{fake_id}")
    check("不存在的提示词返回错误", not resp.get("success"))

    # Invalid state transition (publish a draft directly)
    resp = request("POST", f"/prompts/{PROMPT_ID}/versions", {
        "content": "测试非法转换",
        "variables": [],
        "changelog": "",
    })
    draft_id = resp.get("data", {}).get("id") if resp.get("success") else None
    if draft_id:
        resp2 = request("POST", f"/prompts/{PROMPT_ID}/versions/{draft_id}/publish")
        check("draft 直接发布被拒绝", not resp2.get("success"))
        # Clean up
        request("DELETE", f"/prompts/{PROMPT_ID}/versions/{draft_id}")

    # Unauthenticated access
    global TOKEN
    old_token = TOKEN
    TOKEN = None
    resp = request("GET", "/projects")
    check("未登录访问被拒绝", not resp.get("success"))
    TOKEN = old_token


def main():
    print("=" * 60)
    print("Prompt Platform — E2E Test Suite")
    print("=" * 60)

    if not test_register_and_login():
        print("\n    AUTH FAILED — stopping")
        sys.exit(1)
    if not test_projects():
        print("\n    PROJECTS FAILED — stopping")
        sys.exit(1)
    if not test_prompts():
        print("\n    PROMPTS FAILED — stopping")
        sys.exit(1)
    if not test_versions():
        print("\n    VERSIONS FAILED — stopping")
        sys.exit(1)

    test_diff()
    test_rollback()
    test_playground()
    test_delete_version()
    test_errors()

    print("\n" + "=" * 60)
    print(f"Results: {PASS} passed, {FAIL} failed")
    print("=" * 60)

    if FAIL > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
