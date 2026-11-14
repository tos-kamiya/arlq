# スプライト版のアニメーション導入と GameSession 化の設計メモ

作成日: 2026-11-14

## 状況と目的

`arlq-sprites`（`sprite_funcs.py` の `SpriteUI`）に、ターン制RPGのようなアニメーションや効果を全面的に導入する。そのために、ゲームエンジンを「1手ずつ進めて、起きたことをイベント列で返す」形にし、スプライト版がそれを呼び出して演出する構成に変える。現在は `GameSession` の切り出し、演出用イベント4種の収集、`LegacyHooks` の廃止、初期版 `Presenter` の導入まで実装済み。残りのイベントと演出の作り込みは未実装。

## 決定事項（ユーザーと合意済み）

| 項目 | 内容 |
| --- | --- |
| 方針 | A: 演出だけRPG風にする。ゲームのルール・バランスは変えない（接触の勝敗はすぐ決まり、その結果を演出する）。コマンド選択式の戦闘（方針B）は採らない |
| ステージ6 | プレイヤーがいる階以外で起きたイベントは演出しない |
| 技術基盤 | Python + Pyglet を継続する。問題はフレームワークではなく、エンジンがループを持ち演出を `time.sleep` で止める作りにある。新しい依存ライブラリは追加しない |
| 将来の移行 | `GameSession.step()` が「状態 + イベント列」を返す形を表示側とのつなぎ目にしておけば、将来 Godot や Web で表示側だけを作り直す余地が残る |

## 現状の作り（2026-11-14 時点）

- `GameSession.step()` が1手分のゲーム処理を担当する。`game_engine.run_game()` は入力・描画のループを持つラッパーになった。
- 全UIが `step()` 後にイベントで既存の演出を呼ぶ。文字表示は `presentation.play_turn_events()`、スプライト版は `sprite_fx.Presenter` を経由する。戦闘・バリア・巻き戻し・階移動に対応し、エンジンは演出関数を呼ばない。スプライト版の演出待ちから `time.sleep()` を除去した（文字表示版の待ちは従来どおり）。
- `game_events.py` の `TurnEvents`（wall / contact / expired / world）は引き続きトレース用。演出用の `GameEvent` は別系統で、現在4種を収集する。
- `SpriteUI` はすでに自前で画面更新を回しながら入力を待っている（`_pump`、`input_direction`）。

## 前提

- 入力処理を作り直さない。`pyglet.app.run` への全面移行はせず、「入力 → `step()` → 演出を再生 → 描画」の順に回す方式にする。演出の再生中も既存の `_pump` で画面を回し、キー入力を受け付ける。
- トレースの形式は変えない。`TraceRecorder` は今のまま並行して動かし、演出用イベントは別に集める。
- 既存の演出関数は全UIで使い続けるが、呼び出しはイベント経由に統一した。ターン途中から処理後への演出タイミングの変化は許容する（下記「廃止計画」参照）。

## 1. `GameSession`（新規モジュール `src/arlq/game_session.py`）

`run_game()` のローカル変数（`floors`、`player`、`floor`、`checkpoint`、`queue`、`turn`、`message`、`replay_context`、`game_start_turn`、`loop_anchor_turn`、`has_rewound`、`operation_path`、`loop_trail_*`、トレース用の差分記録など）を、このクラスの属性に移す。

```python
class GameSession:
    def __init__(self, stage_num=3, config=None, *, seed_str="", trace=None,
                 debug_show_entities=False): ...

    # 読み取り用
    phase: Literal["playing", "game_over", "quit"]
    outcome: Literal["win", "lose", "time_up"] | None
    turn: int
    player: d.Player
    floor_index: int
    floor_count: int

    def view(self, view_floor=None, *, map_mode=False,
             farthest_preview=False) -> dict:
        """ui.draw_stage(**kwargs) にそのまま渡せる辞書を返す（今の draw_stage 呼び出し部分を移す）。"""

    def step(self, move, *, repeat=False, auto_repeat_stop=True) -> "TurnResult":
        """1手進める。ローグの危険察知、キー押し続け移動の停止判定、巻き戻し、
        ターン終了時の LP 減少、勝敗判定までを含む。"""

    def quit_check(self) -> bool:
        """Esc が押されたときの「もう詰んでいるか」の判定。True なら確認ダイアログを出す。"""

    def quit(self) -> None:
        """トレースに quit を記録して終了する。"""

    def game_over_message(self) -> str: ...
    def seed_message(self) -> str: ...
```

### `TurnResult`

```python
@dataclass
class TurnResult:
    consumed: bool               # False = 押し続け移動の停止などで、ターンが進まなかった
    events: list[GameEvent]      # 発生順。演出用
    message: tuple[int, str] | None
    stop_repeat: bool            # UI 側でキー押し続け移動を止めるべきか
    floor_before: int
    floor_after: int
```

