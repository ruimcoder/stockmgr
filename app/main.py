from __future__ import annotations

import math
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import func
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import get_session, init_db
from app.i18n import SUPPORTED_LANGUAGES, translate
from app.models import StockItem, StockMovement, User
from app.schemas import BarcodeLookupRequest, BarcodeLookupResult, ItemCreate, ItemRead
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
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
    https_only=False,
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


def _current_language(request: Request) -> str:
    lang = request.session.get("lang", "en")
    if lang not in SUPPORTED_LANGUAGES:
        return "en"
    return lang


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


def _admin_email_set() -> set[str]:
    values = [entry.strip().lower() for entry in settings.admin_emails.split(",")]
    return {entry for entry in values if entry}


def _count_approved_admins(session: Session) -> int:
    query = (
        select(func.count())
        .select_from(User)
        .where(
            User.approval_status == "approved",
            User.is_admin.is_(True),
        )
    )
    return int(session.exec(query).one() or 0)


def _new_user_status(email: str, session: Session) -> tuple[str, bool]:
    email_l = email.lower()
    admin_emails = _admin_email_set()
    if email_l in admin_emails:
        return "approved", True
    if _count_approved_admins(session) == 0:
        return "approved", True
    return "pending", False


def _current_user(request: Request, session: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return session.get(User, user_id)


def _require_user_or_redirect(request: Request, session: Session) -> User | RedirectResponse:
    user = _current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user.approval_status != "approved":
        request.session.clear()
        return RedirectResponse("/login?m=account-not-approved", status_code=303)
    return user


def _require_api_user(request: Request, session: Session = Depends(get_session)) -> User:
    user = _current_user(request, session)
    if not user or user.approval_status != "approved":
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


def _require_admin_user(request: Request, session: Session = Depends(get_session)) -> User:
    user = _require_api_user(request, session)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


def _upsert_oauth_user(
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
    now = datetime.now(UTC)
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

    approval_status, is_admin = _new_user_status(email, session)
    user = User(
        email=email,
        display_name=display_name,
        oauth_provider=provider,
        oauth_subject=subject,
        approval_status=approval_status,
        is_admin=is_admin,
        access_token=access_token,
        refresh_token=refresh_token,
        requested_at=now,
        approved_at=now if approval_status == "approved" else None,
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
        "quantity",
        "unidose_per_pack",
        "target_unidoses_location",
        "temp_min_c",
        "temp_max_c",
        "humidity_min_pct",
        "humidity_max_pct",
        "renewal_date",
    ):
        value = form.get(key)
        if key == "storage_bucket":
            payload[key] = value if value not in ("", None) else ""
        elif key == "quantity":
            payload[key] = int(value) if value not in ("", None) else 0
        elif key == "unidose_per_pack":
            payload[key] = int(value) if value not in ("", None) else 1
        elif key == "target_unidoses_location":
            payload[key] = int(value) if value not in ("", None) else 0
        else:
            payload[key] = value if value not in ("", None) else None
    return payload


def _to_read_model(item: StockItem) -> ItemRead:
    return ItemRead.model_validate(item.model_dump())


def _fetch_message(request: Request) -> str | None:
    return request.query_params.get("m")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest() -> FileResponse:
    return FileResponse(
        BASE_DIR / "static" / "manifest.webmanifest",
        media_type="application/manifest+json",
    )


@app.get("/service-worker.js", include_in_schema=False)
def service_worker() -> FileResponse:
    return FileResponse(
        BASE_DIR / "static" / "service-worker.js",
        media_type="application/javascript",
    )


@app.get("/offline.html", include_in_schema=False)
def offline_page() -> FileResponse:
    return FileResponse(
        BASE_DIR / "static" / "offline.html",
        media_type="text/html",
    )


@app.get("/lang/{lang_code}")
def set_language(lang_code: str, request: Request):
    if lang_code not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="Unsupported language.")
    request.session["lang"] = lang_code
    return RedirectResponse(request.headers.get("referer") or "/", status_code=303)


@app.get("/register")
def register_page(request: Request, session: Session = Depends(get_session)):
    user = _current_user(request, session)
    if user and user.approval_status == "approved":
        return RedirectResponse("/", status_code=303)
    return _render(request, "register.html", {"message": _fetch_message(request)})


@app.post("/register")
def register_user(
    request: Request,
    email: str = Form(...),
    display_name: str = Form(...),
    session: Session = Depends(get_session),
):
    email_l = email.strip().lower()
    query = select(User).where(User.oauth_provider == "dev", User.oauth_subject == email_l)
    existing = session.exec(query).first()
    if existing:
        return RedirectResponse("/login?m=register-already-exists", status_code=303)

    now = datetime.now(UTC)
    status, is_admin = _new_user_status(email_l, session)
    user = User(
        email=email_l,
        display_name=display_name.strip() or email_l,
        oauth_provider="dev",
        oauth_subject=email_l,
        approval_status=status,
        is_admin=is_admin,
        requested_at=now,
        approved_at=now if status == "approved" else None,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    if user.approval_status == "approved":
        request.session["user_id"] = user.id
        return RedirectResponse("/?m=registered-approved", status_code=303)
    return RedirectResponse("/login?m=registration-pending", status_code=303)


@app.get("/login")
def login_page(request: Request, session: Session = Depends(get_session)):
    user = _current_user(request, session)
    if user and user.approval_status == "approved":
        return RedirectResponse("/", status_code=303)
    available_oauth = [name for name in ("google", "microsoft") if oauth.create_client(name)]
    return _render(
        request,
        "login.html",
        {
            "available_oauth": available_oauth,
            "auth_mode": settings.auth_mode,
            "message": _fetch_message(request),
        },
    )


@app.post("/auth/dev-login")
def dev_login(
    request: Request,
    email: str = Form(...),
    session: Session = Depends(get_session),
):
    if settings.auth_mode != "dev":
        raise HTTPException(status_code=403, detail="Development login is disabled.")

    email_l = email.strip().lower()
    query = select(User).where(User.oauth_provider == "dev", User.oauth_subject == email_l)
    user = session.exec(query).first()
    if not user:
        return RedirectResponse("/register?m=login-register-first", status_code=303)
    if user.approval_status != "approved":
        return RedirectResponse("/login?m=login-pending-approval", status_code=303)
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

    user = _upsert_oauth_user(
        session,
        provider=provider,
        subject=subject,
        email=email.lower(),
        display_name=display_name,
        access_token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
    )
    if user.approval_status != "approved":
        return RedirectResponse("/login?m=login-pending-approval", status_code=303)
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@app.get("/")
def index(request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user
    bucket_filter = request.query_params.get("bucket_filter", "all")
    location_filter = request.query_params.get("location_filter", "").strip()
    statement = select(StockItem).where(StockItem.user_id == user.id)
    if bucket_filter == "assigned":
        statement = statement.where(StockItem.storage_bucket != "")
    elif bucket_filter == "unassigned":
        statement = statement.where(StockItem.storage_bucket == "")
    if location_filter:
        statement = statement.where(StockItem.storage_location == location_filter)
    statement = statement.order_by(StockItem.name, StockItem.batch_code, StockItem.expiry_date)
    items = session.exec(statement).all()
    locations = session.exec(
        select(StockItem.storage_location)
        .where(StockItem.user_id == user.id)
        .distinct()
        .order_by(StockItem.storage_location)
    ).all()
    return _render(
        request,
        "index.html",
        {
            "user": user,
            "items": items,
            "locations": locations,
            "bucket_filter": bucket_filter,
            "location_filter": location_filter,
            "message": _fetch_message(request),
        },
    )


@app.get("/stock/views")
def stock_views(request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user

    overall_query = (
        select(
            StockItem.name,
            StockItem.item_type,
            func.sum(StockItem.quantity).label("quantity"),
        )
        .where(StockItem.user_id == user.id)
        .group_by(StockItem.name, StockItem.item_type)
        .order_by(StockItem.name)
    )
    by_location_query = (
        select(
            StockItem.name,
            StockItem.item_type,
            StockItem.storage_location,
            func.sum(StockItem.quantity).label("quantity"),
            func.sum(StockItem.quantity * StockItem.unidose_per_pack).label("total_unidoses"),
            func.max(StockItem.target_unidoses_location).label("target_unidoses"),
        )
        .where(StockItem.user_id == user.id)
        .group_by(StockItem.name, StockItem.item_type, StockItem.storage_location)
        .order_by(StockItem.name, StockItem.storage_location)
    )
    by_location_expiry_query = (
        select(
            StockItem.name,
            StockItem.item_type,
            StockItem.storage_location,
            StockItem.expiry_date,
            func.sum(StockItem.quantity).label("quantity"),
            func.sum(StockItem.quantity * StockItem.unidose_per_pack).label("total_unidoses"),
        )
        .where(StockItem.user_id == user.id)
        .group_by(
            StockItem.name,
            StockItem.item_type,
            StockItem.storage_location,
            StockItem.expiry_date,
        )
        .order_by(StockItem.name, StockItem.storage_location, StockItem.expiry_date)
    )

    return _render(
        request,
        "stock_views.html",
        {
            "user": user,
            "overall_rows": session.exec(overall_query).all(),
            "location_rows": session.exec(by_location_query).all(),
            "validity_rows": session.exec(by_location_expiry_query).all(),
        },
    )


@app.get("/shopping-list")
def shopping_list(request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user
    location_rows = session.exec(
        select(
            StockItem.name,
            StockItem.item_type,
            StockItem.storage_location,
            func.sum(StockItem.quantity * StockItem.unidose_per_pack).label("total_unidoses"),
            func.max(StockItem.target_unidoses_location).label("target_unidoses"),
            func.max(StockItem.unidose_per_pack).label("unidose_per_pack"),
        )
        .where(StockItem.user_id == user.id)
        .group_by(StockItem.name, StockItem.item_type, StockItem.storage_location)
        .order_by(StockItem.name, StockItem.storage_location)
    ).all()

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in location_rows:
        name, item_type, location, total_u, target_u, per_pack = row
        total_unidoses = int(total_u or 0)
        target_unidoses = int(target_u or 0)
        per_pack_value = max(1, int(per_pack or 1))
        delta_unidoses = max(target_unidoses - total_unidoses, 0)
        qty_to_buy = math.ceil(delta_unidoses / per_pack_value) if delta_unidoses else 0
        key = (name, item_type)
        if key not in grouped:
            grouped[key] = {
                "name": name,
                "item_type": item_type,
                "total_quantity_to_buy": 0,
                "distribution": [],
            }
        grouped[key]["total_quantity_to_buy"] += qty_to_buy
        if qty_to_buy > 0:
            grouped[key]["distribution"].append(f"{location}: {qty_to_buy}")

    rows = [value for value in grouped.values() if value["total_quantity_to_buy"] > 0]
    rows.sort(key=lambda item: (item["name"], item["item_type"]))
    return _render(request, "shopping_list.html", {"user": user, "rows": rows})


@app.get("/renewals")
def renewal_plan(
    request: Request, session: Session = Depends(get_session), days: int | None = None
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user

    window_days = days if days and days > 0 else settings.renewal_window_days
    start = date.today()
    end = start + timedelta(days=window_days)
    statement = (
        select(StockItem)
        .where(
            StockItem.user_id == user.id,
            StockItem.renewal_date.is_not(None),
            StockItem.renewal_date >= start,
            StockItem.renewal_date <= end,
        )
        .order_by(StockItem.renewal_date, StockItem.name)
    )
    rows = session.exec(statement).all()
    return _render(
        request,
        "renewals.html",
        {
            "user": user,
            "window_days": window_days,
            "rows": rows,
        },
    )


@app.get("/products/by-name/{item_type}/{product_name}")
def product_detail(
    item_type: str,
    product_name: str,
    request: Request,
    session: Session = Depends(get_session),
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user

    batch_query = (
        select(StockItem)
        .where(
            StockItem.user_id == user.id,
            StockItem.item_type == item_type,
            StockItem.name == product_name,
        )
        .order_by(StockItem.expiry_date, StockItem.storage_location, StockItem.storage_bucket)
    )
    batches = session.exec(batch_query).all()
    if not batches:
        raise HTTPException(status_code=404, detail="Product not found.")

    movement_query = (
        select(StockMovement, StockItem)
        .join(StockItem, StockItem.id == StockMovement.stock_item_id)
        .where(
            StockItem.user_id == user.id,
            StockItem.item_type == item_type,
            StockItem.name == product_name,
        )
        .order_by(StockMovement.created_at.desc())
    )
    movement_rows = session.exec(movement_query).all()
    return _render(
        request,
        "product_detail.html",
        {
            "user": user,
            "item_type": item_type,
            "product_name": product_name,
            "batches": batches,
            "movement_rows": movement_rows,
            "message": _fetch_message(request),
        },
    )


@app.get("/items/new")
def item_new(request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    return _render(
        request,
        "item_form.html",
        {
            "user": maybe_user,
            "mode": "create",
            "draft": {"quantity": 0, "unidose_per_pack": 1, "target_unidoses_location": 0},
            "lookup": None,
        },
    )


@app.get("/items/{item_id}/edit")
def item_edit(item_id: int, request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user
    item = session.get(StockItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found.")
    return _render(
        request,
        "item_form.html",
        {"user": user, "mode": "edit", "draft": item, "lookup": None},
    )


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
    draft: dict[str, Any] = {"barcode": barcode, "item_type": item_type, "quantity": 0}
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
                "unidose_per_pack": 1,
                "target_unidoses_location": 0,
            }
        )
    return _render(
        request,
        "item_form.html",
        {"user": maybe_user, "mode": "create", "draft": draft, "lookup": result},
    )


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

    if item.quantity > 0:
        session.add(
            StockMovement(
                stock_item_id=item.id,
                user_id=user.id,
                delta=item.quantity,
                note="Initial stock quantity",
            )
        )
        session.commit()

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

    previous_quantity = item.quantity
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

    quantity_delta = item.quantity - previous_quantity
    if quantity_delta:
        session.add(
            StockMovement(
                stock_item_id=item.id,
                user_id=user.id,
                delta=quantity_delta,
                note="Quantity updated in edit form",
            )
        )
        session.commit()

    try:
        await calendar_service.schedule_renewal(user=user, item=item)
    except CalendarSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return RedirectResponse("/?m=item-updated", status_code=303)


@app.post("/items/{item_id}/move")
def adjust_stock_quantity(
    item_id: int,
    request: Request,
    direction: str = Form(...),
    quantity_step: int = Form(1),
    note: str = Form(""),
    session: Session = Depends(get_session),
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user
    item = session.get(StockItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found.")

    step = max(1, int(quantity_step))
    if direction not in {"in", "out"}:
        raise HTTPException(status_code=400, detail="Invalid stock movement direction.")
    delta = step if direction == "in" else -step
    new_quantity = item.quantity + delta
    if new_quantity < 0:
        raise HTTPException(status_code=400, detail="Cannot reduce below zero.")

    item.quantity = new_quantity
    item.updated_at = datetime.now(UTC)
    session.add(item)
    session.add(
        StockMovement(
            stock_item_id=item.id,
            user_id=user.id,
            delta=delta,
            note=(note or "").strip() or None,
        )
    )
    session.commit()

    target = request.headers.get("referer") or "/"
    return RedirectResponse(target, status_code=303)


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
    return _render(request, "import.html", {"user": maybe_user, "result": None})


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
    return _render(request, "import.html", {"user": user, "result": result})


@app.get("/admin/users")
def admin_users(
    request: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(_require_admin_user),
):
    users = session.exec(select(User).order_by(User.requested_at.desc())).all()
    return _render(
        request,
        "admin_users.html",
        {"user": admin, "users": users, "message": _fetch_message(request)},
    )


@app.post("/admin/users/{user_id}/approve")
def admin_approve_user(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(_require_admin_user),
):
    _ = request
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.approval_status = "approved"
    user.approved_at = datetime.now(UTC)
    session.add(user)
    session.commit()
    return RedirectResponse("/admin/users?m=user-approved", status_code=303)


@app.post("/admin/users/{user_id}/reject")
def admin_reject_user(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(_require_admin_user),
):
    _ = request
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.approval_status = "rejected"
    user.approved_at = None
    session.add(user)
    session.commit()
    return RedirectResponse("/admin/users?m=user-rejected", status_code=303)


@app.post("/admin/users/{user_id}/toggle-admin")
def admin_toggle_admin(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(_require_admin_user),
):
    _ = request
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == admin.id and user.is_admin and _count_approved_admins(session) <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove the last admin.")
    user.is_admin = not user.is_admin
    session.add(user)
    session.commit()
    return RedirectResponse("/admin/users?m=user-role-updated", status_code=303)


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
    if item.quantity > 0:
        session.add(
            StockMovement(
                stock_item_id=item.id,
                user_id=user.id,
                delta=item.quantity,
                note="Initial stock quantity",
            )
        )
        session.commit()
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
