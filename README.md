# weather-pipeline

![CI](https://github.com/xyu16x/weather-pipeline/actions/workflows/ci.yml/badge.svg)

Open-Meteo の時間別気象データを取得し、DuckDB に載せて dbt で日次マートまで作る小さなデータパイプライン。
データエンジニアリングの基本(取得 → 生データ保存 → ロード → 変換 → テスト)を一通り手を動かして学ぶための個人プロジェクトです。

- 開始: 2026年11月
- 目的: ELT の流れと、冪等性・リトライ・データ品質テストを自分で実装して理解する

## 構成

```
Open-Meteo Archive API
  └─ fetch.py   取得(リトライ+指数バックオフ)→ data/raw/*.json に生のまま保存
      └─ load.py   取得期間を決定(DB の続きから / 期間指定)→ DuckDB raw.weather_hourly へ INSERT OR REPLACE(冪等)
          └─ dbt   staging(整形) → marts(地点×日、地点×月の集計) + seed で地点名の名寄せ + テスト
```

## 使い方

```bash
pip install -r requirements.txt
pip install -e .

# 初回: 期間を指定して取得 + ロード
python -m pipeline.load --start 2026-11-01 --end 2026-11-15

# 2回目以降: DB の続きから自動で取得(確定値が出るまで約5日遅らせる)
python -m pipeline.load

# 欠損日の穴埋め(バックフィル)
python -m pipeline.load --start 2026-11-05 --end 2026-11-05

# 変換とテスト(seed → モデル → テストを依存順に実行)
cd dbt_project
export DBT_PROFILES_DIR=.
dbt build

# Python 側のテスト(ネットワーク不要。src は pytest.ini で読み込み済み)
cd .. && pytest
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
- **データ品質テスト**: 気温レンジ、地点×日・地点×月の一意性、名寄せ漏れ、not null。
- 欠損値(NULL)はそのまま保持し、`temperature_obs_count` で観測数を見えるようにしている。
  月次マートでは `day_count` で月内のデータ日数を出し、日付の欠損に気づけるようにしている。
- **テストで下流を止める**: `dbt run` → `dbt test` ではなく `dbt build` を使う。
  上流のテストが失敗すると下流のマートは作り直されない(SKIP)ため、
  名寄せ漏れなどの不正なデータがマートまで流れない。マートは前回成功時の状態のまま残る
  (「新しいが誤ったデータ」より「古いが正しいデータ」を優先する)。
- **名寄せは inner join**: 未登録の地点を `left join` でマートに残す案もあるが、
  location_id が NULL の行が混ざり利用者が混乱するため採用しない。
  未登録の地点は `assert_all_locations_aliased` で検知し、`dbt build` で下流を止める。

## 動作確認の状況

| 項目 | 状況 |
|---|---|
| pytest(リトライ・冪等・パース・取得期間の決定) | 実行済み・通過 |
| fixture データでの dbt build(seed / run / test) | 実行済み・通過(CI でも自動実行) |
| 実 API からの取得 | 確認済み(WSL 環境で実行) |

## 進捗と今後

- [x] 手元で実 API に対して初回実行する
- [x] 取得期間の差分化(前回ロード済みの日付以降のみ取得)
- [x] ロード対象を今回取得したファイルのみにする(以前は data/raw/ を毎回全件ロードしていた)
- [x] CI(GitHub Actions で pytest / dbt test を自動実行)
- [x] 地点×月の集計マート(mart_monthly_weather)
- [ ] BigQuery への移行(パーティション・クラスタリングとスキャン量の比較)
- [ ] 日次実行(BigQuery 移行後、状態をクラウドに置いてから)
- [ ] マートを使った可視化 or 簡単な分析クエリ

## データ出典・利用条件

気象データ: [Open-Meteo.com](https://open-meteo.com/) — [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。
無料 API は非商用利用向け。本リポジトリは学習目的の個人利用です。