### UI 側に残すもの

- 表示中の階（Shift で切り替える階層ビュー）、マップモード、到達可能範囲のプレビュー、`(0, 0)` 入力の処理、確認ダイアログの表示。これらはゲームの状態を変えないので、セッションには入れない。
- ゲームオーバー画面のループ。セッションは `view()` とメッセージを作る関数を提供するだけにする。

### `run_game()` はラッパーにする

```python
def run_game(ui, seed_str, ..., stage_num=3):
    s = GameSession(stage_num, config, seed_str=seed_str, trace=trace,
                    debug_show_entities=debug_show_entities)
    view_floor = 0
    while s.phase == "playing":
        ui.draw_stage(**s.view(view_floor, map_mode=..., farthest_preview=...))
        move = ui.input_direction()
        ...  # Esc や階層ビューなど UI だけの処理（今のコードを移す）
        r = s.step(move, repeat=getattr(ui, "input_was_repeat", False), ...)
        if r.stop_repeat: _stop_movement_repeat(ui)
        play_turn_events(ui, r, s.player, stage_num)
        view_floor = r.floor_after
    ...  # ゲームオーバー画面のループ（今のコードを移す）
```

`LegacyHooks` は、エンジンの途中で呼んでいた演出関数（`combat_effect`、`barrier_effect`、`rewind_transition`、`floor_transition`）を束ねる過渡的な仕組みだった。以下の計画に沿って廃止した。

押し続け移動の停止は、当初 `LegacyHooks.stop_movement_repeat` も用意していたが、`TurnResult.stop_repeat` と重複するため削除した（2026-11-14）。`run_game` は `step()` の後に `result.stop_repeat` を見て `ui.stop_movement_repeat()` を呼ぶ。UI 側の処理はフラグを戻すだけで、演出関数は入力を読まないため、ターンの途中で呼んでも後で呼んでも結果は同じ。

### `LegacyHooks` の廃止計画（完了）

`LegacyHooks` は、次の3段階で廃止した。

1. `TurnResult.events` を実装する。この時点では `LegacyHooks` も残し、両方から演出できる状態にする。
2. blessed 版と Pyglet 文字表示版に、`step()` の後でイベント列を見て既存の演出関数を呼ぶ小さな関数を用意する（`run_game` 内、またはそれぞれの UI モジュール内）。
   - `Combat` → `draw_combat_effect(positions, won)`
   - `BarrierHit` → バリア上のプレイヤー位置で `draw_combat_effect(pos, False)`
   - `Rewound` → `draw_rewind_transition(message)`
   - `FloorChanged` → `draw_floor_transition(kind, player, exit_point)`
3. `run_game` が `hooks` を渡さないようにし、`GameSession` から `hooks` 引数、`LegacyHooks` クラス、`_process_multi_floor_turn` の `combat_effect=` / `barrier_effect=` 引数を削除する。

進捗（2026-11-14）: 廃止計画の手順 1 として、`TurnResult.events` と
`Combat` / `BarrierHit` / `Rewound` / `FloorChanged` の収集を実装した。
この段階では `LegacyHooks` も既存のタイミングで呼んでいた。`Entity.uid` と `EntityRef`
も追加し、戦闘相手の座標・移動前の味方位置・戦闘による LP 差分を保存する。
`step(collect_events=False)` で収集を無効にでき、収集の有無によるトレースと
乱数状態の一致をテストする。移動・出現など、下記の残りのイベントは未実装。

手順 2 では文字表示 UI を `uses_event_effects = True` とし、
`run_game` から `presentation.play_turn_events` を呼んで既存の演出を再生する。
スプライト版は `False` とし、この段階では引き続き `LegacyHooks` を使用した。
バリアの途中描画が兼ねていた探索状態の更新は、`torch_radius` を渡して
ゲーム処理側で同じ時点に行う。文字表示 UI の演出を遅らせてもトレースを変えない。
手順 3 も完了。スプライト版も同じイベント経路へ切り替え、`LegacyHooks`、
`GameSession` の `hooks` 引数、エンジンの演出コールバック、移行用の
`uses_event_effects` フラグを削除した。削除前後で全6ステージと視界半径を
変えたバリア通過の計9ケースを比較し、トレースと乱数状態の一致を確認した。

廃止による見た目の変化（許容する前提）:

- 戦闘の閃光とバリアの演出は、ターンの途中ではなくターンの処理が終わった後に表示される。閃光はまだ前の画面が表示されている上に重ねて描くので、見た目はほぼ同じ。
- バリアの演出は今はターン途中の状態を描き直しているが、廃止後はイベントの座標を使って描く。
- 巻き戻しと階段の演出は、今もターン処理の終盤で呼んでいるので、ほとんど変わらない。

