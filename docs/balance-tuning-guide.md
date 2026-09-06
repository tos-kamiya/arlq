# 静的バランス調整の分析手順

## このツールで調べること

`arlq-balance-tuner` は、モンスターの食料回復量とステージ別の初期出現数を変えた候補を自動プレイで比較する開発用ツールです。候補値は評価中だけ一時的に適用され、`src/arlq/defs.py` は書き換えません。

主な目的は次の2点です。

- ステージと方針ごとのクリア率や序盤餓死率から、難易度を比較する。
- 発見順に倒す方針と状況に応じて順序を変える方針を比較し、討伐順を考える価値があるか調べる。

ここでいう「発見順」は、プレイヤーの視界に個体が初めて入った順です。ゲーム内部の生成順ではありません。各方針は、探索済みの地形、視界に入った個体、接触によって識別済みの種族だけを利用します。

## 1. 設定ファイルを作る

リポジトリのルートで、標準設定をJSONファイルへ出力します。

```bash
uv run -p .venv/bin/python arlq-balance-tuner \
  --write-default-config balance-tuning.json
```

スクリプトエントリーポイントがまだ仮想環境へ反映されていない場合は、モジュールとして実行できます。

```bash
uv run -p .venv/bin/python python -m arlq.balance_tuner \
  --write-default-config balance-tuning.json
```

生成したファイルは、実験ごとにコピーして保存してください。設定ファイル自体が、どの条件で結果を得たかを示す記録になります。

## 2. 最初は小さな設定で所要時間を測る

本評価の前に、前節で作成した標準設定をコピーし、評価数を減らします。

```bash
cp balance-tuning.json balance-tuning-smoke.json
```

次に、`balance-tuning-smoke.json` の該当項目を編集します。以下は設定ファイル全体の例です。これをそのまま `balance-tuning-smoke.json` として保存しても実行できます。

```json
{
  "stages": [1, 2],
  "policies": ["discovery", "nearest", "situational"],
  "max_steps": 500,
  "stalled_steps": 50,
  "early_turn": 100,
  "search": {
    "seed_start": 1,
    "seeds": 2,
    "candidates": 2
  },
  "validation": {
    "seed_start": 100001,
    "seeds": 2,
    "keep": 1
  },
  "final": {
    "seed_start": 200001,
    "seeds": 2,
    "keep": 1
  },
  "jobs": 2,
  "parameters": {
    "feed": {
      "b": {"min": 35, "max": 45, "step": 5}
    },
    "spawn": {
      "1": {
        "a": {"min": 12, "max": 16, "step": 2}
      },
      "2": {
        "a": {"min": 12, "max": 16, "step": 2}
      }
    },
    "max_total_population": {"1": 40, "2": 48}
  },
  "targets": {}
}
```

`stages`、`policies`、`parameters`、`targets` は必須です。これらを省略したJSONを保存すると、`stages must contain 1 and/or 2` などの検証エラーになります。既存の設定を編集する場合は、上の例から `search`、`validation`、`final` の値だけを変更して構いません。

実行する総プレイ数は、おおむね次の式で求められます。

```text
search.candidates × search.seeds × ステージ数 × 方針数
+ validation.keep × validation.seeds × ステージ数 × 方針数
+ final.keep × final.seeds × ステージ数 × 方針数
```

標準設定は7,400プレイです。マップ生成やターン上限までの移動をプレイごとに行うため、先に小規模実行の所要時間を測り、その結果から本評価の規模を決めます。

```bash
uv run -p .venv/bin/python python -m arlq.balance_tuner \
  --config balance-tuning-smoke.json \
  --output balance-results-smoke
```

出力ディレクトリ内のファイルは同じ名前で上書きされます。再実行するときは新しい出力先を指定するか、以前の結果を退避してください。現在の実装は中断した実行の再開には対応していません。

## 3. 探索範囲を決める

`parameters.feed` は種族ごとの食料回復量、`parameters.spawn` はステージごとの初期出現数です。各値に `min`、`max`、`step` を指定します。

