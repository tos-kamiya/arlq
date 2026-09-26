# Gameplay Trace Record/Replay — Specification

このドキュメントは、arlq の**システムテスト（結合テスト）**を目的とした、プレイセッションの記録・再現機能に関する仕様である。実装済み(`src/arlq/trace.py` 等)。実装時に確定した詳細・単純化点は11章「実装メモ」を参照。

対象読者は開発者のみ。エンドユーザー向けの機能ではないため、`README.md`/`README-ja_JP.md` には記載しない（`docs/developer.md` から本書へのリンクのみを置く）。

コード中の行番号は仕様策定時点（`arlq` 4.6.3 付近）のものであり、実装時には再確認すること。

## 1. 目的

`tests/` にある関数単位のヘッドレステスト（`update_entities()`/`_step()` を直接呼ぶユニットテスト）ではカバーできない、**実際のプレイセッション全体を通した回帰検出**（ゴールデンマスター的な結合テスト）を可能にする。

想定運用：

1. 人間が GUI またはターミナルモードで実際にプレイし、操作と結果を JSON トレースファイルに記録する。
2. コード変更のたびに、そのトレースファイルの入力を再送してヘッドレスにゲームを再現し、新しいトレースファイルを出力する。
3. 記録時のトレースファイルと再現後のトレースファイルを `diff` 等で比較し、差分があれば挙動が変化したことが分かる。

既存の pytest 単体テスト（`tests/test_headless_rules.py` 等）を置き換えるものではない。

## 2. CLIオプション

既存の `main()`（`src/arlq/arlq.py`）はサブコマンドなしのフラットな `argparse` 構成。この慣習に合わせ、以下のフラグを追加する。

- `--trace-record PATH`
  通常通りゲームを起動（GUI/ターミナルいずれも可。`--stage`/`--seed`/`-T`/`-t`/`-n`/`--lang` 等と併用可）しつつ、プレイヤー操作と結果を `PATH` に記録する。セッション終了時（win/lose/quit）に一度だけ書き出す（後述 9章）。

- `--trace-replay PATH`
  `PATH` のトレースを読み込み、既定ではヘッドレス（ウィンドウ／ターミナル描画なし）で入力を再送してゲームを再現し、`--trace-replay-output OUT_PATH` （省略時は `PATH` の拡張子前に `.replay` を挿入した既定名）へ新しいトレースファイルを書き出す。`--seed`/`--stage`/`--rematch` とは併用不可（トレースの `params` を用いる）。

- `--trace-replay-watch`
  `--trace-replay` と併用。人間が目視確認できるよう、再現中も実際のUI（`--terminal` の有無に従い pyglet/blessed）へ描画する。入力の取得元はどちらのモードでも同じ（後述 8章）。

## 3. 記録対象の範囲

- **記録するキー操作は方向キー `"U"`/`"D"`/`"L"`/`"R"` と終了キー `"Q"` のみ**（文字列で記録。dx/dy のような数値タプルは使わない）。
- ステージ選択画面（`select_stage()`）とゲームオーバー後の画面（`input_alphabet()` によるマップ／シード表示キー）の操作は記録・再現の対象外。
  - ステージ番号とシードは `params.stage`/`params.seed` に記録するので、`--stage 3` を CLI で指定した場合でも、選択画面で `3` を選んだ場合でも、**同一のトレースファイル**になる。
  - 再現時、`select_stage()` に到達したら `params.stage` の値から選択に必要な入力を**合成**する。両フロントエンドの `select_stage()` は数字キーによる直接選択をサポートしているため、矢印操作の再現は不要で、対応する数字キー入力を合成すれば足りる（正確なキー列は実装時に両フロントエンドの `select_stage()` 実装で確認）。
  - 再現ループはゲームが win/lose/quit のいずれかで終了した時点で即座に打ち切り、ゲームオーバー画面には一切入らない。
- メッセージ文言（`tr()` で翻訳された表示テキスト）は一切記録しない（今後調整される可能性があるため）。

