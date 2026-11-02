from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import LLMClient
from app.ai.schemas import SearchRequest, SearchResult
from app.ai.service import UNAVAILABLE, reserve_call, search
from app.core.db import get_session
from app.core.errors import ErrorResponse
from app.modules.specialists.repository import find_specialist

router = APIRouter(prefix="/api/v1/specialists", tags=["search"])


def get_llm(request: Request) -> LLMClient | None:
    return cast(LLMClient | None, request.app.state.llm)


@router.post(
    "/{slug}/search",
    response_model=SearchResult,
    operation_id="search_slots",
    responses={429: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def search_slots(
    slug: str,
    body: SearchRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    client: Annotated[LLMClient | None, Depends(get_llm)],
) -> SearchResult:
    specialist = await find_specialist(session, slug)
    if specialist is None:
        raise HTTPException(404)
    if client is None or not await reserve_call(
        session, request.app.state.settings.ai_daily_request_limit
    ):
        return SearchResult(
            status="unavailable", message=UNAVAILABLE, timezone=specialist.timezone, items=[]
        )
    return await search(session, specialist, body.text, client)
