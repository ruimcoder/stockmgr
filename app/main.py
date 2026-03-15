from __future__ import annotations

import json
import logging
import math
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote as url_quote
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.starlette_client import OAuth
from authlib.jose.errors import JoseError
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
from app.food_wheel import FOOD_GROUP_BY_KEY, FOOD_GROUPS, food_group_chart_data, infer_food_group
from app.i18n import SUPPORTED_LANGUAGES, translate
from app.models import LocationPlan, StockItem, StockMovement, User
from app.schemas import (
    BarcodeLookupRequest,
    BarcodeLookupResult,
    ExcelStockUpsertRequest,
    ExcelStockUpsertRow,
    ItemCreate,
    ItemRead,
    LocationPlanCreate,
    TelegramUpdate,
)
from app.services.barcode import BarcodeLookupService
from app.services.calendar import CalendarSyncError, CalendarSyncService
from app.services.imports import parse_import_file
from app.services.telegram import (
    TelegramConfigError,
    TelegramDeliveryError,
    TelegramSecurityError,
    TelegramService,
)

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)

_DEFAULT_SECRET_KEY = "change-me-for-production"


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.environment == "production":
        if settings.secret_key == _DEFAULT_SECRET_KEY:
            raise RuntimeError(
                "SECRET_KEY is set to the default insecure value. "
                "Set a strong SECRET_KEY environment variable before running in production."
            )
    init_db()
    yield


app = FastAPI(title="stockmgr MVP", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
    https_only=settings.environment == "production",
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Media uploads directory (product images)
_MEDIA_DIR = BASE_DIR.parent / "media"
_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(_MEDIA_DIR)), name="media")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["urlencode_path"] = lambda v: url_quote(str(v), safe="")


def _datefmt(value: object) -> str:
    from datetime import date as _date, datetime as _datetime

    if value is None:
        return "-"
    if isinstance(value, (_date, _datetime)):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, str) and value:
        try:
            return _date.fromisoformat(value).strftime("%d/%m/%Y")
        except ValueError:
            return value
    return str(value) if value else "-"


templates.env.filters["datefmt"] = _datefmt


def _datefmt(value: object) -> str:
    from datetime import date as _date, datetime as _datetime

    if value is None:
        return "-"
    if isinstance(value, (_date, _datetime)):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, str) and value:
        try:
            return _date.fromisoformat(value).strftime("%d/%m/%Y")
        except ValueError:
            return value
    return str(value) if value else "-"


templates.env.filters["datefmt"] = _datefmt

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
telegram_service = TelegramService(settings)


def _current_language(request: Request) -> str:
    lang = request.session.get("lang", "en")
    if lang not in SUPPORTED_LANGUAGES:
        return "en"
    return lang


def _get_or_create_csrf_token(request: Request) -> str:
    """Return the CSRF token stored in the session, generating one if absent."""
    token = request.session.get("_csrf_token")
    if not token:
        token = secrets.token_hex(32)
        request.session["_csrf_token"] = token
    return token


async def _validate_csrf(request: Request) -> None:
    """Dependency: validate the CSRF token submitted with an HTML form POST."""
    session_token = request.session.get("_csrf_token")
    if not session_token:
        raise HTTPException(status_code=403, detail="CSRF protection: session token missing.")
    form = await request.form()
    form_token = str(form.get("_csrf_token", ""))
    if not secrets.compare_digest(session_token, form_token):
        raise HTTPException(status_code=403, detail="CSRF protection: token mismatch.")


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
        "csrf_token": _get_or_create_csrf_token(request),
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


def _require_excel_api_user(request: Request, session: Session = Depends(get_session)) -> User:
    configured_key = settings.excel_api_key.strip()
    if not configured_key:
        raise HTTPException(status_code=503, detail="Excel API access is not configured.")

    provided_key = (
        request.headers.get("x-excel-api-key")
        or request.headers.get("x-api-key")
        or request.query_params.get("api_key")
    )
    if (provided_key or "").strip() != configured_key:
        raise HTTPException(status_code=401, detail="Invalid Excel API key.")

    target_email = (
        request.headers.get("x-excel-user-email")
        or request.headers.get("x-user-email")
        or request.query_params.get("user_email")
        or settings.excel_api_user_email
    )
    email = (target_email or "").strip().lower()
    if not email:
        raise HTTPException(
            status_code=400,
            detail="Excel API user email is required via header, query, or configuration.",
        )

    user = session.exec(select(User).where(User.email == email)).first()
    if not user or user.approval_status != "approved":
        raise HTTPException(status_code=404, detail="Excel API user not found or not approved.")
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


def _parse_size(size_str: str | None) -> tuple[float | None, str | None]:
    """Parse a size string like '500g', '1.5kg', '250ml' into (value, unit)."""
    import re as _re
    if not size_str:
        return None, None
    m = _re.match(r"([0-9]+(?:[.,][0-9]+)?)\s*([a-zA-Z]+)", size_str.strip())
    if not m:
        return None, None
    try:
        val = float(m.group(1).replace(",", "."))
        unit = m.group(2).lower()
        return val, unit
    except ValueError:
        return None, None


def _item_payload_from_form(form: dict[str, Any]) -> dict[str, Any]:
    selected_storage_location = form.get("storage_location")
    if selected_storage_location == "__new__":
        form["storage_location"] = form.get("storage_location_new")
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
        "comment",
        "image_url",
        "nutriscore",
        "food_group",
        "weight_capacity",
        "uom",
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
        elif key == "weight_capacity":
            payload[key] = float(value) if value not in ("", None) else None
        else:
            payload[key] = value if value not in ("", None) else None
    return payload


def _to_read_model(item: StockItem) -> ItemRead:
    return ItemRead.model_validate(item.model_dump())


def _excel_match_existing_item(session: Session, *, row: ExcelStockUpsertRow) -> StockItem | None:
    return session.exec(
        select(StockItem).where(
            StockItem.name == row.name,
            StockItem.item_type == row.item_type,
            StockItem.storage_location == row.storage_location,
            StockItem.storage_bucket == row.storage_bucket,
            StockItem.batch_code == row.batch_code,
            StockItem.expiry_date == row.expiry_date,
            StockItem.barcode == row.barcode,
        )
    ).first()


def _apply_item_create_to_stock(item: StockItem, item_in: ItemCreate) -> None:
    for key, value in item_in.model_dump().items():
        setattr(item, key, value)
    item.updated_at = datetime.now(UTC)


def _fetch_message(request: Request) -> str | None:
    return request.query_params.get("m")


def _looks_like_barcode(value: str) -> bool:
    normalized = value.replace(" ", "").strip()
    return normalized.isdigit() and 8 <= len(normalized) <= 20


def _product_batches(
    session: Session,
    *,
    item_type: str,
    product_name: str,
) -> list[StockItem]:
    batch_query = (
        select(StockItem)
        .where(
            StockItem.item_type == item_type,
            StockItem.name == product_name,
        )
        .order_by(StockItem.expiry_date, StockItem.storage_location, StockItem.storage_bucket)
    )
    return session.exec(batch_query).all()


def _storage_location_options(session: Session) -> list[str]:
    rows = session.exec(
        select(StockItem.storage_location)
        .where(StockItem.storage_location != "")
        .distinct()
        .order_by(func.lower(StockItem.storage_location), StockItem.storage_location)
    ).all()
    return [row for row in rows if row]


