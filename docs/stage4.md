# Stage 4 / ステージ4

## English

Stage 4 is experimental and appears in the stage selection menu when started
with `--dev`. It has four floors and adds new enemies and traps to the Stage 3
structure. Its design and gameplay are subject to change.

### Monsters

| Display & Name | Description |
| -------------- | ----------- |
| **k** Marksman | Shoots arrows when the player is in its line of sight. |
| **E** Rare Erebus | Restores LP when defeated but lowers the player's level. |

### Traps

Unidentified traps are displayed as `?`, like monsters. After W is defeated,
a Mimic looks exactly like a treasure chest. A discovered Collapse stays in
place and can be used as a passage to the floor below.

| Trap | Display before discovery | Description |
| ---- | ------------------------ | ----------- |
| **M** Mimic | Hidden, then `T` | Appears as a chest after W is defeated; contact reveals it and starts combat. It disappears from the map when defeated. |
| **O** Collapse | `?` | Drops the player to the same coordinates on the floor below. It can be used repeatedly. |
| **V** Vortex | `?` | Repositions monsters, companions, and chests when defeated; explored areas are reset. |

## 日本語

ステージ4は実験版で、`--dev`を指定するとステージ選択メニューに表示されます。ステージ3を拡張した4フロア構成で、新たな敵やトラップが登場します。仕様やゲーム内容は今後変更される場合があります。

### モンスター

| 表示 | 名前 | 説明 |
| --- | --- | --- |
| `k` | マークスマン | 射線が通ると矢を放つ。 |
| `E` | レアエレボス | 倒すとLPを回復するが、レベルが下がる。 |

### トラップ

未発見のトラップはモンスターと同様に `?` と表示されます。ただしミミックはW撃破後、宝箱とまったく同じ姿になります。発見後の崩落は同じ場所に残り、下のフロアに移動する通路として利用できます。

| トラップ | 発見前の表示 | 説明 |
| --- | --- | --- |
| `M` ミミック | 非表示、その後 `T` | Wを倒すと宝箱と同じ姿で現れ、接触すると正体を現して戦闘になる。倒すとマップから消える。 |
| `O` 崩落 | `?` | 入ると1つ下のフロアの同じ座標へ落ちる。繰り返し利用できる。 |
| `V` ボルテックス | `?` | 倒すとエルフ以外のモンスターや同行者、宝箱を再配置し、探索済みマスをリセットする。 |
