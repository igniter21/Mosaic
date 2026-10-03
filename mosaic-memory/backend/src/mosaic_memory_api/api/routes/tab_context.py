import io
import re
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from sqlalchemy.orm import Session

from mosaic_memory_api.db.session import get_db
from mosaic_memory_api.domain.events import EventRead
from mosaic_memory_api.domain.tab_context import TabContextRequest, TabContextResponse
from mosaic_memory_api.services.domain_policy_service import (
    PrivacyPolicyDeniedError,
    enforce_domain_policy,
)
from mosaic_memory_api.services.gemini_service import (
    GeminiNotConfiguredError,
    GeminiRequestError,
)
from mosaic_memory_api.services.policy_service import record_privacy_action
from mosaic_memory_api.services.privacy_service import SourceDisabledError
from mosaic_memory_api.services.tab_context_service import understand_and_store_tab

router = APIRouter()


def resolve_local_file_path(path_str: str) -> Path | None:
    unquoted = urllib.parse.unquote(path_str).strip().split("?")[0].split("#")[0]
    cleaned = re.sub(r"^/([a-zA-Z]:)", r"\1", unquoted)
    for c in [cleaned, unquoted, cleaned.lstrip("/"), unquoted.lstrip("/")]:
        p = Path(c)
        if p.is_file():
            return p
    raw = path_str.strip().split("?")[0].split("#")[0]
    raw_cleaned = re.sub(r"^/([a-zA-Z]:)", r"\1", raw)
    for c in [raw_cleaned, raw, raw_cleaned.lstrip("/"), raw.lstrip("/")]:
        p = Path(c)
        if p.is_file():
            return p
    return None


def extract_text_from_local_file(file_path: Path) -> tuple[str, str | None]:
    suffix = file_path.suffix.lower()
    description: str | None = None
    if suffix in (".html", ".htm"):
        raw_html = file_path.read_text(encoding="utf-8", errors="replace")

        class HTMLTextExtractor(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.text_parts: list[str] = []
                self.skip = False
                self.in_title = False
                self.title = ""

            def handle_starttag(
                self, tag: str, attrs: list[tuple[str, str | None]]
            ) -> None:
                if tag in ("script", "style", "noscript", "svg"):
                    self.skip = True
                elif tag == "title":
                    self.in_title = True
                elif tag == "meta":
                    attr_dict = {k.lower(): v for k, v in attrs if v is not None}
                    if (
                        attr_dict.get("name") == "description"
                        and "content" in attr_dict
                    ):
                        nonlocal description
                        description = attr_dict["content"].strip()[:500]

            def handle_endtag(self, tag: str) -> None:
                if tag in ("script", "style", "noscript", "svg"):
                    self.skip = False
                elif tag == "title":
                    self.in_title = False

            def handle_data(self, data: str) -> None:
                if self.in_title:
                    self.title += data
                elif not self.skip:
                    clean = data.strip()
                    if clean:
                        self.text_parts.append(clean)

        parser = HTMLTextExtractor()
        parser.feed(raw_html)
        text = " ".join(parser.text_parts)[:6_000]
        return text, description

    raw_text = file_path.read_text(encoding="utf-8", errors="replace")
    return " ".join(raw_text.split())[:6_000], None


@router.post(
    "/tab", response_model=TabContextResponse, status_code=status.HTTP_201_CREATED
)
def understand_current_tab(
    request: TabContextRequest,
    db: Session = Depends(get_db),
) -> TabContextResponse:
    if (request.host == "local-file" or request.source == "document") and len(
        request.context_text.strip()
    ) < 30:
        local_path = resolve_local_file_path(request.path)
        if local_path:
            extracted, desc = extract_text_from_local_file(local_path)
            if len(extracted.strip()) >= 30:
                request = request.model_copy(
                    update={
                        "context_text": extracted,
                        "description": request.description or desc,
                        "source": "document",
                    }
                )

    if len(request.context_text.strip()) < 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There was not enough readable text in this document to understand.",
        )

    try:
        enforce_domain_policy(db, request.source, request.host)
        event, understanding = understand_and_store_tab(db, request)
    except (SourceDisabledError, PrivacyPolicyDeniedError) as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except GeminiNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except GeminiRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    record_privacy_action(
        db,
        direction="external",
        provider="gemini",
        action="understand_tab",
        source=request.source,
        bytes_count=len(request.context_text.encode("utf-8")),
        reason="explicit user-triggered tab understanding",
        metadata={"host": request.host, "path": request.path},
    )
    return TabContextResponse(
        event=EventRead.model_validate(event),
        model_id=understanding.model_id,
        summary=understanding.summary,
        topics=understanding.topics,
    )


@router.post(
    "/pdf", response_model=TabContextResponse, status_code=status.HTTP_201_CREATED
)
async def understand_pdf_document(
    file: UploadFile | None = File(default=None),
    title: str = Form(default="PDF Document"),
    host: str = Form(default="local-file"),
    path: str = Form(default="/document.pdf"),
    description: str | None = Form(default=None),
    source: str = Form(default="document"),
    db: Session = Depends(get_db),
) -> TabContextResponse:
    content: bytes | None = None
    if file is not None:
        content = await file.read()

    if not content:
        local_path = resolve_local_file_path(path)
        if local_path:
            content = local_path.read_bytes()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF file is empty or could not be found.",
        )

    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This PDF is password-protected and cannot be read.",
            )

        extracted_text_parts: list[str] = []
        total_len = 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            clean_page = " ".join(page_text.split())
            if clean_page:
                extracted_text_parts.append(clean_page)
                total_len += len(clean_page)
                if total_len >= 6_000:
                    break

        context_text = " ".join(extracted_text_parts)[:6_000]
        if len(context_text.strip()) < 30:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract enough text from this PDF. It may contain scanned images without text.",
            )

        # Use PDF document metadata if description wasn't provided
        if not description and reader.metadata:
            meta_parts: list[str] = []
            if reader.metadata.title:
                meta_parts.append(f"Title: {reader.metadata.title}")
            if reader.metadata.author:
                meta_parts.append(f"Author: {reader.metadata.author}")
            if reader.metadata.subject:
                meta_parts.append(f"Subject: {reader.metadata.subject}")
            if meta_parts:
                description = "; ".join(meta_parts)[:500]

    except PyPdfError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or corrupted PDF file: {error}",
        ) from error

    clean_host = host.lower().strip().split(":")[0].split("/")[0] or "local-file"
    clean_path = path.strip().split("?")[0].split("#")[0]
    if clean_host == "local-file":
        clean_path = urllib.parse.unquote(clean_path)
    if not clean_path.startswith("/"):
        clean_path = f"/{clean_path}"

    tab_request = TabContextRequest(
        title=title[:500] if title.strip() else "PDF Document",
        host=clean_host,
        path=clean_path[:1_000],
        description=description,
        context_text=context_text,
        source=source if source in ("browser", "youtube", "document") else "document",
    )

    try:
        enforce_domain_policy(db, tab_request.source, tab_request.host)
        event, understanding = understand_and_store_tab(db, tab_request)
    except (SourceDisabledError, PrivacyPolicyDeniedError) as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except GeminiNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except GeminiRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    record_privacy_action(
        db,
        direction="external",
        provider="gemini",
        action="understand_pdf",
        source=tab_request.source,
        bytes_count=len(context_text.encode("utf-8")),
        reason="explicit user-triggered PDF understanding",
        metadata={"host": tab_request.host, "path": tab_request.path},
    )
    return TabContextResponse(
        event=EventRead.model_validate(event),
        model_id=understanding.model_id,
        summary=understanding.summary,
        topics=understanding.topics,
    )