def _storage_location_field_context(
    session: Session, *, selected_location: str | None
) -> dict[str, Any]:
    location_options = _storage_location_options(session)
    selected = (selected_location or "").strip()
    if selected and selected in location_options:
        return {
            "storage_location_options": location_options,
            "storage_location_selection": selected,
            "storage_location_new_value": "",
        }
    if selected:
        return {
            "storage_location_options": location_options,
            "storage_location_selection": "__new__",
            "storage_location_new_value": selected,
        }
    return {
        "storage_location_options": location_options,
        "storage_location_selection": "",
        "storage_location_new_value": "",
    }


def _plan_locations(session: Session) -> list[str]:
    """Return sorted unique location names from LocationPlans + existing StockItems."""
    plan_locs = session.exec(
        select(LocationPlan.location).distinct().order_by(LocationPlan.location)
    ).all()
    item_locs = session.exec(
        select(StockItem.storage_location)
        .where(StockItem.storage_location != "")
        .distinct()
        .order_by(func.lower(StockItem.storage_location))
        .order_by(func.lower(StockItem.storage_location))
    ).all()
    seen: set[str] = set()
    result: list[str] = []
    for loc in list(plan_locs) + [r for r in item_locs if r]:
        key = (loc or "").strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _upsert_location_plan(session: Session, *, location: str, participants: int, stock_duration_days: int) -> None:
    """Create or update a LocationPlan for the given location."""
    location = location.strip()
    if not location:
        return
    existing = session.exec(select(LocationPlan).where(LocationPlan.location == location)).first()
    if existing:
        existing.participants = participants
        existing.stock_duration_days = stock_duration_days
        existing.updated_at = datetime.now(UTC)
        session.add(existing)
    else:
        session.add(LocationPlan(location=location, participants=participants, stock_duration_days=stock_duration_days))
    session.commit()


def _telegram_operation_message(*, operation: str, actor: str, detail: str) -> str:
    return f"[stockmgr] {operation}\nactor: {actor}\n{detail}"


def _notify_telegram_operation_sync(*, operation: str, actor: str, detail: str) -> None:
    if not telegram_service.is_enabled:
        return
    try:
        telegram_service.send_message_sync(
            text=_telegram_operation_message(operation=operation, actor=actor, detail=detail)
        )
    except TelegramDeliveryError as exc:
        logger.warning("Telegram operation notification failed: %s", exc)
    except TelegramConfigError as exc:
        logger.warning("Telegram notification skipped due to configuration error: %s", exc)


async def _notify_telegram_operation_async(*, operation: str, actor: str, detail: str) -> None:
    if not telegram_service.is_enabled:
        return
    try:
        await telegram_service.send_message(
            text=_telegram_operation_message(operation=operation, actor=actor, detail=detail)
        )
    except TelegramDeliveryError as exc:
        logger.warning("Telegram operation notification failed: %s", exc)
    except TelegramConfigError as exc:
        logger.warning("Telegram notification skipped due to configuration error: %s", exc)


def _telegram_help_message() -> str:
    return (
        "stockmgr Telegram commands:\n"
        "/help - command list\n"
        "/health - app health and deployed version\n"
        "/inventory - shared inventory summary\n"
        "/find <name> - search products by name\n"
        "/moves [N] - latest stock movements (default 5)"
    )


def _telegram_inventory_summary(session: Session) -> str:
    batch_count = int(session.exec(select(func.count()).select_from(StockItem)).one() or 0)
    product_count = int(session.exec(select(func.count(func.distinct(StockItem.name)))).one() or 0)
    total_quantity = int(
        session.exec(select(func.coalesce(func.sum(StockItem.quantity), 0))).one() or 0
    )
    today = date.today()
    renewal_cutoff = today + timedelta(days=settings.renewal_window_days)
    renewal_count = int(
        session.exec(
            select(func.count())
            .select_from(StockItem)
            .where(
                StockItem.renewal_date.is_not(None),
                StockItem.renewal_date >= today,
                StockItem.renewal_date <= renewal_cutoff,
            )
        ).one()
        or 0
    )
    return (
        "Shared inventory summary:\n"
        f"Products: {product_count}\n"
        f"Batches: {batch_count}\n"
        f"Total quantity: {total_quantity}\n"
        f"Renewals in next {settings.renewal_window_days} days: {renewal_count}"
    )


def _telegram_find_products(session: Session, query: str) -> str:
    term = query.strip().lower()
    if not term:
        return "Usage: /find <product name>"
    rows = session.exec(
        select(
            StockItem.name,
            StockItem.item_type,
            func.sum(StockItem.quantity).label("total_quantity"),
        )
        .where(func.lower(StockItem.name).like(f"%{term}%"))
        .group_by(StockItem.name, StockItem.item_type)
        .order_by(func.sum(StockItem.quantity).desc(), StockItem.name)
        .limit(5)
    ).all()
    if not rows:
        return f"No products matched '{query.strip()}'."
    lines = ["Top matches:"]
    for name, item_type, total_quantity in rows:
        lines.append(f"- {name} ({item_type}) qty={int(total_quantity or 0)}")
    return "\n".join(lines)


def _telegram_recent_moves(session: Session, requested_limit: str) -> str:
    limit = 5
    normalized = requested_limit.strip()
    if normalized:
        if not normalized.isdigit():
            return "Usage: /moves [N]"
        limit = max(1, min(int(normalized), 20))
    rows = session.exec(
        select(StockMovement, StockItem)
        .join(StockItem, StockItem.id == StockMovement.stock_item_id)
        .order_by(StockMovement.created_at.desc())
        .limit(limit)
    ).all()
    if not rows:
        return "No stock movements recorded yet."
    lines = ["Latest stock movements:"]
    for movement, item in rows:
        sign = "+" if movement.delta >= 0 else ""
        note = f" ({movement.note})" if movement.note else ""
        lines.append(
            f"- {movement.created_at.date()} {item.name} {sign}{movement.delta}{note}"
        )
    return "\n".join(lines)


def _handle_telegram_command(session: Session, text: str) -> str:
    command_line = text.strip()
    if not command_line.startswith("/"):
        return "Unknown input. Send /help to list supported commands."

    parts = command_line.split(maxsplit=1)
    command = parts[0].lower()
    argument = parts[1] if len(parts) > 1 else ""

    if command in {"/start", "/help"}:
        return _telegram_help_message()
    if command == "/health":
        return f"Health: ok\nVersion: {settings.app_version}"
    if command == "/inventory":
        return _telegram_inventory_summary(session)
    if command == "/find":
        return _telegram_find_products(session, argument)
    if command == "/moves":
        return _telegram_recent_moves(session, argument)

    return "Unsupported command. Send /help to list supported commands."


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}


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
    redirect_uri = _oauth_callback_redirect_uri(request, provider)
    return await client.authorize_redirect(request, redirect_uri)


def _oauth_callback_redirect_uri(request: Request, provider: str) -> str:
    callback_uri = str(request.url_for("oauth_callback", provider=provider))
    return _build_oauth_redirect_uri(
        callback_uri=callback_uri,
        public_base_url=settings.public_base_url,
        forwarded_proto=request.headers.get("x-forwarded-proto"),
    )


