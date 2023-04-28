# wikidata-qrank-api
API for selectively querying QRank data

## Description
This is a simple Flask API for selectively querying ranks for wikidata entities. The API uses data [wikidata-qrank](https://github.com/brawer/wikidata-qrank).
It works by periodically querying data from wikidata-qrank and providing it as an API.

## Configuration
Configurations are provided via the following environment variables:
- `PORT` - port number for the API (`8000` by default).
- `DATA_DIR` - directory for storing the ranking data (required).
- `REFRESH_DELAY_MINUTES` - delay in minutes between consecutive refreshes of the ranking data (`60` by default).

## Endpoints
### `/get`
Accepts `GET` requests with wikidata ids to get rankings for. Example usage:
```sh
$ curl "localhost:8000/get?qid=Q1&qid=Q2&qid=Q0"
{"Q1":1,"Q2":2}
```
### `/refresh`
Accepts `PUT` requests and refreshes the ranking data. Example usage:
```sh
$ curl -X PUT "localhost:8000/refresh"
{"success":true}
```
Refresh can fail if another refresh is already running.

## Usage
You can run it manually
```sh
$ pip install -r requirements.txt
$ DATA_DIR=. python app.py
```
or you can use Docker (a volume can be attached to `DATA_DIR` to avoid fetching the data on every run):
```sh
$ docker run --rm -e DATA_DIR=. -p 8000:8000 --name wikidata-qrank-api ghcr.io/vasniktel/wikidata-qrank-api:main
```
