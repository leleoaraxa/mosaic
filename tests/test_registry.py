from app.registry.service import registry_service

def test_registry_loaded():
    items = registry_service.list_all()
    assert isinstance(items, list)
