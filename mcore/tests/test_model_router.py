from mcore.core.model_router import HybridModelRouter


class FakeClient:
    model = "local-test"
    def __init__(self):
        self.calls = 0
    def generate_json(self, prompt):
        self.calls += 1
        return {"route": "local"}


class FakeCloud:
    def __init__(self):
        self.calls = 0
    def generate_json(self, prompt):
        self.calls += 1
        return {"route": "cloud"}


def test_router_defaults_to_local_even_when_cloud_client_exists():
    local, cloud = FakeClient(), FakeCloud()
    router = HybridModelRouter(local, cloud)
    result = router.generate_json_with_policy("sensitive RTL")
    assert result["route"] == "local"
    assert local.calls == 1 and cloud.calls == 0
    assert router.last_route == "local_ollama"


def test_router_requires_explicit_approval_and_cloud_classification():
    local, cloud = FakeClient(), FakeCloud()
    router = HybridModelRouter(local, cloud)
    router.generate_json_with_policy("RTL", cloud_approved=True, data_classification="sensitive")
    assert cloud.calls == 0
    result = router.generate_json_with_policy(
        "non-sensitive prompt", cloud_approved=True,
        data_classification="approved_for_cloud",
    )
    assert result["route"] == "cloud"
    assert cloud.calls == 1
    assert router.last_route == "cloud_approved_request"
