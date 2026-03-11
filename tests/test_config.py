from app.main import barcode_service


def test_provider_config_uses_portugal_first():
    config = barcode_service.config
    assert config["lookup"]["countryPriority"][0] == "PT"
    assert config["lookup"]["chains"]["food"][0] == "open_food_facts"
    assert config["providers"]["continente_pt"]["enabled"] is False
    assert config["providers"]["auchan_pt"]["enabled"] is False
