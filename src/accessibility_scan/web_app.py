"""Flask web UI for accessibility scanner"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from threading import Thread

from flask import Flask, jsonify, render_template, request, send_file
import yaml

from .crawler import Crawler
from .scanner import AccessibilityScanner
from .exporter import ResultExporter


app = Flask(__name__,
            template_folder='../../web/templates',
            static_folder='../../web/static')

REPORTS_DIR = Path(__file__).parent.parent.parent / "scan-results"
REPORTS_DIR.mkdir(exist_ok=True)

# In-memory scan tracking
scans = {}


@app.route("/")
def index():
    """Scan history page"""
    # Load past scans from disk
    past_scans = []

    if REPORTS_DIR.exists():
        for scan_dir in sorted(REPORTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not scan_dir.is_dir():
                continue

            metadata_path = scan_dir / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path) as f:
                    metadata = json.load(f)
                    metadata['scan_id'] = scan_dir.name
                    past_scans.append(metadata)

    return render_template("history.html", scans=past_scans)


@app.route("/new")
def new_scan():
    """New scan form"""
    return render_template("index.html")


@app.route("/rerun/<scan_id>")
def rerun_scan(scan_id):
    """Prefill form with previous scan config"""
    metadata_path = REPORTS_DIR / scan_id / "metadata.json"

    if not metadata_path.exists():
        return "Scan not found", 404

    with open(metadata_path) as f:
        metadata = json.load(f)

    return render_template("index.html", config=metadata.get('config', {}))


@app.route("/start-scan", methods=["POST"])
def start_scan():
    """Start new scan"""
    scan_id = uuid.uuid4().hex[:8]

    # Build config from form
    config = {
        "start_url": request.form["start_url"],
        "max_pages": int(request.form.get("max_pages", 50)),
        "headless": True,
    }

    # Auth if provided
    if request.form.get("login_url"):
        config["authentication"] = {
            "login_url": request.form["login_url"],
            "username": request.form.get("username", ""),
            "password": request.form.get("password", ""),
            "username_selector": request.form.get("username_selector", "input[name='username']"),
            "password_selector": request.form.get("password_selector", "input[name='password']"),
            "submit_selector": request.form.get("submit_selector", "button[type='submit']"),
            "success_indicator": request.form.get("success_indicator", ""),
        }

    # Init scan state
    scans[scan_id] = {
        "status": "running",
        "started": datetime.now().isoformat(),
        "progress": 0,
        "message": "Starting scan...",
        "config": config,
        "crawl": request.form.get("crawl") == "on",
    }

    # Start scan in background
    do_crawl = request.form.get("crawl") == "on"
    thread = Thread(target=run_scan, args=(scan_id, config, do_crawl))
    thread.daemon = True
    thread.start()

    return jsonify({"scan_id": scan_id})


@app.route("/api/status/<scan_id>")
def status(scan_id):
    """Get scan status"""
    if scan_id not in scans:
        return jsonify({"error": "Scan not found"}), 404

    return jsonify(scans[scan_id])


@app.route("/results/<scan_id>")
def results(scan_id):
    """Results page"""
    # Check in-memory first
    if scan_id in scans:
        scan = scans[scan_id]
        if scan["status"] != "complete":
            return render_template("progress.html", scan_id=scan_id)
    else:
        # Try to load from disk
        metadata_path = REPORTS_DIR / scan_id / "metadata.json"
        if not metadata_path.exists():
            return "Scan not found", 404

        with open(metadata_path) as f:
            metadata = json.load(f)

        if metadata.get("status") != "complete":
            return "Scan not complete or failed", 404

    # Load results
    results_path = REPORTS_DIR / scan_id / "violations.json"
    if results_path.exists():
        with open(results_path) as f:
            data = json.load(f)
    else:
        data = {"pages": []}

    return render_template("results.html", scan_id=scan_id, data=data)


@app.route("/download/<scan_id>/<filename>")
def download(scan_id, filename):
    """Download result file"""
    allowed = ["violations.csv", "violations.json", "violations.md"]
    if filename not in allowed:
        return "Invalid file", 400

    file_path = REPORTS_DIR / scan_id / filename
    if not file_path.exists():
        return "File not found", 404

    return send_file(file_path, as_attachment=True)


def run_scan(scan_id: str, config: dict, crawl: bool):
    """Run scan in background thread"""
    try:
        # Discover URLs
        if crawl:
            scans[scan_id]["message"] = "Discovering pages..."
            scans[scan_id]["progress"] = 10

            crawler = Crawler(config)
            urls = asyncio.run(crawler.crawl())

            scans[scan_id]["message"] = f"Found {len(urls)} pages, scanning..."
            scans[scan_id]["progress"] = 30
        else:
            urls = [config["start_url"]]

        # Scan
        scans[scan_id]["message"] = "Running accessibility scans..."
        scans[scan_id]["progress"] = 50

        scanner = AccessibilityScanner(config)
        results = asyncio.run(scanner.scan(urls))

        # Export
        scans[scan_id]["message"] = "Generating reports..."
        scans[scan_id]["progress"] = 80

        output_dir = REPORTS_DIR / scan_id
        exporter = ResultExporter(results, output_dir)
        exporter.export_all()
        summary = exporter.get_summary()

        # Complete
        scans[scan_id].update({
            "status": "complete",
            "progress": 100,
            "message": "Scan complete!",
            "completed": datetime.now().isoformat(),
            "summary": summary
        })

        # Save metadata for history
        metadata = {
            "status": "complete",
            "started": scans[scan_id]["started"],
            "completed": datetime.now().isoformat(),
            "summary": summary,
            "config": {
                "start_url": config.get("start_url"),
                "max_pages": config.get("max_pages"),
                "crawl": crawl,
            }
        }

        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

    except Exception as e:
        scans[scan_id].update({
            "status": "failed",
            "message": f"Error: {str(e)}",
            "error": str(e)
        })

        # Save failed metadata
        output_dir = REPORTS_DIR / scan_id
        output_dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "status": "failed",
            "started": scans[scan_id].get("started", datetime.now().isoformat()),
            "completed": datetime.now().isoformat(),
            "error": str(e),
            "config": {
                "start_url": config.get("start_url"),
                "max_pages": config.get("max_pages"),
                "crawl": crawl,
            }
        }

        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)


if __name__ == "__main__":
    app.run(debug=True)
