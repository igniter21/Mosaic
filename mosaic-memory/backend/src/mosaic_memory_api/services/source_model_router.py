"""Route approved source metadata through the matching local understanding model.

Sources answer *where* an event came from; modalities decide *how* its small,
approved metadata is interpreted.  Every model returns the same canonical
understanding shape, so storage, embeddings, graph links, retrieval, and
deletion stay source-agnostic.

These are intentionally local metadata models. Mosaic never captures page
bodies, video frames/audio, editor contents, or document text unless a future,
separate opt-in collector is added for that material.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from mosaic_memory_api.domain.events import Source

if TYPE_CHECKING:
    from mosaic_memory_api.db.models import RawEvent


@dataclass(frozen=True)
class LocalUnderstanding:
    """Canonical output from one local source-specific understanding model."""

    model_id: str
    model_label: str
    modality: str
    summary: str
    searchable_text: str


@dataclass(frozen=True)
class SourceModel:
    """A privacy-bounded local model profile for exactly one source."""

    source: Source
    model_id: str
    model_label: str
    modality: str
    default_action: str
    payload_keys: tuple[str, ...]
    action_by_event_type: tuple[tuple[str, str], ...] = ()
    context_summary_key: str | None = None

    def understand(self, event: RawEvent) -> LocalUnderstanding:
        action = dict(self.action_by_event_type).get(
            event.event_type,
            self.default_action,
        )
        subject = event.title or event.event_type.replace("_", " ")
        payload_text = " ".join(
            _safe_scalar_text(event.payload.get(key)) for key in self.payload_keys
        )
        searchable_text = " ".join(
            part
            for part in (
                self.source.value,
                event.event_type.replace("_", " "),
                subject,
                payload_text,
            )
            if part
        )
        context_summary = (
            _safe_scalar_text(event.payload.get(self.context_summary_key))
            if self.context_summary_key
            else ""
        )
        summary = (
            f"Understood {subject}: {context_summary}"
            if context_summary
            else f"{action} {subject}"
        )
        return LocalUnderstanding(
            model_id=self.model_id,
            model_label=self.model_label,
            modality=self.modality,
            summary=summary[:600],
            searchable_text=searchable_text,
        )


def _safe_scalar_text(value: Any) -> str:
    """Use only profile-approved scalar metadata in local understanding."""

    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(
            item.strip() for item in value[:16] if isinstance(item, str)
        )
    return ""


SOURCE_MODELS: dict[Source, SourceModel] = {
    Source.BROWSER: SourceModel(
        source=Source.BROWSER,
        model_id="local-web-metadata-v1",
        model_label="Web activity model",
        modality="web metadata",
        default_action="Visited",
        payload_keys=(
            "host",
            "path",
            "context_summary",
            "context_topics",
            "context_excerpt",
        ),
        context_summary_key="context_summary",
    ),
    Source.YOUTUBE: SourceModel(
        source=Source.YOUTUBE,
        model_id="local-video-metadata-v1",
        model_label="Video activity model",
        modality="video metadata",
        default_action="Watched",
        payload_keys=(
            "video_id",
            "host",
            "channel",
            "context_summary",
            "context_topics",
            "context_excerpt",
        ),
        context_summary_key="context_summary",
    ),
    Source.LEETCODE: SourceModel(
        source=Source.LEETCODE,
        model_id="local-code-practice-metadata-v1",
        model_label="Coding practice model",
        modality="coding-practice metadata",
        default_action="Opened LeetCode activity:",
        payload_keys=("problem_slug", "host"),
    ),
    Source.VSCODE: SourceModel(
        source=Source.VSCODE,
        model_id="local-code-workspace-metadata-v1",
        model_label="Code workspace model",
        modality="code metadata",
        default_action="Worked in",
        payload_keys=("relative_path", "language_id", "file_extension", "workspace_name"),
        action_by_event_type=(
            ("document_saved", "Saved"),
            ("editor_focused", "Worked in"),
        ),
    ),
    Source.DOCUMENT: SourceModel(
        source=Source.DOCUMENT,
        model_id="local-document-metadata-v1",
        model_label="Document metadata model",
        modality="document metadata",
        default_action="Indexed document:",
        payload_keys=(
            "host",
            "path",
            "extension",
            "size_bytes",
            "modified_at",
            "context_summary",
            "context_topics",
            "context_excerpt",
        ),
        context_summary_key="context_summary",
    ),
}


def model_for_source(source: Source | str) -> SourceModel:
    """Return the one privacy profile permitted to interpret this source."""

    normalized_source = source if isinstance(source, Source) else Source(source)
    return SOURCE_MODELS[normalized_source]


def understand_event(event: RawEvent) -> LocalUnderstanding:
    """Select and run the source's local model on its approved metadata."""

    return model_for_source(event.source).understand(event)
