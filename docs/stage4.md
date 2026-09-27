# Stage 4 / ステージ4

## English

Stage 4 is experimental and appears in the stage selection menu when started
with `--dev`. It has five floors and adds new enemies and traps to the Stage 3
structure. The filled-room counts are 0, 1, 1, 2, and 3, shuffled across the
five floors on each run. Each floor also has two Golems (`g`), and one randomly
selected floor has an additional Golem. Rocks can obstruct marksman lines when
Golems are defeated.
Rank 2 and 3 enemies are concentrated on floors 4 and 5; rank 3 enemies use a
double quote marker, such as `b"`. Two randomly selected floors from floors 2
through 5 have partitions that act as navigation obstacles. Chimeras are not
placed along the partition, and stairs are not assigned to a particular side.
The reduced Rare Amoeba
(`A`) count makes leveling harder. Its design and gameplay are subject to
change.

| Floor | `A` population | Rank 2 population | Rank 3 population |
| ---: | ---: | ---: | ---: |
| 1 | 1 | 3 | 0 |
| 2 | 1 | 3 | 0 |
| 3 | 1 | 3 | 0 |
| 4 | 1 | 4 | 2 |
| 5 | 1 | 2 | 1 |

The final floor contains the Dread Wyrm (`W`), its Wyrm guard (`w`),
and the treasure chest and Mimic. Barriers cover ten percent of its eligible
floor cells, giving the final floor a more hazardous feel.

### Lifebringer Elf (`L`)

One Lifebringer Elf appears on a random floor. Meeting L restores LP to 120 and raises
the player's level by one. This can temporarily exceed the normal 100 LP gauge.
At a 65-turn respawn tick, L returns on a randomly selected floor. L counts
toward the High Elf's two-elf requirement and has its own mark in the bottom
progress display. Once met, L's floor number is shown as `?` there, so its
respawn location is unknown.

### Monsters

| Display & Name | Description |
| -------------- | ----------- |
| **g** Golem | Rocks scatter when defeated; yields no food. |
| **k** Marksman | Shoots arrows when the player is in its line of sight. |
| **E** Rare Erebus | Restores LP when defeated but lowers the player's level. Returns at a 65-turn respawn tick on a randomly selected floor. |

### Traps

Unidentified traps are displayed as `?`, like monsters. After W is defeated,
a Mimic looks exactly like a treasure chest. A discovered Collapse stays in
place and can be used as a passage to the floor below.

| Trap | Display before discovery | Description |
| ---- | ------------------------ | ----------- |
| **M** Mimic | Hidden, then `T` | Appears as a chest after W is defeated; contact reveals it and starts combat. It disappears from the map when defeated. |
| **O** Collapse | `?` | Drops the player to the same coordinates on the floor below. It can be used repeatedly. |
| **V** Vortex | `?` | Repositions monsters, companions, and chests when defeated; explored areas are reset. Returns at a 65-turn respawn tick on a randomly selected floor. |

## 日本語

ステージ4は実験版で、`--dev`を指定するとステージ選択メニューに表示されます。ステージ3を拡張した5フロア構成で、新たな敵やトラップが登場します。埋める区画数は0、1、1、2、3の組み合わせを毎回シャッフルして各フロアに割り当てます。各フロアにはゴーレム（`g`）を2体配置し、ランダムに選んだ1フロアにはさらに1体追加します。倒したときに飛び散る岩でマークスマンの射線を遮れます。希少モンスターの `A` は各フロアに1体ずつ配置し、rank 2・3の敵はフロア4・5を中心に配置しています。フロア2〜5のうちランダムに選ばれた2フロアでは、分断が移動を妨げる障害として機能します。分断壁のそばにキメラは配置せず、階段も特定の区画側に割り当てません。rank 3の敵は `b"` のようにダブルクォートで表示されます。仕様やゲーム内容は今後変更される場合があります。

| フロア | `A`の数 | rank 2の個体数 | rank 3の個体数 |
| ---: | ---: | ---: | ---: |
| 1 | 1 | 3 | 0 |
| 2 | 1 | 3 | 0 |
| 3 | 1 | 3 | 0 |
| 4 | 1 | 4 | 2 |
| 5 | 1 | 2 | 1 |

最終フロアにはドレッドウィルム（`W`）、護衛のウィルム（`w`）、宝箱、ミミックが配置されます。階段やエンティティのない床マスの10%がバリアになり、より危険な雰囲気になります。

### ライフブリンガーエルフ（`L`）

ライフブリンガーエルフはランダムなフロアに1体だけ登場します。接触するとレベルが1上がり、LPが120まで回復します。通常のLPゲージの上限である100を一時的に超えることがあります。Lはハイエルフの条件となる「エルフ2体と知り合う」に数えられ、画面下の進捗フラグにも表示されます。一度接触すると、進捗表示上のLの階数は `?` になり、再出現先は分からなくなります。65ターン周期の再出現時に、Lはランダムなフロアへ再出現します。

### モンスター

| 表示 | 名前 | 説明 |
| --- | --- | --- |
| `g` | ゴーレム | 倒すと岩が飛び散り、食料は得られない。 |
| `k` | マークスマン | 射線が通ると矢を放つ。 |
| `E` | レアエレボス | 倒すとLPを回復するが、レベルが下がる。65ターン周期の再出現時にランダムなフロアへ出現する。 |

### トラップ

未発見のトラップはモンスターと同様に `?` と表示されます。ただしミミックはW撃破後、宝箱とまったく同じ姿になります。発見後の崩落は同じ場所に残り、下のフロアに移動する通路として利用できます。

| トラップ | 発見前の表示 | 説明 |
| --- | --- | --- |
| `M` ミミック | 非表示、その後 `T` | Wを倒すと宝箱と同じ姿で現れ、接触すると正体を現して戦闘になる。倒すとマップから消える。 |
| `O` 崩落 | `?` | 入ると1つ下のフロアの同じ座標へ落ちる。繰り返し利用できる。 |
| `V` ボルテックス | `?` | 倒すとエルフ以外のモンスターや同行者、宝箱を再配置し、探索済みマスをリセットする。65ターン周期の再出現時にランダムなフロアへ出現する。 |

### Stair discovery / 階段の発見

When a stair is discovered, its matching cell on the adjacent floor is marked
as explored.

階段を発見すると、隣接フロアにある対応位置のセルも探索済みになります。
