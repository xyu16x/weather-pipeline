# weather-pipeline

Open-Meteo の時間別気象データを取得し、DuckDB に載せて dbt で日次マートまで作る小さなデータパイプライン。
データエンジニアリングの基本(取得 → 生データ保存 → ロード → 変換 → テスト)を一通り手を動かして学ぶための個人プロジェクトです。

- 開始: 2026年11月
- 目的: ELT の流れと、冪等性・リトライ・データ品質テストを自分で実装して理解する

## 構成

```
Open-Meteo Archive API
  └─ fetch.py   取得(リトライ+指数バックオフ)→ data/raw/*.json に生のまま保存
      └─ load.py   DuckDB raw.weather_hourly へ INSERT OR REPLACE(冪等)
          └─ dbt   staging(整形) → marts(地点×日の集計) + seed で地点名の名寄せ + テスト
```

## 使い方

```bash
pip install -r requirements.txt

# 取得 + ロード(直近7日、確定値が出るまで約5日遅らせて取得)
PYTHONPATH=src python -m pipeline.load --days 7

# 変換とテスト
cd dbt_project
export DBT_PROFILES_DIR=.
dbt seed && dbt run && dbt test

# Python 側のテスト(ネットワーク不要)
cd .. && PYTHONPATH=src pytest
```

## 設計メモ

- **冪等性**: `(location, observed_at)` を主キーに INSERT OR REPLACE。再実行しても行は増えない(テスト済み)。
- **リトライ**: 429 / 5xx / 通信エラーのみ指数バックオフ。400系は即失敗(リトライしても直らないため)。
- **生データ保持**: API レスポンスは加工せず保存。変換は dbt 側で行い、やり直せるようにしている。
- **名寄せ**: 地点表記ゆれ(tokyo / 東京 など)は seed `location_aliases.csv` で吸収。未登録の地点が来たら `assert_all_locations_aliased` が失敗する。
- **データ品質テスト**: 気温レンジ、地点×日の一意性、名寄せ漏れ、not null。
- 欠損値(NULL)はそのまま保持し、`temperature_obs_count` で観測数を見えるようにしている。

## 動作確認の状況

| 項目 | 状況 |
|---|---|
| pytest(リトライ・冪等・パース) | 実行済み・通過 |
| fixture データでの dbt seed / run / test | 実行済み・通過 |
| 実 API からの取得 | **未確認**(開発環境から外部通信できなかったため。手元で初回実行して確認する) |

## 今後(未着手)

- [ ] 手元で実 API に対して初回実行する
- [ ] 日次実行(cron / GitHub Actions)
- [ ] 取得期間の差分化(前回ロード済みの日付以降のみ取得)
- [ ] マートを使った可視化 or 簡単な分析クエリ

## データ出典・利用条件

気象データ: [Open-Meteo.com](https://open-meteo.com/) — [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。
無料 API は非商用利用向け。本リポジトリは学習目的の個人利用です。
