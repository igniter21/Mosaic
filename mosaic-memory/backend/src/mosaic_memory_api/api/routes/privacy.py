from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from mosaic_memory_api.db.session import get_db
from mosaic_memory_api.domain.privacy import (
    GlobalEraseRequest,
    GlobalEraseResult,
)
from mosaic_memory_api.services.privacy_service import (
    InvalidGlobalEraseConfirmationError,
    erase_all_local_memory,
)

router = APIRouter()


@router.post("/erase-all", response_model=GlobalEraseResult)
def erase_all_memory(
    request: GlobalEraseRequest,
    db: Session = Depends(get_db),
) -> GlobalEraseResult:
    try:
        return erase_all_local_memory(db, request.confirmation)
    except InvalidGlobalEraseConfirmationError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
