"""Read-only localhost dashboard for benchmark campaign artifacts."""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse


def create_app(logs_root=None, results_root=None):
    """Create a dashboard that never opens benchmark SQLite for writing."""

    root = Path(logs_root or Path.home() / "logs" / "pithos").expanduser().resolve()
    campaigns_roots = [root / "benchmarks"]
    if results_root:
        campaigns_roots.append(Path(results_root).expanduser().resolve())
    app = FastAPI(title="Pithos Benchmark", version="1")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTML

    @app.get("/api/health")
    def health():
        available = any(campaigns_root.is_dir() for campaigns_root in campaigns_roots)

        return {"service": "available", "data": "available" if available else "unavailable"}

    @app.get("/api/campaigns")
    def campaigns():
        items = []
        by_id = {}
        for campaigns_root in campaigns_roots:
            for path in sorted(campaigns_root.glob("*/manifest.json"), reverse=True):
                try:
                    manifest = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                by_id.setdefault(manifest["campaign_id"], manifest)
        items = sorted(by_id.values(), key=lambda item: item["campaign_id"], reverse=True)

        return {"items": items, "count": len(items)}

    @app.get("/api/campaigns/{campaign_id}")
    def campaign(campaign_id: str):
        campaign_root = _find_campaign(campaigns_roots, campaign_id)
        manifest = _read_json(campaign_root / "manifest.json")
        summary = _read_json(campaign_root / "summary.json")
        attempts = []
        for path in sorted(campaign_root.glob("attempts/*/*/result.json")):
            attempts.append(_read_json(path))

        return {"manifest": manifest, "summary": summary, "attempts": attempts}

    @app.get("/api/campaigns/{campaign_id}/artifact/{artifact_path:path}")
    def artifact(campaign_id: str, artifact_path: str, offset: int = 0, limit: int = 200_000):
        campaign_root = _find_campaign(campaigns_roots, campaign_id)
        target = (campaign_root / artifact_path).resolve()
        if campaign_root not in target.parents or not target.is_file():
            raise HTTPException(status_code=404, detail="artifact not found")
        safe_offset = max(0, offset)
        safe_limit = min(max(1, limit), 1_000_000)
        with target.open("rb") as stream:
            stream.seek(safe_offset)
            content = stream.read(safe_limit)

        return {
            "path": artifact_path,
            "offset": safe_offset,
            "next_offset": safe_offset + len(content),
            "content": content.decode("utf-8", errors="replace"),
            "complete": safe_offset + len(content) >= target.stat().st_size,
        }

    return app


def _find_campaign(campaigns_roots, campaign_id):
    """Resolve the first raw or versioned copy of one campaign."""

    for campaigns_root in campaigns_roots:
        try:
            return _campaign_root(campaigns_root, campaign_id)
        except HTTPException:
            continue
    raise HTTPException(status_code=404, detail="campaign not found")


def _campaign_root(campaigns_root, campaign_id):
    """Resolve one identifier without allowing path traversal."""

    root = (campaigns_root / campaign_id).resolve()
    if campaigns_root.resolve() not in root.parents or not root.is_dir():
        raise HTTPException(status_code=404, detail="campaign not found")

    return root


def _read_json(path):
    """Read one required dashboard artifact."""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=404, detail=f"invalid artifact: {path.name}") from error


HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pithos Benchmark Observatory</title>
<style>
:root{--ink:#dce7f5;--muted:#8291a8;--bg:#070a10;--panel:#0e1521;--line:#213047;--mint:#55e6c1;--blue:#68a7ff;--bad:#ff6b81;--good:#62e59b}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 15% 0,#102239 0,transparent 36%),var(--bg);color:var(--ink);font:14px Inter,ui-sans-serif,system-ui;min-height:100vh}
header{padding:40px clamp(24px,5vw,72px) 24px;border-bottom:1px solid var(--line)}.kicker{color:var(--mint);letter-spacing:.18em;text-transform:uppercase;font-size:11px}h1{font-size:clamp(30px,5vw,58px);margin:8px 0;font-weight:650;letter-spacing:-.04em}.sub{color:var(--muted);max-width:720px}
main{padding:28px clamp(24px,5vw,72px) 72px}.stats{display:grid;grid-template-columns:repeat(4,minmax(130px,1fr));gap:12px;margin-bottom:26px}.stat,.card{background:linear-gradient(145deg,rgba(18,28,43,.96),rgba(10,16,26,.96));border:1px solid var(--line);border-radius:14px;box-shadow:0 18px 50px #0006}.stat{padding:18px}.stat b{display:block;font-size:27px;margin-top:6px}.label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.12em}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}.card{padding:20px;cursor:pointer;transition:.2s}.card:hover{border-color:#3e6688;transform:translateY(-2px)}.model{font-size:20px;font-weight:650}.id{color:var(--muted);font-family:ui-monospace;font-size:11px;margin:5px 0 18px}.bar{height:6px;background:#192436;border-radius:9px;overflow:hidden}.bar i{display:block;height:100%;background:linear-gradient(90deg,var(--blue),var(--mint))}.metrics{display:flex;gap:20px;margin-top:15px}.metric b{display:block;font-size:17px}.good{color:var(--good)}.bad{color:var(--bad)}dialog{width:min(1050px,92vw);background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:16px;padding:0}dialog::backdrop{background:#000b}.modal-head{padding:20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between}.close{background:none;border:0;color:var(--ink);font-size:24px}.attempts{padding:20px;max-height:70vh;overflow:auto}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid var(--line)}th{color:var(--muted);font-size:11px;text-transform:uppercase}@media(max-width:700px){.stats{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr}}
</style>
</head>
<body><header><div class="kicker">Pithos · local model laboratory</div><h1>Benchmark Observatory</h1><div class="sub">Complete Ollama and Pi evidence, preserved attempt by attempt. No hidden aggregate, no remote telemetry.</div></header>
<main><section class="stats" id="stats"></section><section class="grid" id="grid"></section></main>
<dialog id="detail"><div class="modal-head"><div><div class="kicker">Campaign evidence</div><b id="detail-title"></b></div><button class="close" onclick="detail.close()">×</button></div><div class="attempts" id="attempts"></div></dialog>
<script>
const fmt=n=>n==null?'—':Number(n).toFixed(3);let campaigns=[];
async function load(){const data=await fetch('/api/campaigns').then(r=>r.json());campaigns=data.items;render()}
function render(){const attempts=campaigns.reduce((n,c)=>n+(c.summary?.attempts||0),0);const passed=campaigns.reduce((n,c)=>n+(c.summary?.passed||0),0);const speeds=campaigns.map(c=>c.summary?.median_decode_tokens_per_second).filter(n=>n!=null);const median=speeds.length?speeds.sort((a,b)=>a-b)[Math.floor(speeds.length/2)]:null;
stats.innerHTML=[['Campaigns',campaigns.length],['Attempts',attempts],['Passed',passed],['Median tok/s',fmt(median)]].map(x=>`<div class="stat"><span class="label">${x[0]}</span><b>${x[1]}</b></div>`).join('');
grid.innerHTML=campaigns.map(c=>{const s=c.summary||{};const rate=Math.round((s.pass_rate||0)*100);return `<article class="card" onclick="openCampaign('${c.campaign_id}')"><div class="model">${c.model}</div><div class="id">${c.campaign_id}</div><div class="bar"><i style="width:${rate}%"></i></div><div class="metrics"><div class="metric"><span class="label">pass rate</span><b class="${rate>=50?'good':'bad'}">${rate}%</b></div><div class="metric"><span class="label">speed</span><b>${fmt(s.median_decode_tokens_per_second)}</b></div><div class="metric"><span class="label">suite</span><b>${c.suite}</b></div></div></article>`}).join('')||'<p>No completed campaign yet.</p>'}
async function openCampaign(id){const data=await fetch(`/api/campaigns/${id}`).then(r=>r.json());document.querySelector('#detail-title').textContent=`${data.manifest.model} · ${id}`;document.querySelector('#attempts').innerHTML=`<table><thead><tr><th>Scenario</th><th>Try</th><th>Result</th><th>Duration</th><th>tok/s</th><th>Error</th></tr></thead><tbody>${data.attempts.map(a=>`<tr><td>${a.scenario_id}</td><td>${a.attempt_number}</td><td class="${a.passed?'good':'bad'}">${a.passed?'PASS':'FAIL'}</td><td>${fmt(a.duration_seconds)}</td><td>${fmt(a.decode_tokens_per_second)}</td><td>${a.error||''}</td></tr>`).join('')}</tbody></table>`;detail.showModal()}
load();
</script></body></html>"""
