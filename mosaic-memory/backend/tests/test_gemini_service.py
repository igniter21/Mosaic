import json
from typing import Self

from pydantic import SecretStr

from mosaic_memory_api.core.config import Settings
from mosaic_memory_api.domain.tab_context import TabContextRequest
from mosaic_memory_api.services import gemini_service


class FakeResponse:
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "summary": "A concise page summary.",
                                            "topics": ["privacy", "retrieval"],
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            }
        ).encode()


def test_gemini_request_keeps_the_local_api_key_out_of_the_url(
    monkeypatch,
) -> None:
    captured_request = None

    def fake_urlopen(request, timeout):
        nonlocal captured_request
        captured_request = request
        assert timeout == 30
        return FakeResponse()

    monkeypatch.setattr(
        gemini_service,
        "get_settings",
        lambda: Settings(
            gemini_api_key=SecretStr("test-only-secret"),
            gemini_model="gemini-test-model",
        ),
    )
    monkeypatch.setattr(gemini_service, "urlopen", fake_urlopen)

    result = gemini_service.understand_tab_context(
        TabContextRequest(
            title="Local-only testing",
            host="example.com",
            path="/testing",
            context_text="This is enough visible page text for the Gemini request test. "
            * 2,
        )
    )

    assert result.summary == "A concise page summary."
    assert result.topics == ["privacy", "retrieval"]
    assert result.model_id == "gemini-test-model"
    assert captured_request is not None
    assert "test-only-secret" not in captured_request.full_url
    assert captured_request.get_header("X-goog-api-key") == "test-only-secret"
    body = json.loads(captured_request.data.decode("utf-8"))
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}
    assert body["generationConfig"]["maxOutputTokens"] == 1200


def test_http_error_detail_formats_quota_exhaustion_message() -> None:
    from io import BytesIO
    from urllib.error import HTTPError

    payload = json.dumps(
        {
            "error": {
                "code": 429,
                "message": "Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3.6-flash",
                "status": "RESOURCE_EXHAUSTED",
            }
        }
    ).encode("utf-8")

    error = HTTPError(
        url="https://generativelanguage.googleapis.com",
        code=429,
        msg="Too Many Requests",
        hdrs={},
        fp=BytesIO(payload),
    )

    detail = gemini_service._http_error_detail(error)
    assert "Gemini 3.6 Flash free tier limit (20 req/day) exhausted" in detail


def test_format_evidence_item_includes_summary_topics_and_excerpt() -> None:
    item = {
        "title": "WhatsApp Web",
        "host": "web.whatsapp.com",
        "path": "/",
        "summary": "Recent chats including birthday wishes for Aaru.",
        "topics": ["WhatsApp", "Birthday Wishes"],
        "description": "WhatsApp web application",
        "channel": "Official",
        "excerpt": "Rishi: Hello",
    }
    formatted = gemini_service._format_evidence_item(1, item)
    assert "Evidence 1 — WhatsApp Web (web.whatsapp.com/):" in formatted
    assert "Summary: Recent chats including birthday wishes for Aaru." in formatted
    assert "Topics: WhatsApp, Birthday Wishes" in formatted
    assert "Channel: Official" in formatted
    assert "Description: WhatsApp web application" in formatted
    assert "Excerpt:\nRishi: Hello" in formatted


def test_answer_tab_question_parses_json_response(monkeypatch) -> None:
    monkeypatch.setattr(
        gemini_service,
        "_generate_content",
        lambda _prompt, max_output_tokens: (
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "answer": "There was a birthday greeting for Aaru."
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
            "gemini-test-model",
        ),
    )
    answer = gemini_service.answer_tab_question(
        "birthday",
        [
            {
                "title": "WhatsApp",
                "host": "web.whatsapp.com",
                "path": "/",
                "summary": "Birthday wishes for Aaru.",
                "excerpt": "chat messages",
            }
        ],
    )
    assert answer == "There was a birthday greeting for Aaru."
