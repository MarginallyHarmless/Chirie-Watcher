import os
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
        scraper_healthy = (datetime.now(timezone.utc) - last_dt) < timedelta(hours=2)

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


if __name__ == "__main__":
    db.init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