## 4. トレースファイル構造

```jsonc
{
  "schema_version": 2,
  "arlq_version": "4.6.3",
  "recorded_at": "2026-09-22T12:34:56+09:00",
  "params": {
    "stage": 1,
    "seed": "v4.6.3-Tn-1-1234567890",
    "large_torch": true,
    "narrower_corridors": false,
    "lang": "ja"
  },
  "turns": [
    {
      "turn": 1,
      "input": "R",
      "player": { "lp": 90, "level": 1, "attack": 3 },
      "wall": null,
      "contact": null,
      "expired": [],
      "world": []
    },
    {
      "turn": 2,
      "input": "U",
      "player": { "lp": 90, "level": 1, "attack": 3 },
      "wall": { "result": "blocked" },
      "contact": null,
      "expired": [],
      "world": []
    },
    {
      "turn": 3,
      "input": "L",
      "player": { "lp": 90, "level": 2, "attack": 4 },
      "wall": null,
      "contact": { "type": "monster", "id": "b2", "outcome": "win" },
      "expired": [],
      "world": []
    },
    {
      "turn": 40,
      "input": "R",
      "player": { "lp": 70, "level": 3, "attack": 9 },
      "wall": null,
      "contact": null,
      "expired": [],
      "world": [
        { "type": "respawn", "kind": "monster", "id": "a", "at": [12, 5] }
      ]
    },
    { "turn": 41, "input": "Q" }
  ],
  "final": { "outcome": "quit", "turns": 41 }
}
```

`--trace-record` の出力と `--trace-replay` の出力は**同一スキーマ**にする（フィールドの有無で常にdiffが出るような差異を作らない。10章参照）。

`"Q"` 入力のターンは、ゲーム状態の変化がないため `input` のみを記録する（`player`/`wall`/`contact`/`expired`/`world` は付与しない）。

### `params`

CLI引数または選択画面で実際に確定した値（起動時に生成された実シードを含む。ユーザーが `--seed` を省略した場合でも、実際に使われたシードを記録する）。

### `turns[].player`

- `lp`：`Player.lp`。
- `level`：`Player.level`。
- `attack`：実効攻撃力。`defs.current_player_attack(player, stage_num)`（`defs.py:407-428`）をそのまま用いる。`level`・`item`（剣/毒アイテム）・ステージ3固有フラグ（`STAGE3_K_FLAG`、Javelin エルフ同行ボーナス）を織り込んだ値。戦闘判定はこの値と `defs.monster_level()`（`defs.py:204-205`）の**決定的な整数比較**であり、乱数は使わない（`arlq.py:432-502` 等）。

### `turns[].wall`

方向キー入力で「壁または通常移動不可のタイル」へ進もうとした場合のみ非null（`arlq.py:372-394`、`game_engine.py:264-290` 相当）：

- `{"result": "blocked"}` — 進めなかった。
- `{"result": "pegasus_phase"}` — Pegasus（`p`）companion 同行中に、壁越しへ跳躍して進んだ（`arlq.py:376-384`）。
- `{"result": "sword_break", "item_uses_left": N}` — 剣アイテム（`ITEM_SWORD_X1_5`/`ITEM_SWORD_CURSED`）で壁を破壊して進んだ（`arlq.py:385-394`、`game_engine.py:284-289`）。`item_uses_left` はこの行動後に残った使用回数。

### `turns[].contact`

プレイヤーが今回の移動で接触した結果。発生時のみ非null：

- モンスター：`{"type": "monster", "id": "b2", "outcome": "win" | "lose", "respawn_to": [x, y]}`
  `id` は `defs.monster_type_key()` 形式（char＋empowered、例 `"b2"`）。`respawn_to` は `outcome: "lose"` のときのみ、敗北によるプレイヤーのリスポーン先座標（`arlq.py:464-468`）。
