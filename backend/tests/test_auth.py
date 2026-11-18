"""线上演示的访问保护：密码登录、SSE 也受保护、防暴力尝试、每日用量封顶。"""

import pytest

from tests.conftest import TOPIC, api, create_discussion

pytestmark = pytest.mark.anyio


async def test_without_app_password_everything_is_open(make_app):
    app, _ = make_app()
    async with api(app) as client:
        assert (await client.get("/api/discussions")).status_code == 200
        assert (await client.get("/api/auth/status")).json() == {"required": False, "authenticated": True}


async def test_with_app_password_api_and_sse_require_login(make_app):
    app, _ = make_app(app_password="s3cret-demo")
    async with api(app) as client:
        assert (await client.get("/api/health")).status_code == 200  # 健康检查不拦
        r = await client.get("/api/discussions")
        assert r.status_code == 401 and r.json()["code"] == "UNAUTHORIZED"
        assert (await client.get("/api/discussions/anything/stream")).status_code == 401
        assert (await client.post("/api/discussions", json={"topic": TOPIC})).status_code == 401

        assert (await client.post("/api/auth/login", json={"password": "wrong"})).status_code == 401
        r = await client.post("/api/auth/login", json={"password": "s3cret-demo"})
        assert r.status_code == 200
        assert "httponly" in r.headers["set-cookie"].lower()

        assert (await client.get("/api/auth/status")).json() == {"required": True, "authenticated": True}
        assert (await client.get("/api/discussions")).status_code == 200


async def test_forged_cookie_is_rejected(make_app):
    app, _ = make_app(app_password="s3cret-demo")
    async with api(app) as client:
        client.cookies.set("aps_session", "9999999999.deadbeef")
        assert (await client.get("/api/discussions")).status_code == 401


async def test_repeated_wrong_passwords_are_locked_out(make_app):
    app, _ = make_app(app_password="s3cret-demo")
    async with api(app) as client:
        codes = [(await client.post("/api/auth/login", json={"password": f"guess{i}"})).status_code for i in range(6)]
        assert codes == [401] * 5 + [429]
        # 锁定期间即使密码正确也拒绝
        r = await client.post("/api/auth/login", json={"password": "s3cret-demo"})
        assert r.status_code == 429 and r.json()["code"] == "TOO_MANY_ATTEMPTS"


async def test_daily_start_cap_protects_the_api_budget(make_app):
    app, _ = make_app(max_starts_per_day=1, max_expert_turns=1)
    async with api(app) as client:
        first = (await create_discussion(client))["id"]
        second = (await create_discussion(client))["id"]
        assert (await client.post(f"/api/discussions/{first}/start")).status_code == 202
        await app.state.runner.wait(first)
        r = await client.post(f"/api/discussions/{second}/start")
        assert r.status_code == 429 and r.json()["code"] == "DAILY_LIMIT_REACHED"


async def test_daily_create_cap_stops_new_discussions(make_app):
    app, fake = make_app(max_creates_per_day=1)
    async with api(app) as client:
        await create_discussion(client)
        r = await client.post("/api/discussions", json={"topic": TOPIC})
        assert r.status_code == 429 and r.json()["code"] == "DAILY_LIMIT_REACHED"
    assert fake.calls_for("lineup") == 1  # 超限时不调用模型
