"""FastAPI composition root for the optional Construct 3 lookup service.

This module holds the routes and builds their dependencies. The request and
response contracts live in :mod:`src.interfaces.http.models`, the search
workflow in :mod:`src.application.search`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from src.application.health import build_health_outcome
from src.application.search import InvalidSearchRequestError, SearchWorkflow
from src.settings import load_settings
from src.interfaces.http.models import HealthResponse, SearchRequest, SearchResponse
from src.interfaces.http.presenters import (
    present_health_outcome,
    present_search_outcome,
    request_to_command,
)

if TYPE_CHECKING:
    from src.lookup.service import LookupEngine

SETTINGS = load_settings()

app = FastAPI(
    title="Construct 3 RAG",
    description="Lookup service for Construct 3 reference data",
    version="1.0.0",
)

_lookup_engine: LookupEngine | None = None
_PLAYGROUND_HTML = Path(__file__).parent / "interfaces" / "http" / "playground.html"


def _get_lookup_engine() -> LookupEngine:
    """Build the lookup engine on the first search and keep it."""
    global _lookup_engine
    if _lookup_engine is None:
        from src.lookup.service import LookupEngine

        _lookup_engine = LookupEngine(schema_dir=SETTINGS.schema.directory)
    return _lookup_engine


@app.get("/playground")
def playground() -> Response:
    """Serve the lightweight API playground without caching it."""
    return Response(
        content=_PLAYGROUND_HTML.read_text(encoding="utf-8"),
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return present_health_outcome(
        build_health_outcome(schema_dir=SETTINGS.schema.directory)
    )


@app.post("/search", response_model=SearchResponse, response_model_exclude_none=True)
def search(request: SearchRequest) -> SearchResponse:
    try:
        workflow = SearchWorkflow(get_lookup_engine=_get_lookup_engine)
        outcome = workflow.execute(request_to_command(request))
        return present_search_outcome(outcome)
    except InvalidSearchRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


__all__ = ["app"]
