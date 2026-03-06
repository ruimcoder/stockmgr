from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import get_session, init_db
from app.i18n import SUPPORTED_LANGUAGES, translate
from app.models import StockItem, User
from app.schemas import (
    BarcodeLookupRequest,
    BarcodeLookupResult,
    ItemCreate,
    ItemRead,
)
from app.services.barcode import BarcodeLookupService
from app.services.calendar import CalendarSyncError, CalendarSyncService
from app.services.imports import parse_import_file

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="stockmgr MVP", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware, secret_key=settings.secret_key, same_site="lax", https_only=False
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

oauth = OAuth()
if settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": (
                "openid email profile "
                "https://www.googleapis.com/auth/calendar.events "
                "https://www.googleapis.com/auth/calendar.readonly"
            )
        },
    )

if settings.microsoft_client_id and settings.microsoft_client_secret:
    oauth.register(
        name="microsoft",
        client_id=settings.microsoft_client_id,
        client_secret=settings.microsoft_client_secret,
        server_metadata_url=(
            "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration"
        ),
        client_kwargs={
            "scope": "openid profile email offline_access User.Read Calendars.ReadWrite"
        },
    )

barcode_service = BarcodeLookupService(settings)
calendar_service = CalendarSyncService(settings)


def _render(
    request: Request,
    template_name: str,
    context: dict[str, Any] | None = None,
    status_code: int = 200,
):
    lang = _current_language(request)
    payload = {
        "request": request,
        "settings": settings,
        "lang": lang,
        "t": lambda key: translate(lang, key),
    }
    if context:
        payload.update(context)
    return templates.TemplateResponse(request, template_name, payload, status_code=status_code)


def _current_language(request: Request) -> str:
    lang = request.session.get("lang", "en")
    if lang not in SUPPORTED_LANGUAGES:
        return "en"
    return lang


