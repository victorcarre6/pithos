import { Activity, Bot, Database, FileText, TerminalSquare } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

type Run = {
  run_id: string;
  status: string | null;
  model: string | null;
  started_at: string | null;
  stop_reason: string | null;
  duration_ms: number | null;
  total_tokens: number | null;
  tool_calls: number | null;
  tool_failures: number | null;
  pull_request_url: string | null;
};

type PithosEvent = {
  event_id: string;
  timestamp: string;
  type: string;
  source: string;
  payload: unknown;
};

type Stats = {
  total_runs: number;
  running_runs: number;
  completed_runs: number;
  other_runs: number;
  events: number;
  tool_failures: number;
  total_tokens: number;
  duration_ms: number;
};

type Health = { service: string; data: string; events?: number };

const EMPTY_STATS: Stats = {
  total_runs: 0,
  running_runs: 0,
  completed_runs: 0,
  other_runs: 0,
  events: 0,
  tool_failures: 0,
  total_tokens: 0,
  duration_ms: 0,
};
const DOMAINS = ["all", "model", "tool", "command", "file", "test", "harness", "git", "dependency", "network", "telegram"];

async function api<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`);
  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json() as Promise<T>;
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="card">
      <div className="label">{label}</div>
      <div className="metric">{value}</div>
    </div>
  );
}

function RunList({ runs, selected, onSelect }: { runs: Run[]; selected: string; onSelect: (run: Run) => void }) {
  return (
    <div className="list">
      {runs.map((run) => (
        <button
          className={`run ${selected === run.run_id ? "active" : ""}`}
          onClick={() => onSelect(run)}
          key={run.run_id}
        >
          <div className="row">
            <strong>{run.run_id}</strong>
            <span className={`pill ${run.status}`}>{run.status ?? "unknown"}</span>
          </div>
          <div className="muted">{run.model ?? "—"} · {run.started_at ?? "—"}</div>
        </button>
      ))}
    </div>
  );
}

export function App() {
  const [stats, setStats] = useState(EMPTY_STATS);
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<Run | null>(null);
  const [events, setEvents] = useState<PithosEvent[]>([]);
  const [domain, setDomain] = useState("all");
  const [offset, setOffset] = useState(0);
  const [artifact, setArtifact] = useState("");
  const [error, setError] = useState("");
  const [health, setHealth] = useState<Health | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [nextStats, nextRuns, nextHealth] = await Promise.all([
        api<Stats>("/stats"),
        api<{ items: Run[] }>("/runs"),
        api<Health>("/health"),
      ]);
      setStats(nextStats);
      setRuns(nextRuns.items);
      setHealth(nextHealth);
      setSelected((current) => current ?? nextRuns.items[0] ?? null);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 10_000);

    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    if (!selected) return;
    const domainQuery = domain === "all" ? "" : `&domain=${domain}`;
    void api<{ items: PithosEvent[] }>(
      `/runs/${selected.run_id}/events?limit=100&offset=${offset}${domainQuery}`,
    )
      .then((value) => setEvents(value.items))
      .catch((reason) => setError(String(reason)));
  }, [selected, domain, offset]);

  const selectRun = (run: Run) => {
    setSelected(run);
    setOffset(0);
    setArtifact("");
  };

  const loadArtifact = async (name: string) => {
    if (!selected) return;
    try {
      const result = await api<{ content: string }>(
        `/runs/${selected.run_id}/artifacts/${name}`,
      );
      setArtifact(result.content);
    } catch (reason) {
      setArtifact(reason instanceof Error ? reason.message : String(reason));
    }
  };

  return (
    <main className="shell">
      <header className="header">
        <div className="brand">
          <div className="logo"><Bot size={18} /></div>
          <div><strong>Pithos</strong><div className="subtitle">Agent observability</div></div>
        </div>
        <div className={health?.data === "available" ? "health" : "error"}>
          <Activity size={16} /> Données {health?.data ?? "indisponibles"}
        </div>
      </header>

      {error && <p className="error">{error}</p>}
      <section className="grid">
        <Metric label="Runs" value={stats.total_runs} />
        <Metric label="En cours" value={stats.running_runs} />
        <Metric label="Tokens" value={stats.total_tokens} />
        <Metric label="Tool failures" value={stats.tool_failures} />
      </section>

      <section className="layout">
        <div className="card">
          <h3>Runs</h3>
          <RunList runs={runs} selected={selected?.run_id ?? ""} onSelect={selectRun} />
        </div>
        <div className="stack">
          <div className="card">
            <div className="row"><h3>Run detail</h3><Database size={18} /></div>
            {selected && (
              <div className="detail-grid">
                <div><span className="label">Durée</span>{selected.duration_ms ?? 0} ms</div>
                <div><span className="label">Tokens</span>{selected.total_tokens ?? 0}</div>
                <div><span className="label">Tools</span>{selected.tool_calls ?? 0}</div>
                <div><span className="label">Échecs tools</span>{selected.tool_failures ?? 0}</div>
              </div>
            )}
            <div className="actions">
              <button className="action" onClick={() => void loadArtifact("report.md")}><FileText size={14} /> Rapport</button>
              <button className="action" onClick={() => void loadArtifact("stdout.jsonl")}><TerminalSquare size={14} /> stdout</button>
              <button className="action" onClick={() => void loadArtifact("stderr.log")}><TerminalSquare size={14} /> stderr</button>
            </div>
            {artifact && <pre className="artifact">{artifact}</pre>}
          </div>

          <div className="card">
            <div className="row"><h3>Timeline</h3><Database size={18} /></div>
            <div className="tabs">
              {DOMAINS.map((item) => (
                <button
                  className={`tab ${domain === item ? "active" : ""}`}
                  onClick={() => { setDomain(item); setOffset(0); }}
                  key={item}
                >
                  {item}
                </button>
              ))}
            </div>
            <div className="events">
              {events.map((event) => (
                <article className="event" key={event.event_id}>
                  <div className="row"><strong>{event.type}</strong><span className="muted">{event.source}</span></div>
                  <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                </article>
              ))}
            </div>
            <div className="pager">
              <button className="action" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 100))}>Précédent</button>
              <button className="action" disabled={events.length < 100} onClick={() => setOffset(offset + 100)}>Suivant</button>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
