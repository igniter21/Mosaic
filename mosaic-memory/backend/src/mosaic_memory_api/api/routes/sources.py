from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from mosaic_memory_api.db.models import SourceSetting
from mosaic_memory_api.db.session import get_db
from mosaic_memory_api.domain.events import Source
from mosaic_memory_api.domain.privacy import (
    SourceSettingRead,
    SourceSettingUpdate,
)
from mosaic_memory_api.services.privacy_service import (
    list_source_settings,
    set_source_enabled,
)
from mosaic_memory_api.services.source_model_router import model_for_source

router = APIRouter()


def serialize_source_setting(setting: SourceSetting) -> SourceSettingRead:
    source = Source(setting.source)
    model = model_for_source(source)
    return SourceSettingRead(
        source=source,
        enabled=setting.enabled,
        updated_at=setting.updated_at,
        model_id=model.model_id,
        model_label=model.model_label,
        modality=model.modality,
    )


@router.get("", response_model=list[SourceSettingRead])
def get_sources(
    db: Session = Depends(get_db),
) -> list[SourceSettingRead]:
    settings = list_source_settings(db)
    return [serialize_source_setting(setting) for setting in settings]


@router.patch("/{source}", response_model=SourceSettingRead)
def update_source(
    source: Source,
    update: SourceSettingUpdate,
    db: Session = Depends(get_db),
) -> SourceSettingRead:
    setting = set_source_enabled(db, source, update.enabled)
    return serialize_source_setting(setting)
