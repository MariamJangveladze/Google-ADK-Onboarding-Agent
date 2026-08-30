"""FastAPI demo and operational endpoints."""

import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, Request

from .config import get_settings
from .container import ApplicationContainer, build_container
from .models import (
    ActionRequest,
    BotResponse,
    ChatRequest,
    DemoStartRequest,
    HealthResponse,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.container = build_container(get_settings())
    yield


app = FastAPI(
    title="Google ADK Onboarding Agent",
    version="0.1.0",
    description="Multilingual employee onboarding workflow and Google ADK agent backend.",
    lifespan=lifespan,
)


def _container(request: Request) -> ApplicationContainer:
    return request.app.state.container


def _require_demo_token(authorization: str | None = Header(default=None)) -> None:
    expected = get_settings().demo_api_token
    if not expected:
        raise HTTPException(status_code=503, detail="Set ONBOARDING_DEMO_API_TOKEN")
    scheme, _, supplied = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid demo token")


@app.get("/health", response_model=HealthResponse, tags=["operations"])
async def health() -> HealthResponse:
    return HealthResponse(runtime_mode=get_settings().runtime_mode)


@app.post(
    "/demo/start",
    response_model=BotResponse,
    tags=["demo"],
    dependencies=[Depends(_require_demo_token)],
)
async def start(payload: DemoStartRequest, request: Request) -> BotResponse:
    return await _container(request).service.start_employee(
        payload.slack_user_id, payload.verified_email
    )


@app.post(
    "/demo/chat",
    response_model=BotResponse,
    tags=["demo"],
    dependencies=[Depends(_require_demo_token)],
)
async def chat(payload: ChatRequest, request: Request) -> BotResponse:
    settings = get_settings()
    if len(payload.message) > settings.max_message_characters:
        raise HTTPException(status_code=422, detail="Message exceeds configured length limit")
    return await _container(request).service.handle_message(
        payload.slack_user_id, payload.message.strip()
    )


@app.post(
    "/demo/done",
    response_model=BotResponse,
    tags=["demo"],
    dependencies=[Depends(_require_demo_token)],
)
async def done(payload: ActionRequest, request: Request) -> BotResponse:
    return await _container(request).service.handle_message(payload.slack_user_id, "done")


@app.post(
    "/demo/help",
    response_model=BotResponse,
    tags=["demo"],
    dependencies=[Depends(_require_demo_token)],
)
async def help_request(payload: ActionRequest, request: Request) -> BotResponse:
    return await _container(request).service.handle_message(payload.slack_user_id, "help")


@app.post("/operations/sla-sweep", tags=["operations"], dependencies=[Depends(_require_demo_token)])
async def sla_sweep(request: Request) -> dict[str, int]:
    return await _container(request).service.run_sla_sweep(datetime.now().astimezone())
