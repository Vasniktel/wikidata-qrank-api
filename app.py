import requests as rq
import flask
import os
from pathlib import Path
import csv
import gzip
import json
import tempfile
import shutil
import sched
from threading import Thread, Lock


DATA_DIR = Path(os.environ["DATA_DIR"])
REFRESH_DELAY_MINUTES = int(os.getenv("REFRESH_DELAY_MINUTES", 60))
PORT = int(os.getenv("PORT", 8000))

QRANK_FILE_NAME = "qrank.csv.gz"
DOWNLOAD_URL = f"https://qrank.wmcloud.org/download/{QRANK_FILE_NAME}"
QRANK_FILE_PATH = DATA_DIR / QRANK_FILE_NAME
QRANK_METADATA_PATH = DATA_DIR / "qrank_metadata.json"


app = flask.Flask(__name__)
app.logger.setLevel("INFO")


def load_rank_data():
    app.logger.info("Loading ranking data")

    if not QRANK_FILE_PATH.exists():
        app.logger.info("No ranking found")
        return None

    with gzip.open(QRANK_FILE_PATH, "rt", encoding="utf-8") as f:
        return {el["Entity"]: int(el["QRank"]) for el in csv.DictReader(f)}


def download_data(*, force=False):
    app.logger.info(f"Starting file download ({force=})")

    headers = None
    if not force and QRANK_METADATA_PATH.exists():
        etag = json.load(QRANK_METADATA_PATH.open())["etag"]
        app.logger.info(f"Using existing etag {etag}")
        headers = {"If-None-Match": etag}

    with rq.get(DOWNLOAD_URL, headers=headers, stream=True) as resp:
        app.logger.info(f"Got response status {resp.status_code}")

        resp.raise_for_status()

        if resp.status_code == 304:
            # No new data.
            return False

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_file = Path(tmp_dir) / QRANK_FILE_NAME
            with tmp_file.open("wb") as f:
                for chunk in resp:
                    f.write(chunk)

            shutil.move(tmp_file, QRANK_FILE_PATH)
            etag = resp.headers["etag"]
            json.dump({"etag": etag}, QRANK_METADATA_PATH.open("w"))
            app.logger.info(f"Finished file download ({etag=})")
            return True


refresh_lock = Lock()


def refresh_data_impl(*, force=False, timeout=10):
    if refresh_lock.acquire(timeout=timeout):
        try:
            if download_data(force=force):
                new_data = load_rank_data()
                assert new_data, "Can't load rank data after it is downloaded"
                return new_data
        finally:
            refresh_lock.release()

    return None


rank_data = load_rank_data() or refresh_data_impl(force=True, timeout=-1)


@app.get("/get")
def get_qrank():
    qids = flask.request.args.getlist("qid")
    assert rank_data is not None
    return flask.jsonify({el: rank_data[el] for el in qids if el in rank_data})


@app.put("/refresh")
def refresh_data():
    app.logger.info("Running manual refresh")

    force = flask.request.args.get("force") == "true"

    global rank_data
    if result := refresh_data_impl(force=force):
        rank_data = result
        return flask.jsonify(success=True)
    return flask.jsonify(success=False)


scheduler = sched.scheduler()


def refresh_data_job():
    app.logger.info("Running refresh job")

    global rank_data
    if result := refresh_data_impl():
        rank_data = result
    scheduler.enter(REFRESH_DELAY_MINUTES * 60, 0, refresh_data_job)


scheduler.enter(REFRESH_DELAY_MINUTES * 60, 0, refresh_data_job)


if __name__ == "__main__":
    Thread(target=scheduler.run, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
