import asyncio
import io
import os
import warnings
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile,Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import ValidationError
from google.api_core.exceptions import GoogleAPICallError

from .auth import teacher
from .extraction import extract_chart
from .models import Draft, Extraction
from .materials import router as materials_router, public_router
from .materials import firestore_repository
from .images import router as images_router, save_image
from .safety import normalize_extraction
from .limits import RequestWindow,SnapshotCache,reserve_usage,setting

MAX_FILE = 5 * 1024 * 1024
MAX_BODY = MAX_FILE + 64 * 1024
Image.MAX_IMAGE_PIXELS = 12_000_000


class BodyLimit:
    """Count actual streamed bytes before multipart parsing, including chunked requests."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > MAX_BODY:
                raise HTTPException(413, "画像は5 MiB以下にしてください。")
            return message

        await self.app(scope, limited_receive, send)


def normalize_image(data: bytes, mime: str) -> bytes:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                expected = {"image/png": "PNG", "image/jpeg": "JPEG"}.get(mime)
                if not expected or image.format != expected or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("Invalid format")
                if image.width * image.height > 12_000_000 or min(image.size) < 32:
                    raise ValueError("Invalid dimensions")
                image.load()
                oriented = ImageOps.exif_transpose(image)
                if 'A' in oriented.getbands() or 'transparency' in oriented.info:
                    rgba=oriented.convert('RGBA')
                    clean=Image.alpha_composite(Image.new('RGBA',rgba.size,'white'),rgba).convert('RGB')
                else:
                    clean = oriented.convert("RGB")
                output = io.BytesIO()
                clean.save(output, format="PNG")  # Remove metadata before sending to Gemini.
                if output.tell() > 10 * 1024 * 1024:
                    raise ValueError("Normalized image too large")
                return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, "有効なPNG/JPEG画像を選択してください（32px以上、1200万画素以下・静止画）。") from None


def create_app(demo: bool | None = None) -> FastAPI:
    demo = os.environ.get("LOCAL_DEMO") == "true" if demo is None else demo

    @asynccontextmanager
    async def lifespan(app):
        if demo and (os.environ.get("K_SERVICE") or os.environ.get("APP_ENV") != "local"):
            raise RuntimeError("LOCAL_DEMO requires APP_ENV=local and is forbidden on Cloud Run")
        if os.environ.get("AUTH_MODE", "firebase") not in {"firebase", "google_iam"}:
            raise RuntimeError("Unknown AUTH_MODE")
        if os.environ.get('K_SERVICE') and os.environ.get('APP_ENV')!='production':
            raise RuntimeError('Cloud Run requires production settings')
        if os.environ.get('PUBLIC_ACCESS')=='true' and os.environ.get('AUTH_MODE')!='firebase':
            raise RuntimeError('Public service requires Firebase authentication')
        for name,default,maximum in [('ANALYSIS_PER_MINUTE',2,20),('ANALYSIS_PER_TEACHER_DAY',10,100),('ANALYSIS_GLOBAL_DAY',30,300),('WRITE_PER_MINUTE',30,120),('WRITE_PER_TEACHER_DAY',200,1000)]:setting(name,default,maximum)
        yield

    production=os.environ.get('APP_ENV')=='production' or bool(os.environ.get('K_SERVICE'))
    app = FastAPI(title="ChartBridge", lifespan=lifespan,openapi_url=None if production else '/openapi.json',docs_url=None if production else '/docs',redoc_url=None if production else '/redoc')
    app.state.demo = demo
    app.state.extractor = extract_chart
    app.state.public_reads=RequestWindow(setting('PUBLIC_READ_PER_MINUTE',60,600))
    app.state.api_requests=RequestWindow(setting('API_REQUESTS_PER_MINUTE',240,1200))
    app.state.snapshot_cache=SnapshotCache()
    slots = asyncio.Semaphore(2)
    app.add_middleware(BodyLimit)
    app.include_router(materials_router)
    app.include_router(images_router)
    app.include_router(public_router)

    @app.exception_handler(GoogleAPICallError)
    async def persistence_error(request, exc):
        return JSONResponse(status_code=503, content={"detail":"保存先に接続できません。少し待って再試行してください。"})

    @app.middleware("http")
    async def secure_headers(request, call_next):
        if request.url.path.startswith('/api/') and request.url.path!='/api/health' and not app.state.api_requests.take():
            response=JSONResponse(status_code=429,content={'detail':'アクセスが集中しています。少し待って再試行してください。'},headers={'Retry-After':'60'})
        else:response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self' https://*.googleapis.com https://*.securetoken.google.com; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/config")
    def config():
        return {"demo": demo, "authMode": os.environ.get("AUTH_MODE", "firebase"),
                "persistence": bool(os.environ.get("FIRESTORE_PROJECT_ID")) and not demo,
                "firebase": {"apiKey":os.environ.get('FIREBASE_WEB_API_KEY'),"projectId":os.environ.get('FIREBASE_PROJECT_ID'),"authDomain":os.environ.get('FIREBASE_AUTH_DOMAIN')} if os.environ.get('FIREBASE_WEB_API_KEY') else None,
                "serviceBaseUrl": os.environ.get('SERVICE_BASE_URL',''),
                "publicAccess": os.environ.get('PUBLIC_ACCESS')=='true'}

    @app.get('/api/me')
    def me(uid: str = Depends(teacher)):
        return {'uid':uid,'teacher':True}

    @app.post("/api/analyze", response_model=Draft)
    async def analyze(request:Request,file: UploadFile = File(...), uid: str = Depends(teacher)):
        try:
            if file.content_type not in {"image/png", "image/jpeg"}:
                raise HTTPException(415, "PNGまたはJPEGを選択してください。")
            data = await file.read(MAX_FILE + 1)
        finally:
            await file.close()
        if len(data) > MAX_FILE:
            raise HTTPException(413, "画像は5 MiB以下にしてください。")
        clean = await asyncio.to_thread(normalize_image, data, file.content_type)
        if demo:
            # Deliberately does not claim to analyze the uploaded image.
            return Draft(source="demo", extraction=Extraction(
                supported=True, reason=None, title="操作確認用の固定データ（画像の解析結果ではありません）", unit="人",
                categories=[{"label": "A組", "value": 12, "evidence": "12"}, {"label": "B組", "value": None, "evidence": None}],
                warnings=["デモデータです。Geminiは呼び出していません。"],
            ))
        if not os.environ.get("GEMINI_API_KEY") or not os.environ.get("GEMINI_MODEL"):
            raise HTTPException(503, "Gemini接続が設定されていません。管理者に連絡してください。")
        if slots.locked():
            raise HTTPException(429, "解析が混み合っています。少し待って再試行してください。")
        await asyncio.to_thread(reserve_usage,request,uid,'analysis')
        try:
            async with slots:
                result = await app.state.extractor(clean)
        except (TimeoutError, asyncio.TimeoutError):
            raise HTTPException(504, "解析が時間切れになりました。再試行してください。") from None
        except (ValidationError, ValueError):
            raise HTTPException(502, "解析結果を安全に読み取れませんでした。別の画像をお試しください。") from None
        except Exception:
            raise HTTPException(502, "画像を解析できませんでした。接続設定や画像を確認してください。") from None
        if not result.supported:
            return JSONResponse(status_code=422, content={"detail": "対応範囲外の画像です。数値ラベル付きの単系列縦棒グラフを選択してください。"})
        result=normalize_extraction(result)
        image_id = None
        if os.environ.get('IMAGE_BUCKET'):
            project=os.environ.get('FIRESTORE_PROJECT_ID')
            if not project:
                raise HTTPException(503,'画像保存先が設定されていません。')
            image_id=await asyncio.to_thread(save_image,clean,uid,firestore_repository(project))
        return Draft(source="gemini", extraction=result,image_id=image_id)

    # Unknown API routes must never be mistaken for a SPA page.
    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def missing_api(path: str):
        raise HTTPException(404, "APIが見つかりません。")

    static = Path(__file__).resolve().parents[1] / "static"
    if static.is_dir():
        @app.get('/learn/{identifier}')
        def learner_page(identifier: str):
            return FileResponse(static/'index.html')
        app.mount("/", StaticFiles(directory=static, html=True), name="frontend")
    return app


app = create_app()
