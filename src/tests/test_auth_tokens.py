from fastapi.testclient import TestClient

from src.main import app


def test_dev_login_refresh_revoke_flow():
    client = TestClient(app)

    # Login
    r = client.post("/api/auth/login", json={"email": "tester@example.com"})
    assert r.status_code == 200
    payload = r.json().get("data")
    assert payload and payload.get("access_token") and payload.get("refresh_token")
    access = payload["access_token"]
    refresh = payload["refresh_token"]

    # Access an endpoint using token
    headers = {"Authorization": f"Bearer {access}"}
    r2 = client.get("/api/session/list", headers=headers)
    assert r2.status_code == 200

    # Refresh token
    r3 = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert r3.status_code == 200
    data3 = r3.json().get("data")
    assert data3 and data3.get("access_token") and data3.get("refresh_token")
    new_access = data3["access_token"]

    # Revoke refreshed access token
    r4 = client.post("/api/auth/revoke", json={"token": new_access})
    assert r4.status_code == 200

    # Using revoked token yields 401
    r5 = client.get("/api/session/list", headers={"Authorization": f"Bearer {new_access}"})
    assert r5.status_code == 401
