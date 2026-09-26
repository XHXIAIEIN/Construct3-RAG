"""FastAPI composition root for the optional Construct 3 search service.

The HTTP layer owns routing and dependency construction only.  Request/response
contracts live in :mod:`src.interfaces.http.models`; the searchable SOP lives in
:mod:`src.application.search`.
"""

from __future__ import annotations

from pathlib import Path

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

SETTINGS = load_settings()

app = FastAPI(
    title="Construct 3 RAG",
    description="Lookup service for Construct 3 reference data",
    version="1.0.0",
)

_lookup_engine = None
_PLAYGROUND_HTML = Path(__file__).parent / "interfaces" / "http" / "playground.html"


def _get_lookup_engine():
    """Construct the offline deterministic lookup adapter lazily."""
    global _lookup_engine
    if _lookup_engine is None:
        from src.lookup import LookupEngine

        _lookup_engine = LookupEngine(schema_dir=SETTINGS.schema.directory)
    return _lookup_engine


def _search_workflow() -> SearchWorkflow:
    """Bind the lazy lookup provider to one request workflow."""
    return SearchWorkflow(get_lookup_engine=_get_lookup_engine)


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
        outcome = _search_workflow().execute(request_to_command(request))
        return present_search_outcome(outcome)
    except InvalidSearchRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


__all__ = ["app"]
