# sprite_funcs.py 分割リファクタリング計画

作成日: 2026-11-15

## 背景

`src/arlq/sprite_funcs.py`（2776行、`SpriteUI` 1クラスに約120メソッド）を分割したい。1回目の試み（`sprite_characters.py` / `sprite_effects.py` / `sprite_images.py` への切り出し）は、次の理由でうまくいかなかったため破棄した。

- メソッドを `def f(ui, ...)` の形の関数にして外へ出しただけで、`ui._draw_sprite` などの private な属性を15〜25種類参照していた。結合は弱まらず、元のクラスに転送用のメソッドも残った。
- テストが `sprite_funcs.X` を参照したり monkeypatch したりしているため、定数の `X as X` 再エクスポートや、ラッパー関数（`soft_outline_image`）で辻褄を合わせていた。再エクスポートした名前を monkeypatch しても、移動先のモジュールには効かない。
- 循環 import を避けるため、無関係な定数（`NEIGHBOR_SCALE`、`TERRAIN_*`）を `sprite_effects.py` に置いていた。

1回目の試みの成果物は scratchpad に退避済み（保存はしない前提）。

## 方針

1. **`self` を使わないものは関数として、`self` に強く依存するものはミックスインとして分ける。** 状態に依存するメソッドを無理に関数にしない。
2. **定数は「定義するモジュールを1つに決める」。** 移した名前を `sprite_funcs` から再エクスポートしない。テストの参照先と monkeypatch 先は、名前を定義しているモジュールに書き換える。
3. **フェーズごとに、本体を変えずに移すだけにする。** 移動と同時にロジックや名前、引数を変えない。`git diff --color-moved=zebra` で、変更が移動だけであることを確認できるようにする。
4. **1フェーズ = 1コミット。** フェーズの途中で別のフェーズに手を出さない。
5. 依存の向きは `sprite_defs` ← `sprite_images` ← ミックスイン群 ← `sprite_funcs`（`SpriteUI`）の一方向にする。ミックスインのモジュールは `sprite_funcs` を import しない。

## ミックスインの書き方

```python
# sprite_effects.py
class SpriteEffectsMixin:
    """Combat and floor transition effects of SpriteUI."""

    def draw_combat_effect(self, pos, won: bool) -> None:
        ...  # 本体はそのまま移す
```

```python
# sprite_funcs.py
class SpriteUI(SpriteTerrainMixin, SpriteEffectsMixin, PygletUI):
```

- ミックスインには `__init__` もクラス属性の既定値も置かない。状態の宣言（`_attack_facing = 'up'` など）と初期化は `SpriteUI` に集めたままにし、状態の一覧が1か所で読めるようにする。
- ミックスインは `PygletUI` を継承しない。`SpriteUI` 以外では使わない前提なので、抽象メソッドや Protocol は作らない。
- テストの `SpriteUI.__new__(SpriteUI)` はミックスインに関係なくそのまま動く。

## フェーズ

### フェーズ1: `sprite_images.py`（`self` を使わない画像生成関数）

移すもの（HEAD の 419〜682行目）: `_luminance`、`pillar_image`、`respawn_column_image`、`smoke_image`、`barrier_image`、`ground_disc_image`、`gray_image`、`soft_outline_image`、`brightened_image`、`edge_floor_bounds`、`edge_floor_shade`、`edge_floor_shade_data`、`mipmapped`。

これらの関数が使う定数も一緒に移す: `PILLAR_*`、`RESPAWN_COLUMN_*`（形状と生成用）、`BARRIER_*`（画像生成用）、`GROUND_DISC_*`、`FOLLOWER_*`、`EDGE_FLOOR_*`、`MIPMAP_LOD_BIAS`。調査では、これらの関数はこの定数群と `d.*`、GL 定数にしか依存していなかった。`SpriteUI` 側でも使う定数（`PILLAR_HEIGHT`、`GROUND_DISC_FLATTEN`、`EDGE_FLOOR_*`、`FOLLOWER_SCALE` など）は、`sprite_funcs` が `sprite_images` から import する。

- `soft_outline_image(data)` の引数は今のまま変えない（`FOLLOWER_*` はモジュールのグローバルとして読む）。こうすれば `monkeypatch.setattr(sprite_images, 'FOLLOWER_OUTLINE_BAND', 1)` がそのまま効く。
- テストの修正: `sprite_funcs.barrier_image` → `sprite_images.barrier_image` のように参照先を変える。`_follower_image` のテストは、`mipmapped` / `soft_outline_image` / `gray_image` を「呼び出し側のモジュール」で差し替える必要がある。`sprite_funcs` が `from .sprite_images import ...` で取り込むなら、差し替え先は `sprite_funcs` のままでよい。`sprite_images.mipmapped` のようにモジュール経由で呼ぶなら、差し替え先は `sprite_images` になる。どちらにするかを決めて統一する（推奨は `from ... import` で、テスト側の変更が最小になる）。
- 期待効果: 約370行の削減。リスクは低い。

### フェーズ2: `sprite_defs.py`（複数のモジュールで共有する表示定数）