- エルフ系ゲートキーパー（`H` 等、stage3では `I`/`J`/`K`/`H`）：`{"type": "monster", "id": "H", "outcome": "granted" | "refused"}`
  条件成立・不成立は接触処理コード自身の分岐（`arlq.py:442-450`、`game_engine.py` の対応箇所）が既に判定しているので、その分岐の中で `outcome` をそのまま設定する。トレース機能側で条件を再解釈・再現する必要はない。
- 同行者：`{"type": "companion", "id": "p"}`
  同行者に勝敗の概念はなく、接触すれば常に合流する（`arlq.py:420-431`）。
- 宝箱：`{"type": "treasure", "id": "TD", "collected": true | false}`
  `collected: false` は、対応するボスが未撃破でロックされたまま接触した場合（`arlq.py:414-419`）。
- 階段（Stages 3 and 4 only）：`{"type": "stairs", "from_floor": 0, "to_floor": 1}`（`game_engine.py:572-591`）。

### `turns[].expired`

そのターンで解決した「効果切れ」イベントのリスト（0件以上）：

- `{"type": "companion_departed", "id": "p"}` — `karma >= companion.tribe.durability` により同行者が離脱（`arlq.py:506-510`、`CompanionTribe` の `durability`: `l`=1, `n`=10, `o`=20, `p`=5、`defs.py:324-329`）。
- `{"type": "item_expired", "item": "c", "reason": "depleted" | "overwritten" | "lost_on_defeat"}`
  剣アイテムの `item_uses` が0になった（`depleted`）、新しいアイテムで上書きされた（`overwritten`）、敗北でクリアされた（`lost_on_defeat`）。

  **補足（毒状態について）**：現行コードに「毒の残りターン数」という独立カウンタは存在しない。`ITEM_POISONED` は他アイテムに上書きされるか敗北でクリアされるまで持続するだけの通常アイテムなので、「毒が切れた」は `item_expired`（`reason: "overwritten"` または `"lost_on_defeat"`）として自然に表現される。

### `turns[].world`

プレイヤーの操作結果（`contact`）とは独立した、ワールド側の自動リスポーンイベント（`MONSTER_RESPAWN_INTERVAL`＝65ターンごとの判定、`arlq.py:145-152, 656-664`、`game_engine.py:594-618`）。0件以上：

- `{"type": "respawn", "kind": "monster" | "companion", "id": "b2", "at": [x, y]}`
  `id` は empowered を保持した `monster_type_key()` 形式（リスポーン時に empowered は保持される前提）。`kind: "companion"` の場合は単一char（例 `"p"`、companion に empowered の概念はない）。
- stage3 の場合はフロアをまたいだキュー（`queue: Counter[Tuple[int,str]]`）のため `floor` を追加：`{"type": "respawn", "kind": "monster", "id": "W", "at": [3, 8], "floor": 1}`。

### `final`

```jsonc
{ "outcome": "win" | "lose" | "quit" | "unfinished", "turns": N }
```

`"unfinished"` は、壊れた／人為的に切り詰められたトレースを再現した場合にのみ理論上発生しうる異常系の値としてスキーマ上残す（通常運用では実質発生しない。9章参照）。

## 5. 決定性

乱数源は独自シードLCG（`utils.MyRandom`、シングルトン `rand`）のみで、`main()` で一度 `rand.set_seed(seed)` されるのみ（`arlq.py:815` 付近）。戦闘判定は `current_player_attack() < monster_level()` の決定的な整数比較であり、乱数は使わない。同一シード＋同一入力列であれば理論上完全に再現可能。

**将来コアロジックに非決定的な処理（`os.urandom`、実行時 `time.time()` 依存の分岐など）が混入しないこと**が本機能の前提であり、維持すべき制約として明記しておく。

## 6. バージョニング

`arlq_version` をヘッダに記録する。再現時に現在バージョンと異なれば警告のみ表示し、エラーにはしない。バランス調整（数値定数の変更）由来の差分は、正常な差分として diff に現れる想定。`schema_version` は本仕様のフォーマット変更に備える。

## 7. アーキテクチャ方針