```json
"parameters": {
  "feed": {
    "b": {"min": 30, "max": 50, "step": 5},
    "d": {"min": 30, "max": 50, "step": 5}
  },
  "spawn": {
    "1": {
      "a": {"min": 10, "max": 18, "step": 2},
      "b": {"min": 5, "max": 9, "step": 1}
    },
    "2": {
      "a": {"min": 10, "max": 18, "step": 2},
      "b": {"min": 5, "max": 9, "step": 1}
    }
  },
  "max_total_population": {"1": 40, "2": 48}
}
```

現在の探索で指定できる範囲値は整数です。整数の `population` は配置数を意味します。小数の `population` が表す出現確率は、この初期版の探索対象ではありません。

食料は種族定義として全ステージで共有されます。たとえば `b` の食料を探索する場合、`stages` に `[1, 2]` を指定して両ステージへの影響を確認するのが基本です。ボス、宝箱、敵の強さ、LP上限、再出現間隔、地形は変更しません。

`max_total_population` は、探索対象外のモンスターや同行者も含む初期配置数の上限です。上限を超えたランダム候補は評価対象から除外されます。盤面が過密になる設定は、処理時間と移動不能の両方を増やすため避けます。

## 4. 比較方針を選ぶ

`policies` には次の名前を指定できます。

| 設定値 | 方針 | 見る目的 |
| --- | --- | --- |
| `discovery` | 発見順 | 単純な討伐順の基準 |
| `nearest` | 近距離優先 | 移動距離だけで生じた差の確認 |
| `situational` | 状況判断 | LP、距離、育成、食料、装備を考慮した順序選択 |
| `food` | 食料優先 | 食料回復を主軸にした固定方針への偏りの確認 |
| `growth` | 育成優先 | 経験値と敵レベルを主軸にした固定方針への偏りの確認 |

通常は5方針すべてを残します。少なくとも `discovery` と比較したい方針を含めないと、対応付きのクリア率差を計算できません。全方針は共通の未探索地点選択規則を使います。

## 5. 目標範囲を設定する

`targets` が空のとき、候補は方針差と現行値からの変更量によって比較されます。「適切な難易度」の範囲が決まっている場合は、ステージと方針を組み合わせたキーで条件を指定します。

```json
"targets": {
  "clear_rate": {
    "stage1:situational": {"min": 0.25, "max": 0.55},
    "stage2:situational": {"min": 0.15, "max": 0.40},
    "stage1:discovery": {"min": 0.10, "max": 0.50},
    "stage2:discovery": {"min": 0.05, "max": 0.35}
  },
  "early_starvation_rate_max": {
    "stage1:situational": 0.20,
    "stage2:situational": 0.30
  }
}
```

この数値は記法の例です。ゲームの承認済み目標値ではありません。先に現行値の結果を取り、その分布と意図するプレイヤー体験から範囲を決めてください。

候補の順位は次の順で決まります。

1. `targets` から外れた量が小さい。
2. `situational − discovery` の平均クリア率差が大きい。
3. `nearest − discovery` の平均クリア率差が大きい。
4. 現行値からの食料量・出現数の変更合計が小さい。

`nearest − discovery` が大きい場合は、状況判断ではなく発見順方針の余分な移動が差を作っている可能性があります。順位だけで採用せず、後述の比較手順で内容を確認します。

Stage 2を基準に共通モンスターの条件を探索し、`situational`を優先したい場合は、リポジトリルートの`balance-tuning-situational.json`を使えます。この設定は`a`と`b`だけを両ステージで調整し、Stage 1のDとStage 2のFは現行値のまま固定します。`a`、`A`、`b`、`c`、`C`はリスポーンなし、Cの剣は6回の壁破壊として評価します。

```bash
uv run -p .venv/bin/python python -m arlq.balance_tuner \
  --config balance-tuning-situational.json \
  --output balance-results-situational
```

探索結果では、`paired_deltas`の`stage2:situational-discovery`を最初に確認し、正の差が複数のシード集合で再現する候補だけを残します。

## 6. シード集合を分離する

`search`、`validation`、`final` は、それぞれ粗探索、候補の絞り込み、最終比較に使います。

- `seed_start`: 連続シードの先頭値
- `seeds`: 使用するシード数
- `candidates`: 粗探索で現行値を含めて生成する候補数
- `keep`: 次の段階へ残す候補数

