from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from mosaic_memory_api.db.session import get_db
from mosaic_memory_api.domain.memory import AskMemoryRequest, AskMemoryResponse
from mosaic_memory_api.services.gemini_service import (
    GeminiNotConfiguredError,
    GeminiRequestError,
)
from mosaic_memory_api.services.memory_service import ask_memory, ask_memory_with_gemini

router = APIRouter()


@router.post("/ask", response_model=AskMemoryResponse)
def ask_your_memory(
    request: AskMemoryRequest,
    db: Session = Depends(get_db),
) -> AskMemoryResponse:
    return ask_memory(db, query=request.query, limit=request.limit)


@router.post("/ask-with-gemini", response_model=AskMemoryResponse)
def ask_with_gemini(
    request: AskMemoryRequest,
    db: Session = Depends(get_db),
) -> AskMemoryResponse:
    try:
        return ask_memory_with_gemini(db, query=request.query, limit=request.limit)
    except GeminiNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except GeminiRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
