"""BigQuery へのロード。サンドボックス(DML 不可)前提で、日付パーティションの上書きで冪等性を保つ。"""

from __future__ import annotations

from google.cloud import bigquery

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
