import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]


def test_host_and_docker_configs_share_the_one_hour_request_limit():
    for config_dir in ("pi", "pi-docker"):
        settings_path = PROJECT_ROOT / "config" / config_dir / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))

        assert settings["httpIdleTimeoutMs"] == 3_600_000
        assert settings["retry"]["enabled"] is False
        assert settings["retry"]["provider"]["timeoutMs"] == 3_600_000
        assert settings["retry"]["provider"]["maxRetries"] == 0


def test_pi_configs_only_differ_by_the_ollama_host():
    host_path = PROJECT_ROOT / "config" / "pi" / "models.json"
    docker_path = PROJECT_ROOT / "config" / "pi-docker" / "models.json"
    host = json.loads(host_path.read_text(encoding="utf-8"))
    docker = json.loads(docker_path.read_text(encoding="utf-8"))

    host_provider = host["providers"]["ollama"]
    docker_provider = docker["providers"]["ollama"]

    assert host_provider["baseUrl"] == "http://127.0.0.1:11434/v1"
    assert docker_provider["baseUrl"] == "http://host.docker.internal:11434/v1"
    assert host_provider["models"][0]["id"] == docker_provider["models"][0]["id"]
