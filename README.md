# weather-pipeline

Open-Meteo の時間別気象データを取得し、DuckDB に載せて dbt で日次マートまで作る小さなデータパイプライン。
データエンジニアリングの基本(取得 → 生データ保存 → ロード → 変換 → テスト)を一通り手を動かして学ぶための個人プロジェクトです。

- 開始: 2026年11月
- 目的: ELT の流れと、冪等性・リトライ・データ品質テストを自分で実装して理解する

## 構成

```
Open-Meteo Archive API
  └─ fetch.py   取得(リトライ+指数バックオフ)→ data/raw/*.json に生のまま保存
      └─ load.py   取得期間を決定(DB の続きから / 期間指定)→ DuckDB raw.weather_hourly へ INSERT OR REPLACE(冪等)
          └─ dbt   staging(整形) → marts(地点×日の集計) + seed で地点名の名寄せ + テスト
```

## 使い方

```bash
pip install -r requirements.txt

# 初回: 期間を指定して取得 + ロード
PYTHONPATH=src python -m pipeline.load --start 2026-11-01 --end 2026-11-15

# 2回目以降: DB の続きから自動で取得(確定値が出るまで約5日遅らせる)
PYTHONPATH=src python -m pipeline.load

# 欠損日の穴埋め(バックフィル)
PYTHONPATH=src python -m pipeline.load --start 2026-11-05 --end 2026-11-05

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
- **差分取得**: 地点ごとの最新日付のうち最も古い日の翌日から取得する。
  当初は実行日基準で期間を決めていたため、実行間隔が空くと日付が欠損した(11/05, 11/13)。
  最も古い日を起点にすることで、取得に失敗した地点も次回の実行で取り直される。
  他の地点は再取得になるが、INSERT OR REPLACE で重複しない。
- **初回とバックフィル**: 初回は `--start/--end` で期間を明示する(取得範囲をプログラムに勝手に決めさせない)。
  DB が空なのに期間指定がなければ `EmptyTableError` で止める。同じオプションで欠損日の穴埋めもできる。
- **生データ保持**: API レスポンスは加工せず保存。変換は dbt 側で行い、やり直せるようにしている。
- **名寄せ**: 地点表記ゆれ(tokyo / 東京 など)は seed `location_aliases.csv` で吸収。未登録の地点が来たら `assert_all_locations_aliased` が失敗する。
- **データ品質テスト**: 気温レンジ、地点×日の一意性、名寄せ漏れ、not null。
- 欠損値(NULL)はそのまま保持し、`temperature_obs_count` で観測数を見えるようにしている。

## 動作確認の状況

| 項目 | 状況 |
|---|---|
| pytest(リトライ・冪等・パース・取得期間の決定) | 実行済み・通過 |
| fixture データでの dbt seed / run / test | 実行済み・通過 |
| 実 API からの取得 | 確認済み(WSL 環境で実行) |

## 今後(未着手)

- [x] 手元で実 API に対して初回実行する
- [x] 取得期間の差分化(前回ロード済みの日付以降のみ取得)
- [ ] ロード対象を今回取得したファイルのみにする(現状は data/raw/ を全件ロードしている)
- [ ] 日次実行(cron / GitHub Actions)
- [ ] マートを使った可視化 or 簡単な分析クエリ

## データ出典・利用条件

気象データ: [Open-Meteo.com](https://open-meteo.com/) — [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。
無料 API は非商用利用向け。本リポジトリは学習目的の個人利用です。