確認方法: 既存のトレーステストが変わらず通ること（演出の呼び出しは乱数や状態に影響しない）。加えて、各イベントに対応する演出関数が呼ばれることを、記録用の UI スタブで確かめるテストを追加する。

## 2. イベント型（`src/arlq/game_events.py` に追加）

方針:

- イベントは「画面にどう見せるか」ではなく「何が起きたか」を表す。
- 全イベントに `floor` を持たせる（ステージ6で別の階のイベントを除外するため）。
- 座標は移動前と移動後を両方持たせる。`step()` が返った時点で状態はもう書き換わっているので、演出側が前の位置を知る手段が他にないため。
- 消えたエンティティの見た目は、イベントの中に入れておく。

```python
@dataclass(frozen=True)
class EntityRef:
    uid: int            # エンティティ固有の番号（下記「エンティティID」参照）
    glyph: str          # tribe の文字（'a'、'@' など）
    kind: str           # "monster" | "fairy" | "member" | "treasure" | ...

@dataclass
class GameEvent:
    floor: int

# 移動・地形
@dataclass
class PlayerMoved(GameEvent):    src: Point; dst: Point
@dataclass
class WallBumped(GameEvent):     at: Point; result: str          # 既存の WallEvent.result
@dataclass
class FloorChanged(GameEvent):   kind: str; to_floor: int; exit_point: Point | None
                                 # kind は floor_transition_kind() の値（階段・落とし穴・崩落）
@dataclass
class HazardDamage(GameEvent):   at: Point; amount: float; tone: str   # _set_status_popup の呼び出し箇所
@dataclass
class BarrierHit(GameEvent):     at: Point; amount: float

# 戦闘（今 combat_effect を呼んでいる箇所）
@dataclass
class Combat(GameEvent):         attacker: Point; targets: list[tuple[EntityRef, Point]]
                                 won: bool; lp_delta: float
@dataclass
class Defeated(GameEvent):       entity: EntityRef; at: Point
@dataclass
class ProjectileShot(GameEvent): src: Point; dst: Point; hit: bool; prevented: bool   # 射手
@dataclass
class IvyLashed(GameEvent):      src: Point; dst: Point; amount: float
@dataclass
class Rearranged(GameEvent):     moves: list[tuple[EntityRef, Point, Point]]          # 渦

# 出現・取得
@dataclass
class Respawned(GameEvent):      entity: EntityRef; at: Point; glow: bool
@dataclass
class Gained(GameEvent):         kind: str; event_id: str; at: Point   # 宝箱・仲間・アイテム
@dataclass
class Expired(GameEvent):        kind: str; event_id: str | None       # 既存の ExpiredEvent に対応
@dataclass
class WorldChanged(GameEvent):   kind: str; at: Point                  # ステージ6の world event

# 進行
@dataclass
class Dialogue(GameEvent):       text: str
@dataclass
class Rewound(GameEvent):        message: str; trail: dict[int, set[Point]]
@dataclass
class StageEnded(GameEvent):     outcome: str
```

### イベントの集め方

- `_process_multi_floor_turn` から内部の関数へ、今の `trace` 引数と同じように `events: list | None` を渡していき、`_emit(events, ev)` で追加するだけにする。
- トレースの記録（`trace.record_contact`、`record_checkpoint`、`add_world_event`、`add_expired` など）を呼んでいる箇所は、ほぼそのままイベントを出す箇所になる。
- `_process_multi_floor_turn` は途中で `return` する箇所が多い。そこで出したイベントが失われないよう、リストは戻り値で返さず、引数として外から渡す。
- イベントを出す処理は追加だけにする。状態を読み替えたり、乱数を消費したり、処理の順番を変えたりしない。

### エンティティID

`Entity.__init__` で連番の `uid` を振る（`itertools.count` を使うので乱数を消費しない）。deepcopy や巻き戻し用スナップショットでも番号は引き継がれる。これがあると、演出中に「新しい状態の中で、このエンティティだけ隠す」ことができる。

## 3. スプライト版の演出部分

初期版の実装状況（2026-11-15、作業手順 4）:

- `SpriteUI.present_turn()` が `sprite_fx.Presenter.play()` を呼ぶ。移動補間や新しいエフェクトはまだ追加せず、前の画面に既存の静止画演出を重ねる。
- 戦闘・階移動の表示中は `_pump()` と `_flip()` を回す。フレーム間は Pyglet のプラットフォームイベントループで待ち、入力キューを消費しない。ウィンドウ終了で演出を中断し、リサイズ時は演出用オブジェクトを作り直す。
- 別階と暗いマスの演出を除外する。同一ターンに階が変わる場合は移動前の画面と移動後の `view` の可視範囲を使い分ける。戦闘パーティーのうち暗いマスにいる対象も除外する。
- 既存の戦闘・階移動の表示時間設定を継続する。新しい速度設定、`hidden_uids` による補間用の描画、残りのイベントは今後の作業。

