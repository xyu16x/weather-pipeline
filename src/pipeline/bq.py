"""BigQuery へのロード。サンドボックス(DML 不可)前提で、日付パーティションの上書きで冪等性を保つ。"""

import json
from collections import defaultdict
from datetime import date, datetime

from google.cloud import bigquery

from . import load

LOCATION = "asia-northeast1"  # 東京リージョン

SCHEMA = [
    bigquery.SchemaField("location", "STRING", mode="REQUIRED"),
    bigquery.SchemaField(
        "observed_at", "DATETIME", mode="REQUIRED"
    ),  # 日本時間(タイムゾーンなし)
    bigquery.SchemaField("temperature_2m", "FLOAT64"),
    bigquery.SchemaField("precipitation", "FLOAT64"),
    bigquery.SchemaField("wind_speed_10m", "FLOAT64"),
    bigquery.SchemaField("source_file", "STRING"),
]


def ensure_table(client: bigquery.Client, table_id: str) -> bigquery.Table:
    """データセットとテーブルがなければ作る(あれば何もしない)。"""
    dataset_id = table_id.rsplit(".", 1)[0]
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = LOCATION
    client.create_dataset(dataset, exists_ok=True)

    table = bigquery.Table(table_id, schema=SCHEMA)
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY, field="observed_at"
    )
    table.clustering_fields = ["location"]
    return client.create_table(table, exists_ok=True)


def load_files_to_bq(client, table_id, files) -> int:
    """ファイルを読み、日付ごとにパーティションを WRITE_TRUNCATE で上書きロードする。"""


def read_rows(files) -> list[tuple]:
    rows = []

    for f in files:
        payload = json.loads(f.read_text(encoding="utf-8"))
        file_rows = load.parse_rows(payload, f.name)
        rows.extend(file_rows)

    return rows


def group_rows_by_date(rows) -> dict[date, list[tuple]]:
    by_date = defaultdict(list)
    for row in rows:
        d = datetime.fromisoformat(row[1]).date()
        by_date[d].append(row)

    return by_date
