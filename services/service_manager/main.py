"""
Запуск:
    uv run python -m services.service_manager.main
"""
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("service_manager")


ServiceName = Literal[
    "api_gateway",
    "vacancy_analytics_service",
    "auth_service",
    "vacancy_collector_service",
    "vacancy_ml_service",
    "vacancy_pipeline_worker",
]


class ServiceConfig:
    def __init__(
        self,
        title: str,
        module: str,
        health_url: str | None,
        port: int | None = None,
        swagger_url: str | None = None,
    ):
        self.title = title
        self.module = module
        self.health_url = health_url
        self.port = port
        self.swagger_url = swagger_url


SERVICES: Dict[ServiceName, ServiceConfig] = {
    "api_gateway": ServiceConfig(
        "API Gateway",
        "api_gateway.main",
        "http://localhost:8000/health",
        port=8000,
        swagger_url="http://localhost:8000/docs",
    ),
    "vacancy_analytics_service": ServiceConfig(
        "Vacancy Analytics Service",
        "services.vacancy_analytics_service.main",
        "http://localhost:8002/health",
        port=8002,
        swagger_url="http://localhost:8002/api/v1/analytics/docs",
    ),
    "auth_service": ServiceConfig(
        "Auth Service",
        "services.auth_service.main",
        "http://localhost:8005/health",
        port=8005,
        swagger_url="http://localhost:8005/api/v1/auth/docs",
    ),
    "vacancy_collector_service": ServiceConfig(
        "Vacancy Collector Service",
        "services.vacancy_collector_service.main",
        "http://localhost:8003/health",
        port=8003,
        swagger_url="http://localhost:8003/api/v1/mining/docs",
    ),
    "vacancy_ml_service": ServiceConfig(
        "Vacancy ML Service",
        "services.vacancy_ml_service.main",
        "http://localhost:8001/health",
        port=8001,
        swagger_url="http://localhost:8001/api/v1/ml/docs",
    ),
    "vacancy_pipeline_worker": ServiceConfig(
        "Vacancy Pipeline Worker",
        "services.vacancy_pipeline_worker.main",
        None,
        port=None,
        swagger_url=None,
    ),
}


