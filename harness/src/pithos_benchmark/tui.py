"""Live Textual interface for one benchmark campaign."""

from collections import deque

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Label, ProgressBar, RichLog, Static


class BenchmarkApp(App):
    """Display pipeline, attempts and live events while the engine runs."""

    CSS = """
    Screen { background: #080b12; color: #d7e0ee; }
    Header { background: #111827; color: #a7f3d0; }
    #hero { height: 5; padding: 1 2; background: #101722; border-bottom: solid #2dd4bf; }
    #model { color: #f8fafc; text-style: bold; }
    #campaign { color: #6ee7b7; }
    #main { height: 1fr; }
    #pipeline { width: 28; padding: 1; border: round #334155; }
    #center { width: 1fr; }
    #metrics { width: 34; padding: 1; border: round #334155; }
    .panel-title { color: #5eead4; text-style: bold; margin-bottom: 1; }
    #current { height: 7; padding: 1 2; border: round #0f766e; }
    #progress { margin: 1 0; }
    #attempts { height: 1fr; border: round #334155; }
    #events { height: 14; border: round #334155; padding: 0 1; }
    #status-good { color: #4ade80; }
    #status-bad { color: #fb7185; }
    Footer { background: #111827; }
    """

    BINDINGS = [
        ("q", "request_quit", "Safe stop"),
        ("l", "focus_events", "Events"),
        ("a", "focus_attempts", "Attempts"),
    ]

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.engine.on_event = self._receive_event
        self.completed = 0
        self.total = 0
        self.event_types = deque(maxlen=8)
        self.latest_sample = {}
        self.active_suite = None
        self.completed_suites = set()

    def compose(self) -> ComposeResult:
        """Compose the dense three-column benchmark cockpit."""

        yield Header(show_clock=True)
        with Vertical(id="hero"):
            yield Label(f"PITHOS MODEL BENCHMARK  ·  {self.engine.configuration.model}", id="model")
            yield Label("campaign preparing · evidence first · no model downloads", id="campaign")
        with Horizontal(id="main"):
            with Vertical(id="pipeline"):
                yield Label("PIPELINE", classes="panel-title")
                yield Static("● discovery\n○ smoke\n○ protocol\n○ Pi tools\n○ agentic\n○ endurance", id="pipeline-state")
            with Vertical(id="center"):
                yield Static("Waiting for engine…", id="current")
                yield ProgressBar(total=100, show_eta=False, id="progress")
                yield DataTable(id="attempts")
            with Vertical(id="metrics"):
                yield Label("LIVE SIGNAL", classes="panel-title")
                yield Static("Attempts     0\nPassed       0\nFailed       0\nMedian tok/s —", id="metric-values")
                yield Label("RECENT TRANSITIONS", classes="panel-title")
                yield Static("—", id="transitions")
        yield RichLog(id="events", highlight=True, markup=True, wrap=True)
        yield Footer()

    def on_mount(self):
        """Initialize the table and start the engine outside the UI thread."""

        table = self.query_one("#attempts", DataTable)
        table.add_columns("Scenario", "Try", "Result", "Duration", "TTFT", "tok/s", "Peak RAM")
        self.run_worker(self._run_engine, thread=True, exclusive=True)

    def _run_engine(self):
        """Run the synchronous benchmark worker."""

        try:
            manifest = self.engine.run()
        except Exception as error:
            self.call_from_thread(self._show_failure, error)
            return
        self.call_from_thread(self._show_completion, manifest)

    def _receive_event(self, event):
        """Bridge an engine worker event to Textual's event loop."""

        self.call_from_thread(self._apply_event, event)

    def _apply_event(self, event):
        """Update all panels from one persisted event."""

        event_type = event["type"]
        payload = event["payload"]
        self.event_types.appendleft(event_type)
        self.query_one("#transitions", Static).update("\n".join(self.event_types))
        self.query_one("#events", RichLog).write(f"[dim]{event['timestamp'][11:19]}[/] [cyan]{event_type}[/] {payload}")

        if event_type == "campaign.started":
            self.total = payload["scenario_count"] * self.engine.configuration.attempts
            self.query_one("#campaign", Label).update(self.engine.campaign_id)
            self._update_pipeline()
        elif event_type == "scenario.started":
            if self.active_suite and self.active_suite != payload["suite"]:
                self.completed_suites.add(self.active_suite)
            self.active_suite = payload["suite"]
            self._update_pipeline()
            content = f"[b]{payload['title']}[/b]\n{payload['scenario_id']}\ncollecting raw response + resources"
            self.query_one("#current", Static).update(content)
        elif event_type == "attempt.started":
            content = (
                f"[b]{payload['scenario_id']}[/b]\n"
                f"attempt {payload['attempt']}/{self.engine.configuration.attempts}\n"
                "streaming response · sampling host every second"
            )
            self.query_one("#current", Static).update(content)
        elif event_type == "attempt.finished":
            self._add_attempt(payload)
        elif event_type == "resource.sample":
            self.latest_sample = payload
            self._update_metrics()

    def _add_attempt(self, result):
        """Append one attempt row and recompute compact metrics."""

        table = self.query_one("#attempts", DataTable)
        passed = "PASS" if result["passed"] else "FAIL"
        duration = result.get("duration_seconds")
        speed = result.get("decode_tokens_per_second")
        measurements = result.get("measurements") or {}
        ttft = measurements.get("time_to_first_content_seconds")
        peak_ram = measurements.get("peak_memory_used_bytes")
        duration_text = "—" if duration is None else f"{duration:.1f}s"
        speed_text = "—" if speed is None else f"{speed:.3f}"
        ttft_text = "—" if ttft is None else f"{ttft:.1f}s"
        ram_text = "—" if peak_ram is None else f"{peak_ram / 1_000_000_000:.1f}G"
        table.add_row(
            result["scenario_id"],
            str(result["attempt_number"]),
            passed,
            duration_text,
            ttft_text,
            speed_text,
            ram_text,
        )
        self.completed += 1
        progress = 100 * self.completed / self.total if self.total else 0
        self.query_one("#progress", ProgressBar).update(progress=progress)
        self._update_metrics()

    def _update_metrics(self):
        """Combine functional progress and the latest host resource sample."""

        passed_count = sum(result["passed"] for result in self.engine.results)
        failed_count = len(self.engine.results) - passed_count
        speeds = [item["decode_tokens_per_second"] for item in self.engine.results]
        speeds = [value for value in speeds if value is not None]
        median = "—" if not speeds else f"{sorted(speeds)[len(speeds) // 2]:.3f}"
        cpu = self.latest_sample.get("cpu_percent")
        memory = self.latest_sample.get("memory_percent")
        swap = self.latest_sample.get("swap_percent")
        cpu_text = "—" if cpu is None else f"{cpu:.1f}%"
        memory_text = "—" if memory is None else f"{memory:.1f}%"
        swap_text = "—" if swap is None else f"{swap:.1f}%"
        metrics = (
            f"Attempts     {len(self.engine.results)}\n"
            f"Passed       {passed_count}\n"
            f"Failed       {failed_count}\n"
            f"Median tok/s {median}\n\n"
            f"CPU          {cpu_text}\n"
            f"Memory       {memory_text}\n"
            f"Swap         {swap_text}"
        )
        self.query_one("#metric-values", Static).update(metrics)

    def _update_pipeline(self):
        """Render completed, active and pending benchmark layers."""

        suites = ["smoke", "protocol", "pi", "agentic", "endurance"]
        lines = ["✓ discovery"]
        for suite in suites:
            if suite in self.completed_suites:
                marker = "✓"
            elif suite == self.active_suite:
                marker = "●"
            else:
                marker = "○"
            lines.append(f"{marker} {suite}")
        self.query_one("#pipeline-state", Static).update("\n".join(lines))

    def _show_completion(self, manifest):
        """Render the final campaign outcome without auto-closing."""

        summary = manifest["summary"]
        if self.active_suite:
            self.completed_suites.add(self.active_suite)
            self.active_suite = None
            self._update_pipeline()
        content = (
            "[green bold]CAMPAIGN COMPLETE[/green bold]\n"
            f"{summary['passed']} passed · {summary['failed']} failed\n"
            f"artifacts: {self.engine.storage.campaign_root}"
        )
        self.query_one("#current", Static).update(content)
        self.query_one("#progress", ProgressBar).update(progress=100)

    def _show_failure(self, error):
        """Keep the failure visible with its concrete type."""

        content = f"[red bold]CAMPAIGN FAILED[/red bold]\n{type(error).__name__}: {error}"
        self.query_one("#current", Static).update(content)
        self.query_one("#events", RichLog).write(content)

    def action_request_quit(self):
        """Request a safe stop after the active attempt."""

        self.engine.request_stop()
        self.query_one("#current", Static).update(
            "[yellow bold]SAFE STOP REQUESTED[/yellow bold]\nThe active attempt will be preserved before exit."
        )

    def action_focus_events(self):
        """Focus the live event browser."""

        self.query_one("#events", RichLog).focus()

    def action_focus_attempts(self):
        """Focus the attempt matrix."""

        self.query_one("#attempts", DataTable).focus()
