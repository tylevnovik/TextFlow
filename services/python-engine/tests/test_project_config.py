from __future__ import annotations

from app.config import engine_service_title, load_project_config, product_name, product_version


def test_project_config_is_loaded_from_repository_manifest():
    config = load_project_config()

    assert config["product"]["version"] == "0.2.0"
    assert product_version() == "0.2.0"
    assert product_name() == "TextFlow Studio"
    assert engine_service_title() == "TextFlow Python Engine"