3段階のシード範囲は重複させないでください。重複がある設定は実行前にエラーになります。勝利したシードだけを選んで使うと難易度評価が偏るため、連続した未選別のシードを使います。

最終結果を見てパラメータ範囲や目標値を変更した場合、その `final` シードは調整に使ったことになります。次の実験では新しい未使用範囲を `final` に割り当てます。

## 7. 本評価を実行する

```bash
uv run -p .venv/bin/python python -m arlq.balance_tuner \
  --config balance-tuning.json \
  --output balance-results-20260906 \
  --random-seed 20260906
```

`--random-seed` はパラメータ候補の生成だけに使います。ゲーム本体は各段階のシードを使います。同じコード、設定ファイル、`--random-seed` なら候補生成と結果を再現できます。

評価は `jobs` 個のプロセスで並列実行できます。CPUコア数やメモリに余裕がある場合は、たとえば次のように指定します。

```bash
uv run -p .venv/bin/python python -m arlq.balance_tuner \
  --config balance-tuning.json \
  --output balance-results-20260906 \
  --jobs 4
```

コマンドラインの `--jobs` は設定ファイルの値より優先されます。`jobs` の既定値は1です。プロセス数を変えても、各プレイのシードと候補は同じで、JSONLの結果は決定的な順序で保存されます。プロセス数を増やしてもマップ生成そのものが速くならない環境では、I/Oやメモリ使用量を見ながら値を下げてください。

フェーズ開始、候補開始、候補完了の進捗は標準エラー出力へ表示されます。結果だけを標準出力へ保存する場合は、次のようにリダイレクトできます。

```bash
uv run -p .venv/bin/python python -m arlq.balance_tuner \
  --config balance-tuning.json \
  --output balance-results > balance-tuning.log
```

現在値は必ず粗探索候補の先頭に含まれます。残りは指定範囲からランダムに生成されます。この実装は候補周辺の局所探索やプロセス並列評価をまだ行わないため、候補数とシード数にほぼ比例して実行時間が増えます。

## 8. 出力を読む

### `report.md`

最初に読む比較レポートです。最終評価へ残った候補について、次を掲載します。

- 候補IDと食料・出現数
- 現行値からの変更量
- ステージ・方針別のクリア率
- 序盤餓死率
- 勝利プレイだけを分母にした歩数と残LPの中央値
- 発見順に対する方針別クリア率差と、対応付きブートストラップ95%区間

### `manifest.json`

再現と監査に使うファイルです。実効設定、候補生成シード、方針版、Gitリビジョンと作業ツリー状態、現行値、候補ID、総プレイ数、所要時間を保存します。

`git.dirty` が `true` の結果を共有するときは、どの未コミット変更を含む実行だったかも記録してください。

### `candidates.jsonl`

1行が1段階・1候補のJSONです。同じ候補IDが `search`、`validation`、`final` に複数回現れることがあります。`phase` で段階を区別します。

- `tuning`: 評価した全パラメータ
- `summary.by_policy_stage`: 方針・ステージ別の集約値
- `summary.paired_deltas`: 発見順に対する対応付きクリア率差
- `change_distance`: 現行値からの変更合計
- `rank_key`: 内部の整列キー。値が辞書順で小さいほど上位

### `runs.jsonl`

1行が候補・段階・シード・ステージ・方針ごとの1プレイです。集約値の原因を調べるときに使います。

主な項目は `end_reason`、`steps`、`lp`、`level`、`battle_losses`、`kills`、`first_kill_turn`、`nominal_feed`、`effective_recovery`、`wasted_recovery`、`discovery_order`、`kill_order`、`item_transitions` です。

`end_reason` は次の値を取ります。

| 値 | 意味 |
| --- | --- |
| `won` | 宝箱を獲得してクリア |
| `lp_depleted` | LP切れ |
| `stalled` | 移動も接触もない状態が `stalled_steps` 継続 |
| `turn_limit` | `max_steps` に到達 |

