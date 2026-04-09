import os
import subprocess
from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, request, send_file

import config
import db

app = Flask(__name__)


@app.before_request
def ensure_db():
    db.init_db()


@app.route("/")
def index():
    return send_file("dashboard.html")


@app.route("/log")
def log_page():
    return send_file("log.html")


@app.route("/api/listings")
def get_listings():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    filter_type = request.args.get("filter", "new")

    sort = request.args.get("sort", "newest")
    result = db.get_listings(page=page, per_page=per_page, filter_type=filter_type, sort=sort)

    last_scrape = db.get_last_scrape_time()
    scraper_healthy = False
    if last_scrape:
        last_dt = datetime.fromisoformat(last_scrape)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        settings = db.get_settings()
        local_hour = (now_utc + config.LOCAL_UTC_OFFSET).hour
        if settings["scraper_start_hour"] <= local_hour <= settings["scraper_end_hour"]:
            scraper_healthy = (now_utc - last_dt) < timedelta(hours=2)
        else:
            # Off-hours: healthy if last run was before midnight (within expected gap)
            scraper_healthy = (now_utc - last_dt) < timedelta(hours=10)

    result["last_scrape"] = last_scrape
    result["scraper_healthy"] = scraper_healthy
    return jsonify(result)


@app.route("/api/listings/<listing_id>/acknowledge", methods=["POST"])
def acknowledge_listing(listing_id):
    db.acknowledge(listing_id)
    return jsonify({"ok": True})


@app.route("/api/clear", methods=["POST"])
def clear():
    token = request.args.get("token", "")
    if token != config.CLEAR_TOKEN:
        return jsonify({"error": "forbidden"}), 403
    db.clear_all()
    return jsonify({"ok": True})


@app.route("/api/scrape-logs")
def get_scrape_logs():
    logs = db.get_scrape_logs()
    return jsonify({"logs": logs})


@app.route("/settings")
def settings_page():
    return send_file("settings.html")


@app.route("/api/settings", methods=["GET"])
def get_settings():
    settings = db.get_settings()
    return jsonify(settings)


@app.route("/api/settings", methods=["PUT"])
def put_settings():
    data = request.get_json(force=True)
    errors = []

    neighborhoods = data.get("neighborhoods")
    if not isinstance(neighborhoods, list) or len(neighborhoods) == 0:
        errors.append("neighborhoods must be a non-empty list")
    elif not all(isinstance(n, str) and n.strip() for n in neighborhoods):
        errors.append("each neighborhood must be a non-empty string")

    price_min = data.get("price_min")
    price_max = data.get("price_max")
    if not isinstance(price_min, int) or not isinstance(price_max, int):
        errors.append("price_min and price_max must be integers")
    elif price_min <= 0 or price_max <= 0:
        errors.append("prices must be positive")
    elif price_min >= price_max:
        errors.append("price_min must be less than price_max")

    rooms = data.get("rooms")
    if not isinstance(rooms, list) or len(rooms) == 0:
        errors.append("rooms must be a non-empty list")
    elif not all(isinstance(r, int) and 1 <= r <= 5 for r in rooms):
        errors.append("each room count must be an integer between 1 and 5")

    start_hour = data.get("scraper_start_hour")
    end_hour = data.get("scraper_end_hour")
    if not isinstance(start_hour, int) or not isinstance(end_hour, int):
        errors.append("hours must be integers")
    elif not (0 <= start_hour <= 23) or not (0 <= end_hour <= 23):
        errors.append("hours must be between 0 and 23")
    elif start_hour >= end_hour:
        errors.append("scraper_start_hour must be less than scraper_end_hour")

    if errors:
        return jsonify({"errors": errors}), 400

    db.update_settings(data)
    return jsonify({"ok": True})


@app.route("/api/scrape", methods=["POST"])
def trigger_scrape():
    if db.is_scrape_running():
        return jsonify({"error": "Scrape already running"}), 409
    project_dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.Popen(
        ["python3", "scraper.py"],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return jsonify({"status": "started"})


@app.route("/api/scrape/status")
def scrape_status():
    running = db.is_scrape_running()
    result = {"running": running}
    if not running:
        result["last_completed"] = db.get_last_scrape_time()
    return jsonify(result)


if __name__ == "__main__":
    db.init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
