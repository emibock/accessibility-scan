"""CLI interface for accessibility scanner"""

import asyncio
import sys
from pathlib import Path
import click
import yaml
from rich.console import Console
from rich.progress import Progress

from .crawler import Crawler
from .scanner import AccessibilityScanner
from .exporter import ResultExporter


console = Console()


@click.group()
@click.version_option()
def main():
    """Accessibility scanner with Jira-ready exports"""
    pass


@main.command()
@click.option('--config', type=click.Path(exists=True), help='YAML config file')
@click.option('--url', help='Single URL to scan')
@click.option('--crawl/--no-crawl', default=False, help='Crawl to discover pages')
@click.option('--output', type=click.Path(), default='./scan-results', help='Output directory')
def scan(config, url, crawl, output):
    """Run accessibility scan"""

    if not config and not url:
        console.print("[red]Error: Provide --config or --url[/red]")
        sys.exit(1)

    # Load config
    if config:
        with open(config) as f:
            cfg = yaml.safe_load(f)
    else:
        cfg = {"start_url": url, "max_pages": 1}

    asyncio.run(_run_scan(cfg, crawl, output))


async def _run_scan(config: dict, do_crawl: bool, output_dir: str):
    """Run scan async"""
    console.print("[bold blue]Starting accessibility scan...[/bold blue]")

    # Discover URLs
    if do_crawl:
        console.print("[cyan]Crawling to discover pages...[/cyan]")
        crawler = Crawler(config)
        urls = await crawler.crawl()
        console.print(f"[green]Discovered {len(urls)} pages[/green]")
    else:
        urls = [config.get("start_url")]

    # Scan
    console.print(f"[cyan]Scanning {len(urls)} pages...[/cyan]")
    scanner = AccessibilityScanner(config)

    with Progress() as progress:
        task = progress.add_task("[cyan]Scanning...", total=len(urls))

        results = await scanner.scan(urls)
        progress.update(task, completed=len(urls))

    # Export
    console.print("[cyan]Exporting results...[/cyan]")
    exporter = ResultExporter(results, Path(output_dir))
    exporter.export_all()

    # Summary
    summary = exporter.get_summary()
    console.print("\n[bold green]Scan Complete![/bold green]")
    console.print(f"Pages scanned: {summary['total_pages']}")
    console.print(f"Total violations: {summary['total_violations']}")
    console.print(f"\nBy severity:")
    for severity, count in summary['by_severity'].items():
        console.print(f"  {severity.upper()}: {count}")

    console.print(f"\n[bold]Results saved to:[/bold] {output_dir}")
    console.print(f"  - violations.csv (Jira import)")
    console.print(f"  - violations.json (full data)")
    console.print(f"  - violations.md (readable report)")


@main.command()
@click.option('--port', default=5000, help='Port for web UI')
@click.option('--host', default='127.0.0.1', help='Host for web UI')
def web(port, host):
    """Start web UI"""
    from .web_app import app

    console.print(f"[bold blue]Starting web UI on http://{host}:{port}[/bold blue]")
    app.run(host=host, port=port, debug=True)


if __name__ == '__main__':
    main()