`update_entities()`（`arlq.py`）／`_step()`（`game_engine.py`）はターンごとに必要な材料（`effect`, `contact_happened`, `tribes_to_be_respawned`、呼び出し前後の `player`/`entities`）を既に持っている。ここに最小限のコールバック引数（例：`on_turn_result(input, pre_player, post_player, effect, contact_happened, ...)`）を追加し、`run_game()` 側から任意で渡せるようにする。これが最も小さく確実な変更であり、`tests/test_headless_rules.py` が既に使っている呼び出し方（`update_entities()`/`_step()` を直接叩く）とも整合する。

record/replay は、この共通コールバックに加えて**入力ソース**と**描画先**という2つの独立した差し替えポイントだけで実現する（`run_game()` 自体のロジックは変更しない・複製しない）：

- 入力ソース：`RealInput`（既存の `PygletUI`/`BlessedUI` そのまま、人間のキー入力）／`TraceInput`（トレースファイルから読み込んだ `"U"/"D"/"L"/"R"/"Q"` の列を、あたかも実際に押されたかのように順に返す。`select_stage()` 到達時は3章の通り `params.stage` から合成した入力を返す）。
- 描画先：実際のUI（pyglet/blessed）／no-op UI（`draw_stage()` が何もしない、高速ヘッドレス用）。

| モード | 入力ソース | 描画先 |
|---|---|---|
| 通常プレイ | 実UI | 実UI |
| `--trace-record` | 実UI | 実UI（記録は横のコールバックから取得） |
| `--trace-replay`（既定） | `TraceInput` | no-op |
| `--trace-replay-watch` | `TraceInput` | 実UI |

## 8. 再現（replay）の終了状態

“quit”（Q/ESCキー）は win/lose と同格の正式な終了状態として扱う。

- 記録されたトレースは、常に「その入力列をちょうど使い切ったところでゲームが終わる」形で完結している（人間の実プレイは必ず win／lose／quit のいずれかで終わり、quit で終えた場合もそのキー操作自体が `turns` の最後の要素として記録されるため）。
- 再現側が同じ入力列をそのまま流し込む限り、ゲームロジックが変わっていなければ最後の入力を読み込んだ瞬間に必ずゲームが終了し、入力の消費とゲーム終了は一致する。
- ゲームロジックの変更によって記録時より早く win/lose に到達し、記録された入力（末尾の `"Q"` を含む）が余る、という状況は起こり得るが、これは本機能が検出したい「挙動の変化」そのものであり、特別扱いしない。出力トレースの `turns` が入力トレースより短く、`final.outcome` が変化している、という形で自然に diff に現れる。
- したがって、`--trace-replay` は入力過多／入力不足を判定して標準出力に報告する、といった専用ロジックは持たない。差分の検出はすべて、入力トレースファイルと出力トレースファイルの生の diff に委ねる。
- `--trace-replay` の終了コードは、正常に出力トレースを書き出せたか（`0`）／トレースファイルの読み込み失敗やスキーマ非互換などのエラーか（`0` 以外）のみを表す。

## 9. `--trace-record` の書き出しタイミング

セッションが正常終了（win/lose/quit）した時点で、トレース全体を一度にまとめて書き出す。クラッシュ・強制終了時の途中保存（インクリメンタルな書き出し）は対象外とし、その場合トレースファイルは生成されない。

## 10. スコープ外・今後の課題

- ウィンドウリサイズ、ジョイスティック等 GUI 固有のUIイベント（`select_stage()`/`input_direction()` 以外の入力経路）。
- 画面描画（ピクセル・ターミナルのエスケープシーケンス）そのものの一致検証。
- メッセージ文言・翻訳キー単位の比較（3章の通り、文言自体を記録しないため対象外）。
- トレースファイルを `tests/traces/*.json` としてリポジトリにコミットし、pytest から自動実行する仕組み（本ドキュメントのCLI部分が実装された後の別タスク）。
- 実装時に確認が必要な細部：
  - `select_stage()` の数字キー直接選択の正確な挙動（両フロントエンドで）。
  - リスポーン時に empowered 値が実際に保持されるかどうかのコード上の裏付け。
  - `run_game()`/`_step()` へ追加するコールバックの正確なシグネチャ・引数名。

