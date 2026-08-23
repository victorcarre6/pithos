"""Portable host and Ollama resource sampling."""

import json
import platform
import threading
from datetime import datetime, timezone
from pathlib import Path

import psutil


class ResourceSampler:
    """Sample host memory, CPU and model residency until stopped."""

    def __init__(self, path: Path, ollama, interval_seconds=1, on_sample=None):
        self.path = path
        self.ollama = ollama
        self.interval_seconds = interval_seconds
        self.on_sample = on_sample or (lambda sample: None)
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        """Start the background sampler."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._run, name="benchmark-resources", daemon=True)
        self._thread.start()

    def stop(self):
        """Stop sampling and wait for the final flush."""

        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self.interval_seconds + 2)

    def _run(self):
        """Write one JSON object per interval."""

        while not self._stop.is_set():
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            try:
                resident = self.ollama.running_models()
            except RuntimeError as error:
                resident = {"error": str(error)}
            sample = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cpu_percent": psutil.cpu_percent(),
                "memory_used_bytes": memory.used,
                "memory_available_bytes": memory.available,
                "memory_percent": memory.percent,
                "swap_used_bytes": swap.used,
                "swap_percent": swap.percent,
                "ollama_models": resident,
            }
            line = json.dumps(sample, separators=(",", ":"))
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(line + "\n")
                stream.flush()
            self.on_sample(sample)
            self._stop.wait(self.interval_seconds)


def environment_snapshot():
    """Capture stable host metadata without guessing GPU counters."""

    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "logical_cpu_count": psutil.cpu_count(),
        "physical_cpu_count": psutil.cpu_count(logical=False),
        "memory_total_bytes": psutil.virtual_memory().total,
        "gpu_metrics": {
            "available": False,
            "reason": "macOS exposes no stable unprivileged per-process GPU counter",
        },
    }