以下は作り込み段階の目標も含む設計。

```python
# sprite_funcs.py（または新規の sprite_fx.py）
class Presenter:
    def play(self, ui, result: TurnResult, view: dict) -> None:
        """イベント列を演出の流れに変換し、画面を回しながら最後まで再生する。
        再生中に押されたキーはためておく。設定の演出速度で尺を変える。"""
```

- 描き方: `view`（新しい状態）を土台に描き、演出中のエンティティは `hidden_uids` で隠して、補間した位置に重ねて描く。撃破された敵は `EntityRef` の見た目を使ってフェードアウトさせ、出現する敵は出現演出が始まるまで隠しておく。
- ステージ6の別の階: 演出側で「今いる階」を追い、`FloorChanged` を受けたら更新する。`ev.floor` が今いる階と違うイベントは演出せず捨てる。同じターンの中で階を移動した場合も、各イベントが起きた時点の階で判定される。
- 見えない場所のイベントは演出しない: `view["cur_torched"]` で照らされていないマスのイベント（暗闇での敵の出現など）は捨てる。演出によってプレイヤーが知らないはずの情報が漏れるのを防ぐため。
- キー押し続けの移動: `repeat=True` のターンは `PlayerMoved` だけ短い補間にして、それ以外のイベントが起きたら演出を見せつつ押し続け移動を止める。
- 演出の速度設定（OFF / 速い / 標準）を置く。既存の `combat_effect_seconds` の設定との関係は実装時に決める。
- 演出の部品は `SpriteUI` の既存の描画部品（光の柱、地面の円、バリアの画像など）を使い、トゥイーンやパーティクルの小さな仕組みを自作する。効果音を入れる場合は `pyglet.media` を使う。

演出の例（方針A）:

| イベント | 演出 |
| --- | --- |
| `PlayerMoved` | マス間の移動を補間する |
| `Combat` / `Defeated` | 踏み込み → ヒット閃光 → ダメージ数字 → 揺れ → 撃破なら消滅パーティクル。後で短い戦闘カットインも検討 |
| `ProjectileShot` / `IvyLashed` | 発射元から対象への弾道・つるの軌跡 |
| `Rearranged` | 渦による入れ替わりを補間する |
| `Respawned` | 出現の光 |
| `FloorChanged` / `Rewound` | 既存の階移動・巻き戻しの演出を、止めずに再生する形にする |

## 4. テストと受け入れ基準

1. 乱数・挙動が変わらないこと: イベントを集める場合と集めない場合で既存のトレーステストを両方実行し、トレースが完全に一致することを確かめる。
2. イベント列の中身: シードを固定した代表的な状況（戦闘の勝敗、射手、渦、出現、階段、巻き戻し）で、イベントの型と順番を確かめる。
3. セッション単体で遊べること: `GameSession` だけで UI なしに1ゲーム通して遊べることを確かめる（今の headless テストを流用する）。
4. 演出側の除外ルール: 別の階のイベントと見えない場所のイベントが演出されないことを、`Presenter` の振り分け部分を単体でテストする。

## 5. 作業の順番

1. `uid` の追加とイベント型の定義をし、イベントを出す処理を入れる（挙動は変わらず、テスト 1・2 を追加）
2. `GameSession` を切り出し、`run_game` をラッパーにする（テスト 3 を追加）— 完了（2026-11-14、`e55be2c`、`ef3d71d` ほか。実際には手順 1 より先に実施した）
3. 文字表示の UI の演出をイベント経由に切り替え、`LegacyHooks` を廃止する（上記「`LegacyHooks` の廃止計画」）— 完了（2026-11-14）
4. スプライト版を「セッション + Presenter」の構成に切り替える（最初は今と同じ見た目で、sleep をなくす）— 初期版完了（2026-11-15）
5. 各イベントの演出を順に作り込む

手順 3 と 4 は互いに独立しているので、順番を入れ替えてもよい。

## 未決事項・注意点

- 階層ビュー用の `deepcopy(player)`: 解決済み。コピーせずに `player` をそのまま渡す形にした（`915b183`）。`player.current_floor` を読むのは `sprite_funcs.py` のカメラ追従だけで、階層ビュー以外のときしか通らない。
- 巻き戻し（時間ループ）とリプレイ: スナップショットとイベントの順番が乱数の消費順に左右されるので、手順 1 ではイベントを出すだけにし、処理の順番には一切手を付けない。
- `LegacyHooks` と演出用イベントの二重管理は解消済み（「`LegacyHooks` の廃止計画」参照）。
- トレースを演出用イベントから作る形への統合は、トレース形式を変えずにできる場合に限り、後で検討する。
- プレイヤーに見える挙動（演出速度の設定など）が増えたら、`README.md` と `README-ja_JP.md` を更新する。