app = FastAPI(
    title="Service Manager",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


def _get_proc_store(app_obj: FastAPI) -> Dict[ServiceName, subprocess.Popen]:
    if not hasattr(app_obj.state, "processes"):
        app_obj.state.processes = {}  # type: ignore[attr-defined]
    return app_obj.state.processes  # type: ignore[attr-defined]


def _is_running(proc: subprocess.Popen) -> bool:
    return proc.poll() is None


LOGS_DIR = ROOT / "logs"


def _start_service(name: ServiceName) -> None:
    cfg = SERVICES[name]
    procs = _get_proc_store(app)

    existing: Optional[subprocess.Popen] = procs.get(name)
    if existing and _is_running(existing):
        logger.info("Service %s already running", name)
        return

    LOGS_DIR.mkdir(exist_ok=True)
    log_file = LOGS_DIR / f"{name}.log"

    cmd = [sys.executable, "-m", cfg.module]
    logger.info("Starting service %s: %s (log: %s)", name, " ".join(cmd), log_file)

    fh = open(log_file, "a", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=fh,
        stderr=subprocess.STDOUT,
        shell=False,
    )
    procs[name] = proc


def _stop_service(name: ServiceName) -> None:
    procs = _get_proc_store(app)
    proc = procs.get(name)
    if not proc or not _is_running(proc):
        logger.info("Service %s is not running", name)
        return

    logger.info("Stopping service %s", name)
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        logger.warning("Service %s did not terminate, killing", name)
        proc.kill()


@app.get("/", response_class=HTMLResponse, summary="Панель управления сервисами")
async def service_dashboard() -> str:
    """HTML-дашборд для запуска/остановки/перезапуска микросервисов."""
    import httpx

    procs = _get_proc_store(app)

    # Проверяем health, если он настроен
    async def get_status(name: ServiceName, cfg: ServiceConfig) -> str:
        proc = procs.get(name)
        if not proc or not _is_running(proc):
            return "stopped"
        if not cfg.health_url:
            return "running"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(cfg.health_url)
            return "running" if resp.status_code == 200 else "unhealthy"
        except Exception:
            return "unhealthy"

    statuses: Dict[ServiceName, str] = {}
    for key, cfg in SERVICES.items():
        statuses[key] = await get_status(key, cfg)

    def port_str(c: ServiceConfig) -> str:
        return str(c.port) if c.port is not None else "—"

    def swagger_cell(c: ServiceConfig) -> str:
        if c.swagger_url:
            return f'<a href="{c.swagger_url}" target="_blank" rel="noopener">Swagger</a>'
        return "—"

    rows = []
    for key, cfg in SERVICES.items():
        status = statuses[key]
        rows.append(
            f"""
            <tr data-service="{key}">
              <td>{cfg.title}</td>
              <td>{key}</td>
              <td>{port_str(cfg)}</td>
              <td>{swagger_cell(cfg)}</td>
              <td>
                <span class="status status-{status}">
                  <span class="status-dot"></span>
                  <span class="status-text">{status}</span>
                </span>
              </td>
              <td>
                <button onclick="action('{key}', 'start')">Start</button>
                <button onclick="action('{key}', 'stop')">Stop</button>
                <button onclick="action('{key}', 'restart')">Restart</button>
                <button onclick="showLog('{key}')" style="background:#6366f1;color:white">Logs</button>
              </td>
            </tr>
            """
        )

    html = f"""
    <!doctype html>
    <html lang="ru">
    <head>
      <meta charset="utf-8" />
      <title>Service Manager</title>
      <style>
        body {{
          font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: #0f172a;
          color: #e5e7eb;
          margin: 0;
          padding: 24px;
        }}
        h1 {{
          margin: 0 0 4px 0;
        }}
        .toolbar {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 16px;
          gap: 12px;
        }}
        .toolbar-actions {{
          display: flex;
          gap: 10px;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          background: #020617;
          border-radius: 8px;
          overflow: hidden;
        }}
        th, td {{
          padding: 12px 16px;
          border-bottom: 1px solid #1f2937;
        }}
        th {{
          text-align: left;
          background: #111827;
        }}
        tr:last-child td {{
          border-bottom: none;
        }}
        button {{
          margin-right: 8px;
          padding: 8px 16px;
          border-radius: 6px;
          border: none;
          cursor: pointer;
          font-size: 14px;
        }}
        button:hover {{
          opacity: 0.9;
        }}
        button:nth-child(1) {{ background: #16a34a; color: white; }}
        button:nth-child(2) {{ background: #dc2626; color: white; }}
        button:nth-child(3) {{ background: #0ea5e9; color: white; }}
        button[disabled] {{
          opacity: 0.4;
          cursor: default;
        }}
        .status {{
          padding: 3px 8px;
          border-radius: 999px;
          font-size: 12px;
        }}
        .status-running {{
          background: rgba(34,197,94,0.15);
          color: #4ade80;
        }}
        .status-stopped {{
          background: rgba(248,113,113,0.15);
          color: #fca5a5;
        }}
        .status-unhealthy {{
          background: rgba(234,179,8,0.15);
          color: #facc15;
        }}
        .status-dot {{
          display: inline-block;
          width: 8px;
          height: 8px;
          border-radius: 999px;
          margin-right: 6px;
          background: currentColor;
        }}
        .status-text {{
          vertical-align: middle;
        }}
        table a {{
          color: #38bdf8;
          text-decoration: none;
        }}
        table a:hover {{
          text-decoration: underline;
        }}
        #toast {{
          position: fixed;
          right: 16px;
          bottom: 16px;
          background: #111827;
          color: #e5e7eb;
          padding: 10px 14px;
          border-radius: 6px;
          box-shadow: 0 10px 25px rgba(0,0,0,0.6);
          opacity: 0;
          transform: translateY(10px);
          transition: opacity 0.15s ease, transform 0.15s ease;
          font-size: 13px;
        }}
        #toast.show {{
          opacity: 1;
          transform: translateY(0);
        }}
        #global-loader {{
          position: fixed;
          left: 50%;
          top: 16px;
          transform: translateX(-50%);
          padding: 6px 10px;
          border-radius: 999px;
          background: rgba(15,23,42,0.95);
          color: #e5e7eb;
          font-size: 12px;
          display: none;
          align-items: center;
          gap: 8px;
        }}
        #global-loader .spinner {{
          width: 14px;
          height: 14px;
          border-radius: 999px;
          border: 2px solid #1f2937;
          border-top-color: #38bdf8;
          animation: spin 0.8s linear infinite;
        }}
        @keyframes spin {{
          to {{ transform: rotate(360deg); }}
        }}
      </style>
    </head>
    <body>
      <div class="toolbar">
        <div>
          <h1>Service Manager</h1>
          <p>Управление backend‑сервисами.</p>
        </div>
        <div class="toolbar-actions">
          <button onclick="startAll()">Start all</button>
          <button onclick="stopAll()">Stop all</button>
        </div>
      </div>
      <div id="global-loader">
        <div class="spinner"></div>
        <span>Выполняю действие...</span>
      </div>

      <table id="services-table">
        <thead>
          <tr>
            <th>Service</th>
            <th>Key</th>
            <th>Port</th>
            <th>Swagger</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>

      <div id="toast"></div>

      <div id="log-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:100;padding:40px;overflow:auto" onclick="if(event.target===this)this.style.display='none'">
        <div style="max-width:900px;margin:0 auto;background:#0f172a;border-radius:10px;padding:20px;position:relative">
          <h3 id="log-modal-title" style="margin:0 0 12px 0">Logs</h3>
          <button onclick="document.getElementById('log-modal').style.display='none'" style="position:absolute;top:12px;right:16px;background:#334155;color:white;border-radius:6px;padding:4px 12px;font-size:14px">✕</button>
          <pre id="log-modal-body" style="background:#020617;padding:14px;border-radius:6px;overflow:auto;max-height:70vh;font-size:13px;white-space:pre-wrap;word-break:break-all"></pre>
        </div>
      </div>

      <script>
        function setButtonsDisabled(disabled) {{
          const table = document.getElementById('services-table');
          if (!table) return;
          const buttons = table.querySelectorAll('button');
          buttons.forEach(b => b.disabled = disabled);
        }}

        function setRowLoading(name, loading) {{
          const row = document.querySelector('tr[data-service="' + name + '"]');
          if (!row) return;
          if (loading) {{
            row.classList.add('loading');
          }} else {{
            row.classList.remove('loading');
          }}
        }}

        function showGlobalLoader(show) {{
          const el = document.getElementById('global-loader');
          if (!el) return;
          el.style.display = show ? 'flex' : 'none';
        }}

        async function action(name, op) {{
          try {{
            showGlobalLoader(true);
            setButtonsDisabled(true);
            setRowLoading(name, true);
            const resp = await fetch('/api/service/' + name + '/' + op, {{ method: 'POST' }});
            const data = await resp.json();
            showToast(data.detail || 'OK');
            setTimeout(() => window.location.reload(), 1200);
          }} catch (e) {{
            showToast('Ошибка: ' + e);
            showGlobalLoader(false);
            setButtonsDisabled(false);
            setRowLoading(name, false);
          }}
        }}

        async function startAll() {{
          try {{
            showGlobalLoader(true);
            setButtonsDisabled(true);
            const resp = await fetch('/api/services/start_all', {{ method: 'POST' }});
            const data = await resp.json();
            showToast(data.detail || 'OK');
            setTimeout(() => window.location.reload(), 1500);
          }} catch (e) {{
            showToast('Ошибка: ' + e);
            showGlobalLoader(false);
            setButtonsDisabled(false);
          }}
        }}

        async function stopAll() {{
          try {{
            showGlobalLoader(true);
            setButtonsDisabled(true);
            const resp = await fetch('/api/services/stop_all', {{ method: 'POST' }});
            const data = await resp.json();
            showToast(data.detail || 'OK');
            setTimeout(() => window.location.reload(), 1000);
          }} catch (e) {{
            showToast('Ошибка: ' + e);
            showGlobalLoader(false);
            setButtonsDisabled(false);
          }}
        }}

        async function showLog(name) {{
          try {{
            const resp = await fetch('/api/service/' + name + '/log');
            const data = await resp.json();
            document.getElementById('log-modal-title').textContent = 'Logs: ' + name;
            document.getElementById('log-modal-body').textContent = data.log || '(пусто)';
            document.getElementById('log-modal').style.display = 'block';
          }} catch (e) {{
            showToast('Ошибка: ' + e);
          }}
        }}

        function showToast(msg) {{
          const el = document.getElementById('toast');
          el.textContent = msg;
          el.classList.add('show');
          setTimeout(() => el.classList.remove('show'), 2500);
        }}
      </script>
    </body>
    </html>
    """
    return html


@app.get("/api/service/{name}/log", summary="Лог сервиса")
async def service_log(name: ServiceName, tail: int = 200):
    """Возвращает последние строки лог-файла сервиса."""
    log_path = LOGS_DIR / f"{name}.log"
    if not log_path.exists():
        return {"log": "(лог-файл ещё не создан)"}
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return {"log": "\n".join(lines[-tail:])}
    except Exception as e:
        return {"log": f"(ошибка чтения: {e})"}


@app.post("/api/service/{name}/{op}", summary="Управление отдельным сервисом")
async def service_action(name: ServiceName, op: Literal["start", "stop", "restart"]):
    """Запускает, останавливает или перезапускает указанный сервис."""
    if name not in SERVICES:
        raise HTTPException(status_code=404, detail="unknown service")

    if op == "start":
        _start_service(name)
        msg = f"Service {name} start requested"
    elif op == "stop":
        _stop_service(name)
        msg = f"Service {name} stop requested"
    else:
        _stop_service(name)
        _start_service(name)
        msg = f"Service {name} restart requested"

    return {"detail": msg}


@app.post("/api/services/start_all", summary="Запуск всех сервисов")
async def service_start_all():
    """Запускает все зарегистрированные сервисы."""
    for name in SERVICES.keys():
        _start_service(name)
    return {"detail": "All services start requested"}


@app.post("/api/services/stop_all", summary="Остановка всех сервисов")
async def service_stop_all():
    """Останавливает все запущенные сервисы."""
    for name in SERVICES.keys():
        _stop_service(name)
    return {"detail": "All services stop requested"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.service_manager.main:app", host="localhost", port=8010, reload=True)