フェーズ3・4で循環 import を避けるための準備。**2つ以上のモジュールで使う**表示定数だけを移す。例: `NEIGHBOR_SCALE`、`SPRITE_REFERENCE_PIXELS`、`SPRITE_GROUND_OFFSET_PIXELS`、`TERRAIN_TINT`、`TERRAIN_SIDE`、`TERRAIN_OVERHANG`、`PLAYER_FACING_BY_MOVE`。1つのモジュールでしか使わない定数は、そのモジュールに置く。ゲームの定数を `defs.py` に集めているのと同じ考え方。

- 実際にどの定数を移すかは、フェーズ3・4で移すメソッドの範囲が決まってから、`grep` で使っているモジュールを数えて決める。フェーズ3・4と同じコミットにしてもよい。
- テストの `sprite_funcs.TERRAIN_TINT` などは `sprite_defs.TERRAIN_TINT` に変える。

### フェーズ3: `sprite_effects.py`（`SpriteEffectsMixin`）

移すもの（HEAD の 1667〜1858行目付近）: `_update_player_facing`、`_play_effect`、`draw_combat_effect`、`draw_floor_transition`、`_animate_floor_transition`、`_create_floor_transition`。
定数: `SLASH_FILES`、`FLOOR_TRANSITION_*`、`ROPE_*`、`TRANSITION_BACKGROUND`、`LANDING_FEET_HEIGHT`（エフェクトでしか使わないなら、ここで定義する）。

- `present_turn` は `Presenter` と `SpriteUI` をつなぐ入口なので、`SpriteUI` に残す。
- 期待効果: 約200行の削減。

### フェーズ4: `sprite_terrain.py`（`SpriteTerrainMixin`）

移すもの: 床・壁・地形・障壁の描画と、端の影。
`_set_terrain_theme`、`_create_floor_tiles`、`_copy_floor_tile`、`_draw_floor_backdrop`、`_draw_floor_tiles`、`_draw_tile`、`_draw_floor`、`_draw_wall_block`、`_draw_wall_rect`、`_decor_at`、`_draw_barrier`、`_near_cooling_center`、`_barrier_look`、`_draw_d_gate`、`_draw_stairs`、`_draw_bridgehead`、`_open_floor`、`_draw_pit`、`_draw_terrain`、`_terrain_region`、`_set_edge_shade_field`、`_get_edge_shade_image`、`_edge_shade_strips`、`_draw_edge_shade`。
定数: `WALL_*`、`FLOOR_PARTS`、`FLOOR_TINTS`、`FLOOR_CHECKER_SHADE`、`TERRAIN_THEMES`、`STAGE_TERRAIN_THEMES`、`TERRAIN_FILES`、`TERRAIN_EXPLORED_SHADE`、`STAIR_DISC_OPACITY`、`LANDING_FILE`、`FALLEN_ROCK_BLOCKERS`、`BARRIER_*`（描画用）、`SMOKE_*`。

- `SpriteUI` のクラス属性の既定値に `FLOOR_TINTS` / `TERRAIN_THEMES` が使われているので、`sprite_funcs` はそれらを `sprite_terrain`（または `sprite_defs`）から import する。
- `__init__` の中の地形画像の読み込みは、今回は `SpriteUI` に残す。分けるとしても、`self._load_terrain_images()` をミックスイン側に置いて `__init__` から呼ぶ程度にとどめる。
- 期待効果: 約600行の削減。

### フェーズ5（保留。フェーズ4の後で判断する）

キャラクターの描画（`_draw_player`、`_draw_member`、`_draw_fairy_slot`、`_draw_rank_mark`、`_draw_dungeon_core`、`_draw_lp_gauge`、`_draw_hover_name`、`_player_sprite`）や HUD・レイアウト（`_set_scaled_dimensions`、`_on_window_resize`、`_draw_strength_entry*`、`_draw_*_panel`）。これらは `_draw_sprite`、`_place_sprite`、`_sprite_unit`、`_field_col_x` という描画の基本処理と強く絡んでいて、分けても読みやすさの改善は小さい。フェーズ4の時点で `sprite_funcs.py` は約1500行になる見込み。そこで止めるかどうかを判断する。

## 各フェーズの完了条件

- `uv run -p .venv/bin/python pytest` がすべて通る（現在 1107 passed）。
- `uv run -p .venv/bin/python python -m compileall src` と `python -c "import arlq.sprite_funcs"` が成功する。
- `git diff --color-moved=zebra` で、変更が移動と import 行・テストの参照先の変更だけであることを確認する。
- `grep -n " as \([A-Z_]*\)," src/arlq/sprite_funcs.py` で、再エクスポートが残っていないことを確認する。
- GUI（`arlq-sprites` / `--sprite` 系の起動）を手動で起動し、床の切り替え、戦闘のスラッシュ、障壁、階段、端の影の見た目が変わっていないことを確認する。ヘッドレス環境で確認できなかった場合は、その旨をコミット前に報告する。
- コミットメッセージは `refactor: move sprite image generators to sprite_images` のように1フェーズに1つ付ける。プレイヤーから見える挙動は変わらないので、README とバージョンは変更しない。

## やらないこと

- 関数への移動と同時に、名前の変更、引数の追加、`self` → `ui` の書き換えをすること。
- `sprite_funcs` からの再エクスポートと、互換性のためのラッパー関数。
- `SpriteDrawing` / `SpriteUI` のように、同じファイルの中でクラスを継承で分けること（diff が大きくなるだけで、ファイルは小さくならない）。
- `sprite_fx.py`（`Presenter`）の変更。今回の分割の対象外。
