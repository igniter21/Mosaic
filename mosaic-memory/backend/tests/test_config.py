from mosaic_memory_api.core.config import Settings


def test_allowed_origins_includes_frontend_and_explicit_collectors() -> None:
    settings = Settings(
        frontend_origin="http://localhost:3000",
        collector_origins=(
            "chrome-extension://first, chrome-extension://second, "
            "chrome-extension://first"
        ),
    )

    assert settings.allowed_origins == [
        "http://localhost:3000",
        "chrome-extension://first",
        "chrome-extension://second",
    ]
