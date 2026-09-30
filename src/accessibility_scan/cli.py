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
@click.option('--min-severity', type=click.Choice(['minor', 'moderate', 'serious', 'critical'], case_sensitive=False), help='Minimum severity to include in results')
def scan(config, url, crawl, output, min_severity):
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

    asyncio.run(_run_scan(cfg, crawl, output, min_severity))


async def _run_scan(config: dict, do_crawl: bool, output_dir: str, min_severity: str = None):
    """Run scan async"""
    console.print("[bold blue]Starting accessibility scan...[/bold blue]")

    if min_severity:
        console.print(f"[yellow]Filtering: minimum severity = {min_severity.upper()}[/yellow]")

    # Discover URLs
    if do_crawl:
        console.print("[cyan]Crawling to discover pages...[/cyan]")

        last_count = [0]  # Mutable to update from callback

        def crawl_progress(discovered: int):
            if discovered > last_count[0]:
                console.print(f"[dim]  Found {discovered} pages...[/dim]")
                last_count[0] = discovered

        crawler = Crawler(config)
        urls = await crawler.crawl(progress_callback=crawl_progress)
        console.print(f"[green]Discovered {len(urls)} pages[/green]")
    else:
        urls = [config.get("start_url")]

    # Scan
    console.print(f"[cyan]Scanning {len(urls)} pages...[/cyan]")
    scanner = AccessibilityScanner(config)

    with Progress() as progress:
        task = progress.add_task("[cyan]Scanning...", total=len(urls))

        def update_progress(pages_done: int, total: int):
            progress.update(task, completed=pages_done)

        results = await scanner.scan(urls, progress_callback=update_progress)

    # Export
    console.print("[cyan]Exporting results...[/cyan]")
    exporter = ResultExporter(results, Path(output_dir), min_severity=min_severity)
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
@click.argument('config_file', type=click.Path(exists=True))
def validate(config_file):
    """Validate configuration file"""
    console.print(f"[cyan]Validating {config_file}...[/cyan]")

    try:
        with open(config_file) as f:
            config = yaml.safe_load(f)

        errors = []
        warnings = []

        # Required fields
        if not config.get('start_url'):
            errors.append("Missing required field: start_url")

        # URL validation
        start_url = config.get('start_url', '')
        if start_url and not (start_url.startswith('http://') or start_url.startswith('https://')):
            errors.append(f"Invalid start_url: must begin with http:// or https://")

        # max_pages validation
        max_pages = config.get('max_pages')
        if max_pages is not None and (not isinstance(max_pages, int) or max_pages < 1):
            errors.append("max_pages must be a positive integer")
        elif max_pages is not None and max_pages > 500:
            warnings.append(f"max_pages is {max_pages} (>500) - scan may take significant time and resources")

        # Auth validation
        auth = config.get('authentication')
        if auth:
            if not auth.get('login_url'):
                warnings.append("authentication.login_url not set")
            if not auth.get('username'):
                warnings.append("authentication.username not set")
            if not auth.get('password'):
                warnings.append("authentication.password not set")

        # Report results
        if errors:
            console.print("\n[bold red]Validation failed:[/bold red]")
            for error in errors:
                console.print(f"  [red]✗[/red] {error}")
            sys.exit(1)

        console.print("[bold green]✓ Configuration valid[/bold green]")

        if warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for warning in warnings:
                console.print(f"  [yellow]![/yellow] {warning}")

        # Print summary
        console.print("\n[bold]Configuration:[/bold]")
        console.print(f"  Start URL: {config.get('start_url')}")
        console.print(f"  Max pages: {config.get('max_pages', 'unlimited')}")
        console.print(f"  Headless: {config.get('headless', True)}")
        if auth:
            console.print(f"  Authentication: configured")

    except yaml.YAMLError as e:
        console.print(f"[bold red]YAML parsing error:[/bold red]\n{e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


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