def _current_user(request: Request, session: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return session.get(User, user_id)


def _require_user_or_redirect(request: Request, session: Session) -> User | RedirectResponse:
    user = _current_user(request, session)
    if user:
        return user
    return RedirectResponse("/login", status_code=303)


def _require_api_user(request: Request, session: Session = Depends(get_session)) -> User:
    user = _current_user(request, session)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


def _upsert_user(
    session: Session,
    *,
    provider: str,
    subject: str,
    email: str,
    display_name: str,
    access_token: str | None = None,
    refresh_token: str | None = None,
) -> User:
    query = select(User).where(User.oauth_provider == provider, User.oauth_subject == subject)
    existing = session.exec(query).first()
    if existing:
        existing.email = email
        existing.display_name = display_name
        if access_token:
            existing.access_token = access_token
        if refresh_token:
            existing.refresh_token = refresh_token
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    user = User(
        email=email,
        display_name=display_name,
        oauth_provider=provider,
        oauth_subject=subject,
        access_token=access_token,
        refresh_token=refresh_token,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _item_payload_from_form(form: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in (
        "barcode",
        "batch_code",
        "name",
        "item_type",
        "storage_location",
        "storage_bucket",
        "expiry_date",
        "temp_min_c",
        "temp_max_c",
        "humidity_min_pct",
        "humidity_max_pct",
        "renewal_date",
    ):
        value = form.get(key)
        if key == "storage_bucket":
            payload[key] = value if value not in ("", None) else ""
        else:
            payload[key] = value if value not in ("", None) else None
    return payload


def _to_read_model(item: StockItem) -> ItemRead:
    return ItemRead.model_validate(item.model_dump())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/lang/{lang_code}")
def set_language(lang_code: str, request: Request):
    if lang_code not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="Unsupported language.")
    request.session["lang"] = lang_code
    return RedirectResponse(request.headers.get("referer") or "/", status_code=303)


@app.get("/login")
def login_page(request: Request, session: Session = Depends(get_session)):
    user = _current_user(request, session)
    if user:
        return RedirectResponse("/", status_code=303)
    available_oauth = [name for name in ("google", "microsoft") if oauth.create_client(name)]
    return _render(
        request,
        "login.html",
        {"available_oauth": available_oauth, "auth_mode": settings.auth_mode},
    )


@app.post("/auth/dev-login")
def dev_login(
    request: Request,
    email: str = Form(...),
    display_name: str = Form("Local User"),
    session: Session = Depends(get_session),
):
    if settings.auth_mode != "dev":
        raise HTTPException(status_code=403, detail="Development login is disabled.")
    user = _upsert_user(
        session,
        provider="dev",
        subject=email.lower(),
        email=email.lower(),
        display_name=display_name,
    )
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@app.get("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/auth/{provider}/start")
async def oauth_start(request: Request, provider: str):
    client = oauth.create_client(provider)
    if not client:
        raise HTTPException(status_code=404, detail=f"OAuth provider '{provider}' is unavailable.")
    redirect_uri = request.url_for("oauth_callback", provider=provider)
    return await client.authorize_redirect(request, str(redirect_uri))


@app.get("/auth/{provider}/callback")
async def oauth_callback(
    request: Request,
    provider: str,
    session: Session = Depends(get_session),
):
    client = oauth.create_client(provider)
    if not client:
        raise HTTPException(status_code=404, detail=f"OAuth provider '{provider}' is unavailable.")

    token = await client.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if not userinfo:
        if provider == "google":
            userinfo = await client.userinfo(token=token)
        elif provider == "microsoft":
            async with httpx.AsyncClient(timeout=8) as http_client:
                graph_response = await http_client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {token.get('access_token')}"},
                )
            graph_response.raise_for_status()
            userinfo = graph_response.json()
        else:
            raise HTTPException(status_code=400, detail="Unsupported OAuth provider.")

    email = userinfo.get("email") or userinfo.get("mail") or userinfo.get("userPrincipalName")
    if not email:
        raise HTTPException(
            status_code=400, detail="OAuth profile does not include an email address."
        )
    subject = str(userinfo.get("sub") or userinfo.get("id") or email)
    display_name = userinfo.get("name") or email.split("@")[0]

    user = _upsert_user(
        session,
        provider=provider,
        subject=subject,
        email=email.lower(),
        display_name=display_name,
        access_token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
    )
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@app.get("/")
def index(request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user
    statement = (
        select(StockItem)
        .where(StockItem.user_id == user.id)
        .order_by(StockItem.name, StockItem.batch_code, StockItem.expiry_date)
    )
    items = session.exec(statement).all()
    return _render(
        request,
        "index.html",
        {"user": user, "items": items, "message": request.query_params.get("m")},
    )


@app.get("/items/new")
def item_new(request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    return _render(request, "item_form.html", {"mode": "create", "draft": {}, "lookup": None})


@app.get("/items/{item_id}/edit")
def item_edit(item_id: int, request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user
    item = session.get(StockItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found.")
    return _render(request, "item_form.html", {"mode": "edit", "draft": item, "lookup": None})


@app.post("/items/lookup")
async def lookup_for_form(
    request: Request,
    barcode: str = Form(...),
    item_type: str = Form("unknown"),
    session: Session = Depends(get_session),
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    result = await barcode_service.lookup(barcode=barcode, item_type=item_type)
    draft: dict[str, Any] = {"barcode": barcode, "item_type": item_type}
    if result.found and result.data:
        draft.update(
            {
                "name": result.data.get("name"),
                "item_type": item_type
                if item_type != "unknown"
                else (result.data.get("category") or "unknown"),
                "batch_code": "",
                "storage_location": "",
                "storage_bucket": "",
            }
        )
    return _render(request, "item_form.html", {"mode": "create", "draft": draft, "lookup": result})


@app.post("/items")
async def item_create(request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user
    form = await request.form()
    payload = _item_payload_from_form(dict(form))
    try:
        item_in = ItemCreate.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    item = StockItem(**item_in.model_dump(), user_id=user.id)
    session.add(item)
    session.commit()
    session.refresh(item)

    try:
        await calendar_service.schedule_renewal(user=user, item=item)
    except CalendarSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return RedirectResponse("/?m=item-created", status_code=303)


@app.post("/items/{item_id}/update")
async def item_update(item_id: int, request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user
    item = session.get(StockItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found.")

    form = await request.form()
    payload = _item_payload_from_form(dict(form))
    try:
        item_in = ItemCreate.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    for key, value in item_in.model_dump().items():
        setattr(item, key, value)
    item.updated_at = datetime.now(UTC)
    session.add(item)
    session.commit()
    session.refresh(item)

    try:
        await calendar_service.schedule_renewal(user=user, item=item)
    except CalendarSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return RedirectResponse("/?m=item-updated", status_code=303)


@app.post("/items/{item_id}/delete")
def item_delete(item_id: int, request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user
    item = session.get(StockItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found.")
    session.delete(item)
    session.commit()
    return RedirectResponse("/?m=item-deleted", status_code=303)


@app.get("/items/import")
def import_page(request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    return _render(request, "import.html", {"result": None})


@app.post("/items/import")
async def import_items(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user
    file_bytes = await file.read()
    items, result = parse_import_file(file_bytes, file.filename or "")
    for item_in in items:
        item = StockItem(**item_in.model_dump(), user_id=user.id)
        session.add(item)
    session.commit()
    return _render(request, "import.html", {"result": result})


@app.get("/api/items", response_model=list[ItemRead])
def api_list_items(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(_require_api_user),
):
    _ = request
    items = session.exec(select(StockItem).where(StockItem.user_id == user.id)).all()
    return [_to_read_model(item) for item in items]


@app.post("/api/items", response_model=ItemRead)
async def api_create_item(
    item_in: ItemCreate,
    session: Session = Depends(get_session),
    user: User = Depends(_require_api_user),
):
    item = StockItem(**item_in.model_dump(), user_id=user.id)
    session.add(item)
    session.commit()
    session.refresh(item)
    try:
        await calendar_service.schedule_renewal(user=user, item=item)
    except CalendarSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _to_read_model(item)


@app.post("/api/barcode-lookup", response_model=BarcodeLookupResult)
async def api_barcode_lookup(
    payload: BarcodeLookupRequest,
    user: User = Depends(_require_api_user),
):
    _ = user
    return await barcode_service.lookup(payload.barcode, payload.item_type)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
