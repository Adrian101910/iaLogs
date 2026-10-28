import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from app.body_limit import BodyLimitMiddleware
from app.config import Settings
from app.models import Analysis, LogEvent
from app.ollama import PROMPT_VERSION, OllamaService
from app.schemas import AnalysisInput, AnalysisOut, AnalysisPage, LogBatch, LogOut, LogPage, normalize_severity


def create_app(settings: Settings | None = None, ollama_transport=None) -> FastAPI:
    settings = settings or Settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=5, connect_args={"connect_timeout": 5}, echo=False)
    sessions = sessionmaker(engine, expire_on_commit=False)
    ollama = OllamaService(settings, ollama_transport)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title="iaLogs", version="0.1.0", lifespan=lifespan)
    app.state.engine = engine
    app.state.settings = settings
    app.state.ollama = ollama
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_request_bytes)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        # Pydantic's default errors include input values, potentially credentials
        # or sensitive logs. Do not echo them in HTTP responses or application logs.
        return JSONResponse(status_code=422, content={"detail": [{"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]} for item in error.errors()]})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError):
        return JSONResponse(status_code=503, content={"detail": "PostgreSQL no está disponible o no se pudo completar la operación"})

    def authenticated(x_api_key: Annotated[str | None, Header()] = None):
        if x_api_key is None or not secrets.compare_digest(x_api_key.encode("utf-8"), settings.api_key.get_secret_value().encode("utf-8")):
            raise HTTPException(401, "API key no válida", headers={"WWW-Authenticate": "ApiKey"})

    def get_session():
        with sessions() as session:
            yield session

    db_dep = Annotated[Session, Depends(get_session)]
    auth = [Depends(authenticated)]

    @app.get("/health")
    def health(db: db_dep):
        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            raise HTTPException(503, "PostgreSQL no está disponible") from None
        return {"status": "ok", "database": "ok"}

    @app.post("/v1/logs", response_model=LogPage, status_code=201, dependencies=auth)
    def ingest(batch: LogBatch, db: db_dep):
        if len(batch.events) > settings.max_batch_events:
            raise HTTPException(422, f"El lote admite como máximo {settings.max_batch_events} eventos")
        if any(len(event.message) > settings.max_message_chars for event in batch.events):
            raise HTTPException(422, f"Los mensajes admiten como máximo {settings.max_message_chars} caracteres")
        rows = [LogEvent(**event.model_dump()) for event in batch.events]
        db.add_all(rows)
        db.commit()
        return {"items": rows, "total": len(rows)}

    @app.get("/v1/logs", response_model=LogPage, dependencies=auth)
    def logs(
        db: db_dep,
        source: str | None = Query(default=None, max_length=255),
        service: str | None = Query(default=None, max_length=255),
        severity: str | None = Query(default=None, max_length=16),
        start: AwareDatetime | None = None,
        end: AwareDatetime | None = None,
        text: str | None = Query(default=None, max_length=500),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
    ):
        if start and end and start > end:
            raise HTTPException(422, "El inicio debe ser anterior o igual al fin")
        filters = []
        for column, value in [(LogEvent.source, source), (LogEvent.service, service)]:
            if value is not None:
                filters.append(column == value)
        if severity is not None:
            normalized = normalize_severity(severity)
            if normalized not in {"TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
                raise HTTPException(422, "Severidad no válida")
            filters.append(LogEvent.severity == normalized)
        if start:
            filters.append(LogEvent.timestamp >= start)
        if end:
            filters.append(LogEvent.timestamp <= end)
        if text:
            filters.append(LogEvent.message.icontains(text, autoescape=True))
        total = db.scalar(select(func.count()).select_from(LogEvent).where(*filters))
        rows = db.scalars(select(LogEvent).where(*filters).order_by(LogEvent.timestamp.desc(), LogEvent.id.desc()).limit(limit).offset(offset)).all()
        return {"items": rows, "total": total, "limit": limit, "offset": offset}

    @app.get("/v1/logs/{log_id}", response_model=LogOut, dependencies=auth)
    def log_detail(log_id: UUID, db: db_dep):
        row = db.get(LogEvent, log_id)
        if row is None:
            raise HTTPException(404, "Evento no encontrado")
        return row

    @app.post("/v1/analyses", response_model=AnalysisOut, status_code=201, dependencies=auth)
    async def analyse(body: AnalysisInput):
        if len(body.log_ids) > settings.max_analysis_events:
            raise HTTPException(422, f"Selecciona como máximo {settings.max_analysis_events} eventos")

        def fetch_events():
            with sessions() as db:
                rows = db.scalars(select(LogEvent).where(LogEvent.id.in_(body.log_ids))).all()
                if len(rows) != len(body.log_ids):
                    raise HTTPException(404, "Uno o más eventos seleccionados no existen")
                by_id = {row.id: LogOut.model_validate(row) for row in rows}
                return [by_id[log_id] for log_id in body.log_ids]

        events = await run_in_threadpool(fetch_events)
        diagnosis = await ollama.diagnose(events)

        def save_analysis():
            with sessions() as db:
                row = Analysis(model=settings.ollama_model, prompt_version=PROMPT_VERSION, log_ids=body.log_ids, diagnosis=diagnosis.model_dump(mode="json"))
                db.add(row)
                db.commit()
                return AnalysisOut.model_validate(row)

        return await run_in_threadpool(save_analysis)

    @app.get("/v1/analyses", response_model=AnalysisPage, dependencies=auth)
    def analyses(db: db_dep, limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0, le=1_000_000)):
        total = db.scalar(select(func.count()).select_from(Analysis))
        rows = db.scalars(select(Analysis).order_by(Analysis.created_at.desc(), Analysis.id.desc()).limit(limit).offset(offset)).all()
        return {"items": rows, "total": total, "limit": limit, "offset": offset}

    @app.get("/v1/analyses/{analysis_id}", response_model=AnalysisOut, dependencies=auth)
    def analysis_detail(analysis_id: UUID, db: db_dep):
        row = db.get(Analysis, analysis_id)
        if row is None:
            raise HTTPException(404, "Análisis no encontrado")
        return row

    return app
