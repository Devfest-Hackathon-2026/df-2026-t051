import os
from functools import lru_cache
from threading import Lock

import firebase_admin
from fastapi import Header, HTTPException, Request
from firebase_admin import auth
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

_firebase_lock=Lock()


@lru_cache
def firebase_app():
    project = os.environ.get("FIREBASE_PROJECT_ID")
    if not project:
        raise RuntimeError("Firebase project is not configured")
    with _firebase_lock:
        try:
            app=firebase_admin.get_app('chartbridge')
        except ValueError:
            app=firebase_admin.initialize_app(options={"projectId":project},name='chartbridge')
        if app.project_id!=project:
            raise RuntimeError('Firebase project mismatch')
        return app


def teacher(request: Request, authorization: str | None = Header(default=None)) -> str:
    if request.app.state.demo:
        if request.client and request.client.host in {"127.0.0.1", "::1", "testclient"}:
            return "local-demo"
        raise HTTPException(403, "デモモードはローカル接続専用です。")
    if os.environ.get("AUTH_MODE", "firebase") == "google_iam":
        # Cloud Run remains IAM-private. Independently verify a full ID token,
        # since Cloud Run can strip the signature from its Authorization header.
        token = request.headers.get("X-ChartBridge-Identity")
        if not token:
            raise HTTPException(401, "IAM認証付き検証プロキシからアクセスしてください。")
        audience = os.environ.get("IAM_TOKEN_AUDIENCE")
        allowed = {email.strip() for email in os.environ.get("IAM_TEACHER_EMAILS", "").split(",") if email.strip()}
        if not audience or not allowed:
            raise HTTPException(503, "IAM検証環境が設定されていません。")
        try:
            claims = id_token.verify_oauth2_token(token, GoogleRequest(), audience=audience)
        except Exception:
            raise HTTPException(401, "IAM認証の有効期限を確認してください。") from None
        if claims.get("email_verified") is not True or claims.get("email") not in allowed:
            raise HTTPException(403, "この検証環境の教員権限が必要です。")
        return claims["sub"]
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "教員としてログインしてください。")
    try:
        app = firebase_app()
    except RuntimeError:
        raise HTTPException(503, "教員認証が設定されていません。") from None
    try:
        claims = auth.verify_id_token(authorization[7:], app=app, check_revoked=True)
    except Exception:
        raise HTTPException(401, "ログインの有効期限を確認してください。") from None
    if claims.get("teacher") is not True:
        raise HTTPException(403, "教員権限が必要です。")
    return claims["uid"]