Smoke設定ではシード数が少ないため、すべてのクリア率が `0.000` になることがあります。これは直ちに「候補がクリア不能」という意味ではありません。まず `runs.jsonl` の `end_reason` を確認し、`turn_limit` が多ければ `max_steps` を増やし、`lp_depleted` が多ければ序盤餓死率、討伐数、食料回復量を確認します。最終的な難易度判断には、Smokeより多い独立シードを使ってください。

`decision_examples.jsonl` は将来の局面分岐診断用に予約されています。現在は空です。「今倒す」と「後回し」のどちらが有利かを同一局面から直接分岐して証明する機能は、まだ実装されていません。

## 9. 候補を比較する

候補の判断は次の順で行います。

1. `report.md` で、両ステージのクリア率と序盤餓死率が目標範囲内か確認する。
2. `situational − discovery` が正で、95%区間が十分狭いか確認する。
3. `nearest − discovery` と比較し、単なる移動距離の差で説明されないか確認する。
4. `food` と `growth` が一方的に強すぎないか確認する。
5. `runs.jsonl` で終了理由、戦闘敗北、回復の無駄、装備遷移、討伐順を調べる。
6. 成績が近い候補では、`change_distance` が小さいものを優先する。

区間が広い、または候補間で順位が頻繁に入れ替わる場合は、最終シード数を増やします。全候補のクリア率が0または1に張り付く場合は、パラメータ範囲、`max_steps`、方針の進行状況を確認してから評価規模を増やします。

クリア率差だけで「討伐順を考える価値がある」と断定することはできません。現在の結果は有限個の固定方針による比較です。具体的な局面については、必要に応じて `arlq-branch-analyzer` や手動再生で補助的に確認します。その場合、分岐解析は完全情報を使い、ビーム探索の `wins / leaves` は通常プレイのクリア率ではないことを明記します。

## 10. 採用前に再確認する

## 再出現ルールを少数シードで比較する

食料モンスターの再出現を止めたときの大まかな傾向だけを確認する場合は、専用の比較コマンドを使います。各条件は同じシード集合で実行されるため、条件間の差を直接比較できます。

```bash
uv run -p .venv/bin/python python -m arlq.respawn_compare \
  --seeds 5 \
  --seed-start 1 \
  --max-steps 1000 \
  --jobs 4 \
  --output respawn-comparison
```

既定では次の5条件を、`discovery`、`nearest`、`situational` の3方針でStage 1/2それぞれ評価します。

| 条件 | 内容 |
| --- | --- |
| `all` | 現在の再出現ルール |
| `no-a` | `a` のみ再出現なし |
| `no-b` | `b` のみ再出現なし |
| `no-weak` | `a`、`A`、`b` を再出現なし |
| `no-core` | `a`、`A`、`b`、`c`、`C` をすべて再出現なし |

結果は `report.md`、`summary.json`、`runs.jsonl` に出力されます。`--seeds` は少数の傾向確認用なので、候補採用の判断には使わず、同じシード範囲で条件を追加した比較や通常の最終評価へ進めます。`--jobs` はプロセス数です。

`a` と `b` の再出現を止め、`b` の食料を増やした影響だけを確認する場合は、条件を絞って `--b-feed` を指定します。

```bash
uv run -p .venv/bin/python python -m arlq.respawn_compare \
  --conditions all no-a-b \
  --b-feed 60 \
  --a-count 20 \
  --b-count 9 \
  --seeds 50 \
  --seed-start 1 \
  --max-steps 1000 \
  --jobs 8 \
  --output respawn-comparison-b60
```

この実験では、`all` は現在の食料値と再出現ルール、`no-a-b` は `a` と `b` の再出現なし・`b` の食料60・両ステージの初期 `a` 数20・初期 `b` 数9として評価されます。`--b-feed`、`--a-count`、`--b-count` は`all`以外の選択した条件に適用されます。その他の初期出現数やゲーム定数は変更しません。各オプションを省略すると現行値のままです。

Stage 1にも `C` を追加して比較する場合は、`--stage1-c-count 1` を付けます。`C` は両条件に同じ数だけ一時追加され、`defs.py` は変更されません。