def _build_oauth_redirect_uri(
    callback_uri: str,
    public_base_url: str | None,
    forwarded_proto: str | None,
) -> str:
    parsed_callback = urlsplit(callback_uri)
    configured_base = (public_base_url or "").strip()
    if configured_base:
        if "://" not in configured_base:
            configured_base = f"https://{configured_base}"
        parsed_base = urlsplit(configured_base)
        if parsed_base.scheme and parsed_base.netloc:
            base_path = parsed_base.path.rstrip("/")
            callback_path = parsed_callback.path
            combined_path = f"{base_path}{callback_path}" if base_path else callback_path
            return urlunsplit(
                (
                    parsed_base.scheme,
                    parsed_base.netloc,
                    combined_path,
                    parsed_callback.query,
                    parsed_callback.fragment,
                )
            )

    normalized_forwarded_proto = (forwarded_proto or "").split(",")[0].strip().lower()
    if normalized_forwarded_proto == "https" and parsed_callback.scheme != "https":
        return urlunsplit(
            (
                "https",
                parsed_callback.netloc,
                parsed_callback.path,
                parsed_callback.query,
                parsed_callback.fragment,
            )
        )
    return callback_uri


def _oauth_message_from_error(error: str | None) -> str:
    normalized_error = (error or "").strip().lower()
    if normalized_error in {"access_denied", "user_cancelled"}:
        return "oauth-cancelled"
    if normalized_error:
        return "oauth-provider-error"
    return "oauth-login-failed"


@app.get("/auth/{provider}/callback")
async def oauth_callback(
    request: Request,
    provider: str,
    session: Session = Depends(get_session),
):
    client = oauth.create_client(provider)
    if not client:
        raise HTTPException(status_code=404, detail=f"OAuth provider '{provider}' is unavailable.")

    oauth_error = request.query_params.get("error")
    if oauth_error:
        message_key = _oauth_message_from_error(oauth_error)
        return RedirectResponse(f"/login?m={message_key}", status_code=303)

    token_kwargs: dict[str, Any] = {}
    if provider == "microsoft":
        # Microsoft /common may return tenant-specific issuers; accept token claims
        # without strict issuer matching and rely on subsequent Graph profile lookup.
        token_kwargs["claims_options"] = {}
    try:
        token = await client.authorize_access_token(request, **token_kwargs)
    except OAuthError as exc:
        logger.warning(
            "OAuth token exchange failed for provider %s: %s (%s)",
            provider,
            exc.error,
            exc.description,
        )
        message_key = _oauth_message_from_error(exc.error)
        return RedirectResponse(f"/login?m={message_key}", status_code=303)
    except JoseError as exc:
        logger.warning("OAuth ID token validation failed for provider %s: %s", provider, exc)
        return RedirectResponse("/login?m=oauth-provider-error", status_code=303)
    userinfo = token.get("userinfo")
    if not userinfo:
        if provider == "google":
            try:
                userinfo = await client.userinfo(token=token)
            except OAuthError as exc:
                logger.warning(
                    "OAuth userinfo lookup failed for provider %s: %s (%s)",
                    provider,
                    exc.error,
                    exc.description,
                )
                message_key = _oauth_message_from_error(exc.error)
                return RedirectResponse(f"/login?m={message_key}", status_code=303)
        elif provider == "microsoft":
            try:
                async with httpx.AsyncClient(timeout=8) as http_client:
                    graph_response = await http_client.get(
                        "https://graph.microsoft.com/v1.0/me",
                        headers={"Authorization": f"Bearer {token.get('access_token')}"},
                    )
                graph_response.raise_for_status()
                userinfo = graph_response.json()
            except httpx.HTTPError as exc:
                logger.warning("Microsoft Graph profile lookup failed: %s", exc)
                return RedirectResponse("/login?m=oauth-provider-error", status_code=303)
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
    statement = select(StockItem)
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