## 11. 実装メモ（Implementation Notes）

本機能は実装済み（`src/arlq/trace.py` の `TraceRecorder`/`ReplayUI`/`load_trace`、
および `arlq.py`/`game_engine.py` 側の計装、`main()` のCLI配線）。3章までで
「実装時に確認が必要」としていた点への回答と、実装上の単純化を記録する。

- **コールバックの実装方式**：単一の汎用コールバックオブジェクトではなく、
  `trace: Optional[TraceRecorder] = None` を `update_entities()`/`_step()` と
  その下位ヘルパー（`respawn_entity()` 呼び出し元、`_resolve_contact()`、
  `_resolve_monster_contact()`、`_defeat_monster()`、`_process_respawn_queue()`
  など）に直接引き回す方式にした。`run_game()`（両方の実装）が
  `begin_turn()`/`set_player()`/`commit_turn()`/`record_quit()`/`set_outcome()`
  を呼び、`update_entities()`/`_step()` 側が `record_wall()`/`record_contact()`/
  `add_expired()`/`add_world_event()` を呼ぶ、という役割分担。既存コードへの
  差分が最小になり、`trace=None`（デフォルト）のときは一切の分岐が増えない。
- **`select_stage()` の再現**：実際にはキー入力の合成を行っていない。
  `--trace-replay` は `params.stage` を直接 `run_game(..., stage_num=params.stage, ...)`
  に渡すため、`select_stage()` 自体が呼ばれない（`ReplayUI.select_stage()` は
  安全のため残してあるが、通常は到達しない）。両フロントエンドとも数字キー
  直接選択に対応しているため挙動として等価であり、フロントエンド固有の
  キーコードに依存しないぶん単純。
- **empowered の respawn 保持**：確認済み。`monster_type_key()` が
  `char`+`empowered` を1文字列に符号化し、リスポーン処理（legacy側の
  `respawn_queue`/`CHAR_TO_TRIBE`、Stage3側の `_process_respawn_queue()`）は
  この文字列から `empowered` を復元して再スポーンするため、保持される。
- **Stage3 の I/J/K/H の outcome**：仕様では一律 granted/refused としていたが、
  実装はコードの実際の分岐に忠実にした。「初回接触かつ無条件で成立する」
  I/J は `outcome: "granted"`。K（Cursed Sword 未取得時）・H（エルフ進捗2未満
  時）・「既に会った」エルフへの再接触は `outcome: "refused"`。一方、条件を
  満たした K/H の成立は、コード上は通常のモンスター戦闘勝利分岐
  （`_defeat_monster()`）にそのまま合流するため、`outcome: "win"` として記録
  される（`id` はエルフの文字そのもの）。
- **legacy Stage 2 の "H"**：現行コードには granted に至る分岐が存在しない
  （常に refused）。したがって legacy 側の H 接触は常に
  `{"type": "monster", "id": "H", "outcome": "refused"}` として記録される。
- **`item_expired` の `reason: "overwritten"`**：新しいアイテムが実際に
  付与されたかどうかに関わらず、`take_monster_item()` 呼び出し前に
  プレイヤーが何らかのアイテムを保持していた場合に発生したものとして
  記録する（新モンスターがアイテムを与えない場合に手持ちが単に失われる
  ケースも含む）。
- **副次的なバグ修正**：`main()` はステージ未指定時、`select_stage()` の解決前に
  シード文字列（`seed_str`、`"v<version>-<flags>-<stage>-<seed>"`）を生成して
  いたため、対話式のステージ選択時は常に stage 0 のまま埋め込まれていた
  （ゲームオーバー画面の `[s]eed` 表示にも影響する既存バグ）。本機能の
  `params.seed` を正しくするため、`run_game()` が stage 解決直後に
  `seed_str` 内の stage 部分を実際の値へ書き換えるよう修正した。