```bash
uv run -p .venv/bin/python python -m arlq.respawn_compare \
  --conditions all no-a-b \
  --stage1-c-count 1 \
  --b-feed 60 \
  --a-count 20 \
  --b-count 10 \
  --seeds 50 \
  --seed-start 1 \
  --max-steps 1000 \
  --jobs 8 \
  --output respawn-stage1-c1
```

`--stage1-c-count` を付けない実行結果と、付けた実行結果を同じシード範囲で比較してください。`C` の追加は乱数消費と配置を変えるため、個別プレイの完全な対応ではなく、方針間の差と全体傾向を見ます。

`a`、`A`、`b`、`c`、`C`をすべてリスポーンなしにする場合は、`no-core`を指定します。Stage 1にも`C`を出現させる設定と組み合わせる場合は、次のように実行します。

```bash
uv run -p .venv/bin/python python -m arlq.respawn_compare \
  --conditions all no-core \
  --stage1-c-count 1 \
  --b-feed 60 \
  --a-count 20 \
  --b-count 10 \
  --seeds 100 \
  --seed-start 1 \
  --max-steps 1000 \
  --jobs 8 \
  --output respawn-no-core
```

`no-core`では、指定した両ステージの初期配置は維持したまま、討伐後の`a`、`A`、`b`、`c`、`C`だけを再出現させません。`all`との差分を同じシード範囲で確認してください。

現行の`no-core`ルールで、残りのモンスターのリスポーン位置だけを固定する場合は、`no-core`と`checkpoint`を比較します。`checkpoint`では、初期スポーン地点または最後にモンスターへ勝った地点へ戻ります。

`c`または`C`から得る剣で壁を壊せる回数を増やす場合は、`--c-sword-uses`を指定します。この設定は通常の剣と呪いの剣の両方に適用され、`all`以外の条件だけが変更されます。6回に緩和する例:

```bash
uv run -p .venv/bin/python python -m arlq.respawn_compare \
  --conditions all no-core \
  --stage1-c-count 1 \
  --c-sword-uses 6 \
  --b-feed 60 --a-count 20 --b-count 10 \
  --seeds 100 --seed-start 1 --max-steps 1000 --jobs 8 \
  --output respawn-no-core-c-sword6
```

Cのリスポーン停止分を初期配置で補う場合は、`--c-count`で両ステージのC配置数を指定します。この値は`all`以外の条件に適用されます。たとえばCを3体ずつ配置する比較は次のとおりです。

```bash
uv run -p .venv/bin/python python -m arlq.respawn_compare \
  --conditions all no-core \
  --c-count 3 \
  --seeds 100 --seed-start 1 --max-steps 1000 --jobs 8 \
  --output respawn-no-core-c3
```

再出現条件では初期出現数と食料量を変更していません。したがって、クリア率低下が見られた場合は、まず再出現を止めたことによる食料・経験値の総量減少として解釈します。条件差が見えた後に、食料量や出現数を別の実験で調整してください。

## 11. 採用前に再確認する

採用候補を決めても、ツールはゲーム定数を変更しません。変更する場合は `src/arlq/defs.py` に手作業で反映し、次を実施します。

```bash
uv run -p .venv/bin/python python -m compileall src
uv run -p .venv/bin/python python -c "import arlq"
```

さらに、新しい未使用シードで両ステージを再評価し、可能ならGUIとcursesの両方で手動プレイします。プレイヤーに見える食料量や出現傾向を変更した場合は、`README.md` と `README.ja_JP.md` の説明も確認します。

## 結果を解釈するときの制約

- 同じシードでも、出現数が変わると乱数の消費順が変わるため、候補間で完全に同じ配置にはなりません。
- 討伐後の再出現があるため、初期配置数だけでは総食料量を判断できません。
- LP上限を超えた食料は `wasted_recovery` に記録されます。
- 呪われた剣によるLP変化は食料適用後に起きます。食料の実効回復量と最終LP差は一致しない場合があります。
- 敵を倒すと、装備を持たない敵も含めて現在の装備が上書きされます。
- 戦闘敗北による再配置とLP補正を攻略に利用している可能性は、`battle_losses` と個別プレイから確認します。
- 有限の候補、方針、シード、ターン上限による結果であり、最適性やクリア不可能性の証明ではありません。