@app.post("/items/search")
def search_item_from_home(
    request: Request,
    query: str = Form(...),
    session: Session = Depends(get_session),
    _csrf: None = Depends(_validate_csrf),
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    search_value = query.strip()
    if not search_value:
        return RedirectResponse("/?m=search-empty", status_code=303)

    is_barcode = _looks_like_barcode(search_value)
    barcode_value = search_value.replace(" ", "").strip() if is_barcode else ""

    if is_barcode:
        barcode_match = session.exec(
            select(StockItem)
            .where(
                StockItem.barcode == barcode_value,
                StockItem.quantity > 0,
            )
            .order_by(StockItem.expiry_date, StockItem.updated_at.desc())
        ).first()
        if barcode_match:
            detail_url = (
                str(request.base_url).rstrip("/")
                + "/products/by-name/"
                + url_quote(barcode_match.item_type, safe="")
                + "/"
                + url_quote(barcode_match.name, safe="")
            )
            return RedirectResponse(detail_url, status_code=303)

        new_item_url = f"{request.url_for('item_new')}?{urlencode({'barcode': barcode_value})}"
        return RedirectResponse(new_item_url, status_code=303)

    name_match = session.exec(
        select(StockItem)
        .where(
            func.lower(StockItem.name) == search_value.lower(),
            StockItem.quantity > 0,
        )
        .order_by(StockItem.expiry_date, StockItem.updated_at.desc())
    ).first()
    if not name_match:
        name_match = session.exec(
            select(StockItem)
            .where(
                StockItem.name.like(f"%{search_value}%"),
                StockItem.quantity > 0,
            )
            .order_by(StockItem.name, StockItem.expiry_date, StockItem.updated_at.desc())
        ).first()

    if name_match:
        detail_url = (
            str(request.base_url).rstrip("/")
            + "/products/by-name/"
            + url_quote(name_match.item_type, safe="")
            + "/"
            + url_quote(name_match.name, safe="")
        )
        return RedirectResponse(detail_url, status_code=303)

    new_item_url = f"{request.url_for('item_new')}?{urlencode({'name': search_value})}"
    return RedirectResponse(new_item_url, status_code=303)


@app.get("/stock/views")
def stock_views(request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user

    plans: dict[str, LocationPlan] = {
        p.location: p for p in session.exec(select(LocationPlan)).all()
    }

    overall_query = (
        select(
            StockItem.name,
            StockItem.item_type,
            func.sum(StockItem.quantity).label("quantity"),
        )
        .group_by(StockItem.name, StockItem.item_type)
        .order_by(StockItem.name)
    )
    by_location_query = (
        select(
            StockItem.name,
            StockItem.item_type,
            StockItem.storage_location,
            StockItem.food_group,
            func.sum(StockItem.quantity).label("quantity"),
            func.sum(StockItem.quantity * StockItem.unidose_per_pack).label("total_unidoses"),
            func.max(StockItem.target_unidoses_location).label("target_unidoses"),
        )
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
        .group_by(
            StockItem.name,
            StockItem.item_type,
            StockItem.storage_location,
            StockItem.expiry_date,
        )
        .order_by(StockItem.name, StockItem.storage_location, StockItem.expiry_date)
    )

    # Enrich location_rows with plan-based target
    raw_location = session.exec(by_location_query).all()
    location_rows = []
    for row in raw_location:
        name, item_type, location, food_group, qty, total_u, target_u = row
        plan = plans.get(location)
        if plan and food_group:
            fg = FOOD_GROUP_BY_KEY.get(food_group)
            plan_target = (
                math.ceil(plan.total_meal_occasions * fg.target_pct / 100) if fg
                else plan.total_meal_occasions
            )
        elif plan:
            plan_target = plan.total_meal_occasions
        else:
            plan_target = None
        effective_target = plan_target if plan_target is not None else int(target_u or 0)
        location_rows.append({
            "name": name,
            "item_type": item_type,
            "location": location,
            "quantity": qty,
            "total_unidoses": int(total_u or 0),
            "target_unidoses": effective_target,
            "plan_target": plan_target,
            "delta_unidoses": (effective_target - int(total_u or 0)) if effective_target else None,
        })

    return _render(
        request,
        "stock_views.html",
        {
            "user": user,
            "overall_rows": session.exec(overall_query).all(),
            "location_rows": location_rows,
            "validity_rows": session.exec(by_location_expiry_query).all(),
        },
    )


@app.get("/shopping-list")
def shopping_list(request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user

    # Load location plans for plan-based target computation
    plans: dict[str, LocationPlan] = {
        p.location: p for p in session.exec(select(LocationPlan)).all()
    }

    location_rows = session.exec(
        select(
            StockItem.name,
            StockItem.item_type,
            StockItem.storage_location,
            StockItem.food_group,
            func.sum(StockItem.quantity * StockItem.unidose_per_pack).label("total_unidoses"),
            func.max(StockItem.target_unidoses_location).label("target_unidoses"),
            func.max(StockItem.unidose_per_pack).label("unidose_per_pack"),
        )
        .group_by(StockItem.name, StockItem.item_type, StockItem.storage_location)
        .order_by(StockItem.name, StockItem.storage_location)
    ).all()

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in location_rows:
        name, item_type, location, food_group, total_u, target_u, per_pack = row
        total_unidoses = int(total_u or 0)
        per_pack_value = max(1, int(per_pack or 1))

        # Prefer plan-based target if a plan exists for this location
        plan = plans.get(location)
        if plan and food_group:
            fg = FOOD_GROUP_BY_KEY.get(food_group)
            effective_target = (
                math.ceil(plan.total_meal_occasions * fg.target_pct / 100) if fg
                else plan.total_meal_occasions
            )
        else:
            effective_target = int(target_u or 0)

        delta_unidoses = max(effective_target - total_unidoses, 0)
        qty_to_buy = math.ceil(delta_unidoses / per_pack_value) if delta_unidoses else 0
        key = (name, item_type)
        if key not in grouped:
            fg_obj = FOOD_GROUP_BY_KEY.get(food_group) if food_group else None
            grouped[key] = {
                "name": name,
                "item_type": item_type,
                "food_group": food_group,
                "food_group_color": fg_obj.color if fg_obj else None,
                "total_quantity_to_buy": 0,
                "distribution": [],
            }
        grouped[key]["total_quantity_to_buy"] += qty_to_buy
        if qty_to_buy > 0:
            grouped[key]["distribution"].append(f"{location}: {qty_to_buy}")

    rows = [value for value in grouped.values() if value["total_quantity_to_buy"] > 0]
    rows.sort(key=lambda item: (item["name"], item["item_type"]))
    return _render(request, "shopping_list.html", {"user": user, "rows": rows})


# ── Location plans ──────────────────────────────────────────────────────────


@app.get("/location-plans")
def location_plans_list(request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    plans = session.exec(select(LocationPlan).order_by(LocationPlan.location)).all()
    return _render(
        request,
        "location_plans.html",
        {
            "user": maybe_user,
            "plans": plans,
            "edit_plan": None,
            "message": _fetch_message(request),
        },
    )


@app.post("/location-plans")
async def location_plans_create(
    request: Request,
    session: Session = Depends(get_session),
    _csrf: None = Depends(_validate_csrf),
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    form = await request.form()
    try:
        plan_in = LocationPlanCreate(
            location=str(form.get("location") or ""),
            participants=int(form.get("participants") or 1),
            stock_duration_days=int(form.get("stock_duration_days") or 1),
        )
    except (ValueError, Exception) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    existing = session.exec(
        select(LocationPlan).where(LocationPlan.location == plan_in.location)
    ).first()
    if existing:
        existing.participants = plan_in.participants
        existing.stock_duration_days = plan_in.stock_duration_days
        existing.updated_at = datetime.now(UTC)
        session.add(existing)
    else:
        session.add(LocationPlan(**plan_in.model_dump()))
    session.commit()
    return RedirectResponse("/location-plans?m=location-plan-saved", status_code=303)


@app.get("/location-plans/{plan_id}/edit")
def location_plans_edit(
    plan_id: int, request: Request, session: Session = Depends(get_session)
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    plan = session.get(LocationPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Location plan not found.")
    all_plans = session.exec(select(LocationPlan).order_by(LocationPlan.location)).all()
    return _render(
        request,
        "location_plans.html",
        {"user": maybe_user, "plans": all_plans, "edit_plan": plan, "message": None},
    )


@app.post("/location-plans/{plan_id}/update")
async def location_plans_update(
    plan_id: int,
    request: Request,
    session: Session = Depends(get_session),
    _csrf: None = Depends(_validate_csrf),
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    plan = session.get(LocationPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Location plan not found.")
    form = await request.form()
    try:
        plan_in = LocationPlanCreate(
            location=str(form.get("location") or ""),
            participants=int(form.get("participants") or 1),
            stock_duration_days=int(form.get("stock_duration_days") or 1),
        )
    except (ValueError, Exception) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    plan.location = plan_in.location
    plan.participants = plan_in.participants
    plan.stock_duration_days = plan_in.stock_duration_days
    plan.updated_at = datetime.now(UTC)
    session.add(plan)
    session.commit()
    return RedirectResponse("/location-plans?m=location-plan-saved", status_code=303)


@app.post("/location-plans/{plan_id}/delete")
async def location_plans_delete(
    plan_id: int,
    request: Request,
    session: Session = Depends(get_session),
    _csrf: None = Depends(_validate_csrf),
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    plan = session.get(LocationPlan, plan_id)
    if plan:
        session.delete(plan)
        session.commit()
    return RedirectResponse("/location-plans?m=location-plan-deleted", status_code=303)


@app.get("/device-check")
def device_check(request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    return _render(request, "device_check.html", {"user": maybe_user})


@app.get("/food-wheel")
def food_wheel_page(
    request: Request,
    location: str | None = None,
    session: Session = Depends(get_session),
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user

    # All locations for filter dropdown (unfiltered)
    all_location_rows = session.exec(
        select(StockItem.storage_location).distinct()
    ).all()
    all_locations: list[str] = sorted(loc for loc in all_location_rows if loc)

    query = select(
        StockItem.food_group,
        StockItem.storage_location,
        StockItem.quantity,
        StockItem.unidose_per_pack,
    )
    if location:
        query = query.where(StockItem.storage_location == location)
    all_rows = session.exec(query).all()

    items_for_chart = [
        {"food_group": row[0], "quantity": row[2], "unidose_per_pack": row[3]}
        for row in all_rows
    ]
    lang = request.session.get("language", "pt")
    chart = food_group_chart_data(items_for_chart, language=lang)

    # Normalize group_stats keys for template
    chart_data = [
        {
            "label": g["label"],
            "color": g["color"],
            "unidoses": int(g["actual_unidoses"]),
            "actual_pct": g["actual_pct"],
            "target_pct": g["target_pct"],
            "delta": g["delta_pct"],
        }
        for g in chart["group_stats"]
    ]
    ungrouped_count = sum(
        1 for item in items_for_chart if not item["food_group"]
    )

    return _render(
        request,
        "food_wheel.html",
        {
            "user": user,
            "chart_data": chart_data if chart["total_unidoses"] > 0 else [],
            "chart_json": json.dumps(chart_data),
            "ungrouped_count": ungrouped_count,
            "all_locations": all_locations,
            "selected_location": location or "",
        },
    )


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


@app.get("/products/by-name/{item_type}/{product_name:path}")
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

    batches = _product_batches(
        session,
        item_type=item_type,
        product_name=product_name,
    )
    if not batches:
        raise HTTPException(status_code=404, detail="Product not found.")

    primary_batch = batches[0]
    product_summary = {
        "barcode": primary_batch.barcode,
        "temp_min_c": primary_batch.temp_min_c,
        "temp_max_c": primary_batch.temp_max_c,
        "humidity_min_pct": primary_batch.humidity_min_pct,
        "humidity_max_pct": primary_batch.humidity_max_pct,
        "renewal_date": primary_batch.renewal_date,
        "image_url": primary_batch.image_url,
        "nutriscore": primary_batch.nutriscore,
        "batch_count": len(batches),
        "total_quantity": sum(batch.quantity for batch in batches),
        "total_unidoses": sum(batch.quantity * batch.unidose_per_pack for batch in batches),
    }
    location_options = sorted(
        {batch.storage_location for batch in batches if batch.storage_location}
    )

    movement_query = (
        select(StockMovement, StockItem)
        .join(StockItem, StockItem.id == StockMovement.stock_item_id)
        .where(
            StockItem.item_type == item_type,
            StockItem.name == product_name,
        )
        .order_by(StockMovement.created_at.desc())
    )
    movement_rows = session.exec(movement_query).all()

    # Build per-location plan info map
    location_plans: dict[str, dict] = {}
    for loc in location_options:
        plan = session.exec(select(LocationPlan).where(LocationPlan.location == loc)).first()
        if plan:
            location_plans[loc] = {
                "participants": plan.participants,
                "days": plan.days,
                "total_meal_occasions": plan.total_meal_occasions,
            }

    return _render(
        request,
        "product_detail.html",
        {
            "user": user,
            "item_type": item_type,
            "product_name": product_name,
            "edit_item_id": primary_batch.id,
            "product_summary": product_summary,
            "location_options": location_options,
            "batches": batches,
            "movement_rows": movement_rows,
            "location_plans": location_plans,
            "message": _fetch_message(request),
        },
    )


@app.get("/items/new")
def item_new(request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    prefill_name = request.query_params.get("name", "").strip()
    prefill_barcode = request.query_params.get("barcode", "").replace(" ", "").strip()
    prefill_item_type = request.query_params.get("item_type", "").strip()
    prefill_location = request.query_params.get("storage_location", "").strip()
    prefill_bucket = request.query_params.get("storage_bucket", "").strip()
    plans_map = {p.location: p.total_meal_occasions for p in session.exec(select(LocationPlan)).all()}
    return _render(
        request,
        "item_form.html",
        {
            "user": maybe_user,
            "mode": "create",
            "draft": {
                "name": prefill_name,
                "item_type": prefill_item_type or "unknown",
                "barcode": prefill_barcode,
                "storage_location": prefill_location,
                "storage_bucket": prefill_bucket,
                "quantity": 0,
                "unidose_per_pack": 1,
                "target_unidoses_location": 0,
            },
            "lookup": None,
            "food_groups": FOOD_GROUPS,
            "plan_locations": _plan_locations(session),
            "location_plans_json": json.dumps(plans_map),
        },
    )


@app.get("/items/{item_id}/edit")
def item_edit(item_id: int, request: Request, session: Session = Depends(get_session)):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user
    item = session.get(StockItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")
    all_batches = _product_batches(
        session,
        item_type=item.item_type,
        product_name=item.name,
    )
    plans_map = {p.location: p.total_meal_occasions for p in session.exec(select(LocationPlan)).all()}
    return _render(
        request,
        "item_form.html",
        {
            "user": user,
            "mode": "edit",
            "draft": item,
            "lookup": None,
            "all_batches": all_batches,
            "food_groups": FOOD_GROUPS,
            "plan_locations": _plan_locations(session),
            "location_plans_json": json.dumps(plans_map),
        },
    )


@app.post("/items/lookup")
async def lookup_for_form(
    request: Request,
    barcode: str = Form(...),
    item_type: str = Form("unknown"),
    session: Session = Depends(get_session),
    _csrf: None = Depends(_validate_csrf),
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    result = await barcode_service.lookup(barcode=barcode, item_type=item_type)
    draft: dict[str, Any] = {"barcode": barcode, "item_type": item_type, "quantity": 0}
    if result.found and result.data:
        inferred_group = infer_food_group(
            name=result.data.get("name") or "",
            item_type=item_type if item_type != "unknown" else result.data.get("category") or "",
            food_groups_tags=result.data.get("foodGroupsTags"),
        )
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
                "image_url": result.data.get("imageUrl"),
                "nutriscore": result.data.get("nutriscore"),
                "food_group": inferred_group,
                **dict(zip(("weight_capacity", "uom"), _parse_size(result.data.get("size")))),
            }
        )
    location_context = _storage_location_field_context(
        session,
        selected_location=str(draft.get("storage_location") or ""),
    )
    plans_map = {p.location: p.total_meal_occasions for p in session.exec(select(LocationPlan)).all()}
    return _render(
        request,
        "item_form.html",
        {
            "user": maybe_user,
            "mode": "create",
            "draft": draft,
            "lookup": result,
            "food_groups": FOOD_GROUPS,
            "plan_locations": _plan_locations(session),
            "location_plans_json": json.dumps(plans_map),
            **location_context,
        },
    )


@app.post("/items")
async def item_create(
    request: Request,
    session: Session = Depends(get_session),
    _csrf: None = Depends(_validate_csrf),
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user
    form = await request.form()

    # Multi-location create: loc_location[] submitted per row
    loc_locations = form.getlist("loc_location")
    if loc_locations:
        # Filter to non-empty location rows
        loc_batch_codes = form.getlist("loc_batch_code")
        loc_expiries = form.getlist("loc_expiry")
        loc_quantities = form.getlist("loc_quantity")
        loc_buckets = form.getlist("loc_bucket")
        loc_renewals = form.getlist("loc_renewal")
        loc_targets = form.getlist("loc_target")

        base_payload = _item_payload_from_form(dict(form))
        if not base_payload.get("food_group"):
            base_payload["food_group"] = infer_food_group(
                name=base_payload.get("name") or "",
                item_type=base_payload.get("item_type") or "",
            )

        created_items: list[StockItem] = []
        for idx, loc in enumerate(loc_locations):
            loc = loc.strip()
            if not loc:
                continue
            expiry = loc_expiries[idx] if idx < len(loc_expiries) else ""
            if not expiry:
                continue
            row = dict(base_payload)
            row["storage_location"] = loc
            row["batch_code"] = (loc_batch_codes[idx] if idx < len(loc_batch_codes) else None) or None
            row["expiry_date"] = expiry
            row["quantity"] = int(loc_quantities[idx] or 0) if idx < len(loc_quantities) else 0
            row["storage_bucket"] = loc_buckets[idx] if idx < len(loc_buckets) else ""
            renewal_raw = loc_renewals[idx] if idx < len(loc_renewals) else ""
            row["renewal_date"] = renewal_raw if renewal_raw else None
            target_raw = loc_targets[idx] if idx < len(loc_targets) else 0
            row["target_unidoses_location"] = int(target_raw or 0)
            if not row["target_unidoses_location"]:
                plan = session.exec(select(LocationPlan).where(LocationPlan.location == loc)).first()
                if plan and row.get("food_group"):
                    fg = FOOD_GROUP_BY_KEY.get(row["food_group"])
                    if fg:
                        row["target_unidoses_location"] = math.ceil(
                            plan.total_meal_occasions * fg.target_pct / 100
                        )
            try:
                item_in = ItemCreate.model_validate(row)
            except ValidationError as exc:
                raise HTTPException(status_code=422, detail=exc.errors()) from exc
            item = StockItem(**item_in.model_dump(), user_id=user.id)
            session.add(item)
            session.commit()
            session.refresh(item)
            created_items.append(item)
            if item.quantity > 0:
                session.add(StockMovement(
                    stock_item_id=item.id,
                    user_id=user.id,
                    delta=item.quantity,
                    note="Initial stock quantity",
                ))
                session.commit()
            try:
                await calendar_service.schedule_renewal(user=user, item=item)
            except CalendarSyncError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
        names = ", ".join(i.storage_location for i in created_items)
        await _notify_telegram_operation_async(
            operation="item-created",
            actor=user.email,
            detail=(
                f"name={base_payload.get('name')} type={base_payload.get('item_type')} "
                f"locations={names}"
            ),
        )
        # Auto-create location plans for any new locations submitted (#53)
        new_plan_locs = form.getlist("new_plan_location")
        new_plan_parts = form.getlist("new_plan_participants")
        new_plan_days = form.getlist("new_plan_days")
        for i, plan_loc in enumerate(new_plan_locs):
            plan_loc = plan_loc.strip()
            if not plan_loc:
                continue
            try:
                parts = int(new_plan_parts[i]) if i < len(new_plan_parts) else 4
                days = int(new_plan_days[i]) if i < len(new_plan_days) else 30
                _upsert_location_plan(session, location=plan_loc, participants=parts, stock_duration_days=days)
            except (ValueError, IndexError):
                pass
        if form.get("continue_adding"):
            return RedirectResponse("/items/new?m=item-created", status_code=303)
        return RedirectResponse("/?m=item-created", status_code=303)

    # Legacy single-row path
    payload = _item_payload_from_form(dict(form))
    # Auto-infer food_group from name/type if not set
    if not payload.get("food_group"):
        payload["food_group"] = infer_food_group(
            name=payload.get("name") or "",
            item_type=payload.get("item_type") or "",
        )
    # Auto-compute target_unidoses_location from location plan if not set
    if not payload.get("target_unidoses_location"):
        loc = payload.get("storage_location") or ""
        plan = session.exec(select(LocationPlan).where(LocationPlan.location == loc)).first()
        if plan and payload.get("food_group"):
            fg = FOOD_GROUP_BY_KEY.get(payload["food_group"])
            if fg:
                payload["target_unidoses_location"] = math.ceil(
                    plan.total_meal_occasions * fg.target_pct / 100
                )
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
    await _notify_telegram_operation_async(
        operation="item-created",
        actor=user.email,
        detail=(
            f"name={item.name} type={item.item_type} qty={item.quantity} "
            f"location={item.storage_location}"
        ),
    )

    if form.get("new_plan_location"):
        try:
            _upsert_location_plan(
                session,
                location=str(form.get("new_plan_location")),
                participants=int(form.get("new_plan_participants") or 4),
                stock_duration_days=int(form.get("new_plan_days") or 30),
            )
        except (ValueError, Exception):
            pass

    if form.get("continue_adding"):
        return RedirectResponse("/items/new?m=item-created", status_code=303)
    return RedirectResponse("/?m=item-created", status_code=303)


@app.post("/items/{item_id}/update")
async def item_update(
    item_id: int,
    request: Request,
    session: Session = Depends(get_session),
    _csrf: None = Depends(_validate_csrf),
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user
    item = session.get(StockItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")

    form = await request.form()

    # ── Multi-row edit path ──────────────────────────────────────────────
    row_ids = form.getlist("row_id")
    if row_ids is not None and len(row_ids) > 0:
        # Product-level fields (shared across all batches)
        product_payload = _item_payload_from_form(dict(form))
        if not product_payload.get("food_group"):
            product_payload["food_group"] = infer_food_group(
                name=product_payload.get("name") or "",
                item_type=product_payload.get("item_type") or "",
            )

        # Delete marked batches (safety: only delete batches for this product)
        delete_ids_raw = form.getlist("delete_ids")
        for raw_id in delete_ids_raw:
            try:
                del_id = int(raw_id)
            except (ValueError, TypeError):
                continue
            del_item = session.get(StockItem, del_id)
            if del_item and del_item.name == item.name and del_item.item_type == item.item_type:
                session.delete(del_item)
        session.commit()

        row_locations = form.getlist("row_location")
        row_batch_codes = form.getlist("row_batch_code")
        row_expiries = form.getlist("row_expiry")
        row_quantities = form.getlist("row_quantity")
        row_buckets = form.getlist("row_bucket")
        row_targets = form.getlist("row_target")
        row_renewals = form.getlist("row_renewal")

        for idx, raw_row_id in enumerate(row_ids):
            loc = (row_locations[idx] if idx < len(row_locations) else "").strip()
            if not loc:
                continue
            expiry = row_expiries[idx] if idx < len(row_expiries) else ""
            if not expiry:
                continue

            row = dict(product_payload)
            row["storage_location"] = loc
            row["batch_code"] = (row_batch_codes[idx] if idx < len(row_batch_codes) else None) or None
            row["expiry_date"] = expiry
            row["quantity"] = int(row_quantities[idx] or 0) if idx < len(row_quantities) else 0
            row["storage_bucket"] = row_buckets[idx] if idx < len(row_buckets) else ""
            renewal_raw = row_renewals[idx] if idx < len(row_renewals) else ""
            row["renewal_date"] = renewal_raw if renewal_raw else None
            target_raw = row_targets[idx] if idx < len(row_targets) else 0
            row["target_unidoses_location"] = int(target_raw or 0)
            if not row["target_unidoses_location"]:
                plan = session.exec(select(LocationPlan).where(LocationPlan.location == loc)).first()
                if plan and row.get("food_group"):
                    fg = FOOD_GROUP_BY_KEY.get(row["food_group"])
                    if fg:
                        row["target_unidoses_location"] = math.ceil(
                            plan.total_meal_occasions * fg.target_pct / 100
                        )

            try:
                item_in = ItemCreate.model_validate(row)
            except ValidationError as exc:
                raise HTTPException(status_code=422, detail=exc.errors()) from exc

            raw_row_id = raw_row_id.strip()
            if raw_row_id:
                existing = session.get(StockItem, int(raw_row_id))
                if existing and existing.name == item.name and existing.item_type == item.item_type:
                    previous_qty = existing.quantity
                    for key, value in item_in.model_dump().items():
                        setattr(existing, key, value)
                    existing.updated_at = datetime.now(UTC)
                    session.add(existing)
                    session.commit()
                    session.refresh(existing)
                    qty_delta = existing.quantity - previous_qty
                    if qty_delta:
                        session.add(StockMovement(
                            stock_item_id=existing.id,
                            user_id=user.id,
                            delta=qty_delta,
                            note="Quantity updated in edit form",
                        ))
                    try:
                        await calendar_service.schedule_renewal(user=user, item=existing)
                    except CalendarSyncError as exc:
                        raise HTTPException(status_code=502, detail=str(exc)) from exc
            else:
                new_item = StockItem(**item_in.model_dump(), user_id=user.id)
                session.add(new_item)
                session.commit()
                session.refresh(new_item)
                if new_item.quantity > 0:
                    session.add(StockMovement(
                        stock_item_id=new_item.id,
                        user_id=user.id,
                        delta=new_item.quantity,
                        note="Initial stock quantity",
                    ))
                try:
                    await calendar_service.schedule_renewal(user=user, item=new_item)
                except CalendarSyncError as exc:
                    raise HTTPException(status_code=502, detail=str(exc)) from exc

        session.commit()
        await _notify_telegram_operation_async(
            operation="item-updated",
            actor=user.email,
            detail=f"name={item.name} type={item.item_type} rows={len(row_ids)}",
        )
        product_name_enc = item.name.replace(" ", "%20")
        return RedirectResponse(
            f"/products/by-name/{item.item_type}/{product_name_enc}?m=item-updated",
            status_code=303,
        )

    # ── Legacy single-field path (API / backward-compat) ────────────────
    previous_quantity = item.quantity
    payload = _item_payload_from_form(dict(form))
    if not payload.get("food_group"):
        payload["food_group"] = infer_food_group(
            name=payload.get("name") or "",
            item_type=payload.get("item_type") or "",
        )
    if not payload.get("target_unidoses_location"):
        loc = payload.get("storage_location") or ""
        plan = session.exec(select(LocationPlan).where(LocationPlan.location == loc)).first()
        if plan and payload.get("food_group"):
            fg = FOOD_GROUP_BY_KEY.get(payload["food_group"])
            if fg:
                payload["target_unidoses_location"] = math.ceil(
                    plan.total_meal_occasions * fg.target_pct / 100
                )
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
    await _notify_telegram_operation_async(
        operation="item-updated",
        actor=user.email,
        detail=(
            f"name={item.name} type={item.item_type} qty={item.quantity} "
            f"delta={quantity_delta} location={item.storage_location}"
        ),
    )

    return RedirectResponse("/?m=item-updated", status_code=303)


@app.post("/items/{item_id}/move")
def adjust_stock_quantity(
    item_id: int,
    request: Request,
    direction: str = Form(...),
    quantity_step: int = Form(1),
    note: str = Form(""),
    session: Session = Depends(get_session),
    _csrf: None = Depends(_validate_csrf),
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user
    item = session.get(StockItem, item_id)
    if not item:
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
    _notify_telegram_operation_sync(
        operation="stock-move",
        actor=user.email,
        detail=(
            f"name={item.name} type={item.item_type} delta={delta} "
            f"new_qty={item.quantity} note={(note or '').strip() or '-'}"
        ),
    )

    target = request.headers.get("referer") or "/"
    return RedirectResponse(target, status_code=303)


@app.post("/items/{item_id}/delete")
def item_delete(
    item_id: int,
    request: Request,
    session: Session = Depends(get_session),
    _csrf: None = Depends(_validate_csrf),
):
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user
    user = maybe_user
    item = session.get(StockItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")
    deleted_name = item.name
    deleted_type = item.item_type
    deleted_location = item.storage_location
    session.delete(item)
    session.commit()
    _notify_telegram_operation_sync(
        operation="item-deleted",
        actor=user.email,
        detail=f"name={deleted_name} type={deleted_type} location={deleted_location}",
    )
    return RedirectResponse("/?m=item-deleted", status_code=303)



@app.get("/items/export")
def export_items(request: Request, session: Session = Depends(get_session)):
    """Export all stock items to XLSX in import-compatible format."""
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user

    from io import BytesIO
    from openpyxl import Workbook

    items = session.exec(select(StockItem).order_by(StockItem.name, StockItem.storage_location)).all()

    columns = [
        ("barcode", "barcode"),
        ("batch_code", "batch_code"),
        ("name", "name"),
        ("item_type", "item_type"),
        ("storage_location", "storage_location"),
        ("storage_bucket", "storage_bucket"),
        ("expiry_date", "expiry_date"),
        ("quantity", "quantity"),
        ("unidose_per_pack", "unidose_per_pack"),
        ("target_unidoses_location", "target_unidoses_location"),
        ("weight_capacity", "weight_capacity"),
        ("uom", "uom"),
        ("temp_min_c", "temp_min_c"),
        ("temp_max_c", "temp_max_c"),
        ("humidity_min_pct", "humidity_min_pct"),
        ("humidity_max_pct", "humidity_max_pct"),
        ("renewal_date", "renewal_date"),
        ("comment", "comment"),
    ]

    wb = Workbook()
    ws = wb.active
    ws.title = "Stock"
    ws.append([col[0] for col in columns])
    for item in items:
        ws.append([getattr(item, col[1], None) for col in columns])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    from fastapi.responses import Response
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=stockmgr-export.xlsx"},
    )


@app.post("/items/{item_id}/upload-image")
async def upload_item_image(
    item_id: int,
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _csrf: None = Depends(_validate_csrf),
):
    """Upload a product image for a stock item."""
    maybe_user = _require_user_or_redirect(request, session)
    if isinstance(maybe_user, RedirectResponse):
        return maybe_user

    item = session.get(StockItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")

    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=422, detail="Only JPEG, PNG, WebP and GIF images are allowed.")

    suffix = Path(file.filename or "image.jpg").suffix.lower() or ".jpg"
    filename = f"item_{item_id}_{secrets.token_hex(8)}{suffix}"
    dest = _MEDIA_DIR / filename
    dest.write_bytes(await file.read())

    item.image_url = f"/media/{filename}"
    item.updated_at = datetime.now(UTC)
    session.add(item)
    session.commit()
    return RedirectResponse(f"/items/{item_id}/edit?m=image-updated", status_code=303)


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
    _csrf: None = Depends(_validate_csrf),
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
    await _notify_telegram_operation_async(
        operation="items-imported",
        actor=user.email,
        detail=f"imported={result.imported} failed={result.failed}",
    )
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
        {
            "user": admin,
            "users": users,
            "message": _fetch_message(request),
            "enriched_count": request.query_params.get("enriched"),
        },
    )


@app.post("/admin/users/{user_id}/approve")
def admin_approve_user(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(_require_admin_user),
    _csrf: None = Depends(_validate_csrf),
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
    _csrf: None = Depends(_validate_csrf),
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
    _csrf: None = Depends(_validate_csrf),
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



@app.get("/admin/enrich")
def admin_enrich_page(
    request: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(_require_admin_user),
):
    _ = session
    return _render(
        request,
        "enrich.html",
        {
            "user": admin,
            "message": _fetch_message(request),
            "enriched_count": request.query_params.get("enriched"),
        },
    )


@app.post("/admin/enrich-items")
async def admin_enrich_items(
    request: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(_require_admin_user),
    _csrf: None = Depends(_validate_csrf),
):
    """Re-query barcode providers for all items missing image_url or nutriscore."""
    _ = request
    items_with_barcode = session.exec(
        select(StockItem).where(
            StockItem.barcode.is_not(None),  # type: ignore[union-attr]
            StockItem.barcode != "",
        )
    ).all()
    enriched = 0
    for item in items_with_barcode:
        if item.image_url and item.nutriscore and item.food_group:
            continue
        try:
            result = await barcode_service.lookup(
                barcode=item.barcode, item_type=item.item_type
            )
        except Exception:
            continue
        if not result.found or not result.data:
            continue
        changed = False
        if not item.image_url and result.data.get("imageUrl"):
            item.image_url = result.data["imageUrl"]
            changed = True
        if not item.nutriscore and result.data.get("nutriscore"):
            item.nutriscore = result.data["nutriscore"]
            changed = True
        if not item.food_group:
            inferred = infer_food_group(
                name=result.data.get("name") or item.name,
                item_type=item.item_type,
                food_groups_tags=result.data.get("foodGroupsTags"),
            )
            if inferred:
                item.food_group = inferred
                changed = True
        if not item.weight_capacity and result.data.get("size"):
            wc, u = _parse_size(result.data.get("size"))
            if wc is not None:
                item.weight_capacity = wc
                item.uom = u
                changed = True
        if changed:
            item.updated_at = datetime.now(UTC)
            session.add(item)
            enriched += 1
    session.commit()
    return RedirectResponse(f"/admin/enrich?m=enrich-done&enriched={enriched}", status_code=303)


@app.get("/api/items", response_model=list[ItemRead])
def api_list_items(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(_require_api_user),
):
    _ = request, user
    items = session.exec(select(StockItem)).all()
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
    await _notify_telegram_operation_async(
        operation="api-item-created",
        actor=user.email,
        detail=(
            f"name={item.name} type={item.item_type} qty={item.quantity} "
            f"location={item.storage_location}"
        ),
    )
    return _to_read_model(item)


@app.get("/api/excel/stocks", response_model=list[ItemRead])
def api_excel_list_stocks(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(_require_excel_api_user),
):
    _ = request, user
    items = session.exec(
        select(StockItem)
        .order_by(StockItem.name, StockItem.storage_location, StockItem.expiry_date)
    ).all()
    return [_to_read_model(item) for item in items]


@app.put("/api/excel/stocks/{item_id}", response_model=ItemRead)
async def api_excel_update_stock(
    item_id: int,
    item_in: ItemCreate,
    session: Session = Depends(get_session),
    user: User = Depends(_require_excel_api_user),
):
    item = session.get(StockItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Stock item not found.")

    previous_quantity = item.quantity
    _apply_item_create_to_stock(item, item_in)
    session.add(item)
    quantity_delta = item.quantity - previous_quantity
    if quantity_delta:
        session.add(
            StockMovement(
                stock_item_id=item.id,
                user_id=user.id,
                delta=quantity_delta,
                note="Quantity updated via Excel API",
            )
        )
    session.commit()
    session.refresh(item)
    try:
        await calendar_service.schedule_renewal(user=user, item=item)
    except CalendarSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await _notify_telegram_operation_async(
        operation="excel-item-updated",
        actor=user.email,
        detail=(
            f"id={item.id} name={item.name} qty={item.quantity} "
            f"delta={quantity_delta} location={item.storage_location}"
        ),
    )
    return _to_read_model(item)


@app.post("/api/excel/stocks/upsert")
async def api_excel_upsert_stocks(
    payload: ExcelStockUpsertRequest,
    session: Session = Depends(get_session),
    user: User = Depends(_require_excel_api_user),
):
    created = 0
    updated = 0
    rows: list[ItemRead] = []

    for row in payload.rows:
        item_in = ItemCreate.model_validate(row.model_dump(exclude={"id"}))
        item = None
        if row.id is not None:
            item = session.get(StockItem, row.id)
            if not item:
                raise HTTPException(
                    status_code=404,
                    detail=f"Stock item not found for id={row.id}.",
                )
        else:
            item = _excel_match_existing_item(session, row=row)

        if item:
            previous_quantity = item.quantity
            _apply_item_create_to_stock(item, item_in)
            session.add(item)
            quantity_delta = item.quantity - previous_quantity
            if quantity_delta:
                session.add(
                    StockMovement(
                        stock_item_id=item.id,
                        user_id=user.id,
                        delta=quantity_delta,
                        note="Quantity updated via Excel API upsert",
                    )
                )
            updated += 1
        else:
            item = StockItem(**item_in.model_dump(), user_id=user.id)
            session.add(item)
            session.flush()
            if item.quantity > 0:
                session.add(
                    StockMovement(
                        stock_item_id=item.id,
                        user_id=user.id,
                        delta=item.quantity,
                        note="Initial stock quantity (Excel API)",
                    )
                )
            created += 1

        session.commit()
        session.refresh(item)
        try:
            await calendar_service.schedule_renewal(user=user, item=item)
        except CalendarSyncError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        await _notify_telegram_operation_async(
            operation="excel-upsert-row",
            actor=user.email,
            detail=(
                f"id={item.id} name={item.name} qty={item.quantity} "
                f"location={item.storage_location}"
            ),
        )
        rows.append(_to_read_model(item))

    return {"created": created, "updated": updated, "rows": rows}


@app.post("/api/barcode-lookup", response_model=BarcodeLookupResult)
async def api_barcode_lookup(
    payload: BarcodeLookupRequest,
    user: User = Depends(_require_api_user),
):
    _ = user
    return await barcode_service.lookup(payload.barcode, payload.item_type)


@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request, session: Session = Depends(get_session)):
    if not telegram_service.is_enabled:
        raise HTTPException(status_code=503, detail="Telegram integration is not configured.")

    secret_token = request.headers.get("x-telegram-bot-api-secret-token")
    payload = await request.json()
    try:
        update = TelegramUpdate.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    message = update.message or update.edited_message
    if not message or not message.text:
        return {"ok": True, "ignored": "unsupported-update"}

    try:
        incoming = telegram_service.parse_incoming(
            text=message.text,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            chat_type=message.chat.type,
            provided_secret=secret_token,
        )
    except TelegramConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TelegramSecurityError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    command_output = _handle_telegram_command(session, incoming.text)
    try:
        await telegram_service.send_message(text=command_output, chat_id=incoming.chat_id)
    except TelegramConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TelegramDeliveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True}


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
