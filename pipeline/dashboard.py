import time
import requests
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.live import Live
from rich.layout import Layout

STORE_ID = "STORE_BLR_002"
API_BASE = "http://localhost:8000"
REFRESH  = 3  # seconds between updates

console = Console()

def fetch(endpoint: str) -> dict:
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}

def build_metrics_panel(data: dict) -> Panel:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="bold cyan", width=25)
    table.add_column("Value",  style="bold white")

    visitors   = data.get("unique_visitors",  0)
    purchased  = data.get("purchased",        0)
    conv       = data.get("conversion_rate",  0.0)
    abandon    = data.get("abandonment_rate", 0.0)
    queue      = data.get("queue_depth",      0)

    # colour conversion rate
    conv_pct = f"{conv * 100:.1f}%"
    if conv >= 0.3:
        conv_str = f"[green]{conv_pct}[/green]"
    elif conv >= 0.1:
        conv_str = f"[yellow]{conv_pct}[/yellow]"
    else:
        conv_str = f"[red]{conv_pct}[/red]"

    # colour queue depth
    if queue >= 8:
        queue_str = f"[red]{queue} CRITICAL[/red]"
    elif queue >= 5:
        queue_str = f"[yellow]{queue} WARNING[/yellow]"
    else:
        queue_str = f"[green]{queue}[/green]"

    table.add_row("Unique visitors",    str(visitors))
    table.add_row("Purchased",          str(purchased))
    table.add_row("Conversion rate",    conv_str)
    table.add_row("Abandonment rate",   f"{abandon * 100:.1f}%")
    table.add_row("Queue depth",        queue_str)

    as_of = data.get("as_of", "")
    if as_of:
        try:
            dt = datetime.fromisoformat(as_of)
            as_of = dt.strftime("%H:%M:%S")
        except Exception:
            pass

    return Panel(
        table,
        title=f"[bold yellow]Live Metrics — {STORE_ID}[/bold yellow]",
        subtitle=f"as of {as_of}",
        border_style="yellow"
    )

def build_funnel_panel(data: dict) -> Panel:
    stages = data.get("stages", [])
    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("Stage",       style="bold cyan",  width=20)
    table.add_column("Count",       style="bold white", width=8)
    table.add_column("% of total",  style="green",      width=12)
    table.add_column("Drop-off",    style="red",        width=10)

    for s in stages:
        drop = s.get("dropoff_pct", 0)
        drop_str = f"{drop:.1f}%" if drop > 0 else "-"
        table.add_row(
            s.get("label", ""),
            str(s.get("count", 0)),
            f"{s.get('pct_of_total', 0):.1f}%",
            drop_str
        )

    return Panel(
        table,
        title="[bold blue]Conversion Funnel[/bold blue]",
        border_style="blue"
    )

def build_zone_panel(data: dict) -> Panel:
    zones = data.get("zone_dwell", [])
    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("Zone",       style="bold cyan", width=20)
    table.add_column("Visits",     style="white",     width=8)
    table.add_column("Avg dwell",  style="green",     width=12)

    if not zones:
        table.add_row("No zone data yet", "-", "-")
    else:
        for z in zones:
            table.add_row(
                z.get("zone_id", ""),
                str(z.get("visits", 0)),
                f"{z.get('avg_dwell_sec', 0):.1f}s"
            )

    return Panel(
        table,
        title="[bold magenta]Zone Activity[/bold magenta]",
        border_style="magenta"
    )

def build_anomalies_panel(data: dict) -> Panel:
    anomalies = data.get("anomalies", [])
    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("Type",    style="bold", width=25)
    table.add_column("Severity", width=10)
    table.add_column("Detail",   width=35)
    table.add_column("Action",   width=30)

    for a in anomalies:
        sev = a.get("severity", "INFO")
        if sev == "CRITICAL":
            sev_str = "[red]CRITICAL[/red]"
        elif sev == "WARN":
            sev_str = "[yellow]WARN[/yellow]"
        else:
            sev_str = "[green]INFO[/green]"

        table.add_row(
            a.get("type", ""),
            sev_str,
            a.get("detail", "")[:35],
            a.get("suggested_action", "")[:30]
        )

    return Panel(
        table,
        title="[bold red]Anomalies[/bold red]",
        border_style="red"
    )

def build_health_panel(data: dict) -> Panel:
    stores = data.get("stores", [])
    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("Store",       style="bold cyan", width=20)
    table.add_column("Last event",  style="white",     width=25)
    table.add_column("Lag",         style="white",     width=12)
    table.add_column("Status",      width=12)

    if not stores:
        table.add_row("-", "No events yet", "-", "[yellow]WAITING[/yellow]")
    else:
        for s in stores:
            status = s.get("feed_status", "OK")
            status_str = (
                "[red]STALE[/red]"
                if status == "STALE_FEED"
                else "[green]OK[/green]"
            )
            lag = s.get("lag_minutes")
            lag_str = f"{lag:.1f} min" if lag else "-"
            table.add_row(
                s.get("store_id", ""),
                s.get("last_event_timestamp", "")[:19],
                lag_str,
                status_str
            )

    return Panel(
        table,
        title="[bold green]Health[/bold green]",
        border_style="green"
    )

def build_header() -> Panel:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = Text(justify="center")
    text.append("APEX RETAIL — STORE INTELLIGENCE DASHBOARD\n",
                style="bold yellow")
    text.append(f"Live  •  Refreshing every {REFRESH}s  •  {now}",
                style="dim")
    return Panel(text, border_style="yellow")

def render(metrics, funnel, anomalies, health):
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="top",    size=14),
        Layout(name="middle", size=12),
        Layout(name="bottom", size=8),
    )
    layout["top"].split_row(
        Layout(name="metrics", ratio=1),
        Layout(name="funnel",  ratio=1),
    )
    layout["header"].update(build_header())
    layout["metrics"].update(build_metrics_panel(metrics))
    layout["funnel"].update(build_funnel_panel(funnel))
    layout["middle"].split_row(
        Layout(name="zones",     ratio=1),
        Layout(name="anomalies", ratio=2),
    )
    layout["zones"].update(build_zone_panel(metrics))
    layout["anomalies"].update(build_anomalies_panel(anomalies))
    layout["bottom"].update(build_health_panel(health))
    return layout

def main():
    console.print(
        Panel(
            "[bold yellow]Starting Store Intelligence Dashboard...[/bold yellow]\n"
            f"Connecting to API at {API_BASE}\n"
            "Press Ctrl+C to exit",
            border_style="yellow"
        )
    )
    time.sleep(1)

    with Live(console=console, refresh_per_second=1, screen=True) as live:
        while True:
            metrics   = fetch(f"/stores/{STORE_ID}/metrics")
            funnel    = fetch(f"/stores/{STORE_ID}/funnel")
            anomalies = fetch(f"/stores/{STORE_ID}/anomalies")
            health    = fetch("/health")

            live.update(render(metrics, funnel, anomalies, health))
            time.sleep(REFRESH)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]")