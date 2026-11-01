# dev-samples

開発用のサンプル、素材の生成スクリプト、計測用のスクリプトを置く。ゲーム本体（`src/arlq`）からは読み込まない。

| パス | 中身 |
| --- | --- |
| `3d-stage1/` | スプライト版GUIの3D素材（キャラクター、地形、効果）を Blender で作るスクリプトと、そのシーンやプレビュー。詳しくは `3d-stage1/README.md` |
| `benchmark-floor-rendering.py` | 床の描画の計測 |
| `detect_locale.py` | 言語の自動判定の確認 |

以下は、キャラクターのモデルを直したあとに、ゲーム用の画像（アセット）と全体プレビューへ反映するときの手順と注意点をまとめたもの。コマンドはリポジトリの最上位で実行する。各スクリプトの細かい説明とモデルごとの仕様は `3d-stage1/README.md` にある。

## 生成物

| 生成物 | 場所 | 作るスクリプト |
| --- | --- | --- |
| 3つのシーン（モンスター、メンバー、その他） | `3d-stage1/heroic/characters-*-angle60.blend` | `3d-stage1/build-heroic.py` |
| 全体プレビュー | `3d-stage1/heroic/preview-angle60.jpg` | `3d-stage1/build-heroic.py`（PNGで描かれるのでJPEGに変換） |
| キャラクター画像 | `src/arlq/assets/characters/*.png` | `3d-stage1/export-sprites.py` のあと `3d-stage1/bleed-alpha.py` |
| 非常食の画像 | `src/arlq/assets/rations/*.png` | 同上 |

キャラクター画像は、保存済みのシーンを開いて書き出す。モデルのコードを直したら、先にシーンを作り直す。

## 一部のキャラクターを直したとき

```bash
# 1. シーンを作り直す（全体プレビューは描かない。約1分）
blender --background --threads 4 --python dev-samples/3d-stage1/build-heroic.py -- --save-only
# 2. 直したキャラクターだけ書き出す（名前は export-sprites.py の models の1つ目）
blender --background --threads 4 --python dev-samples/3d-stage1/export-sprites.py -- --only explorer-light explorer-medium explorer-dark
# 3. 書き出した画像だけ、透明な画素に輪郭の色を広げる
.venv/bin/python dev-samples/3d-stage1/bleed-alpha.py src/arlq/assets/characters/explorer-*.png
```

- `--save-only` は、直したキャラクターのシーンだけでなく3つのシーンをすべて作り直すので、`.blend` は3つとも変更ありになる。1つのシーンだけでよければ `-- --group monsters`（または `members`、`others`）を使う。
- `bleed-alpha.py` を引数なしで実行すると、`src/arlq/assets` の全PNGを処理する。このとき、関係のない `src/arlq/assets/effects/slash.png` が毎回書き換わる。処理した画像のパスを渡すか、実行後に `git checkout -- src/arlq/assets/effects/slash.png` で戻す。
- 書き出し先は固定（`src/arlq/assets/...`）。試しに描いて比べるだけのときは、書き出した画像をスクラッチ領域へコピーしてから、`git checkout --` でアセットを元に戻す。

## 全体プレビューと全キャラクターの書き出し

```bash
# 1. 3つのシーンと全体プレビュー（約4〜5分）
blender --background --threads 4 --python dev-samples/3d-stage1/build-heroic.py
# 2. JPEGにする（リポジトリには .jpg だけを置く）
(cd dev-samples/3d-stage1/heroic && convert preview-angle60.png -quality 90 preview-angle60.jpg && rm preview-angle60.png)
# 3. 全キャラクターの書き出し（約6〜7分）
blender --background --threads 4 --python dev-samples/3d-stage1/export-sprites.py
# 4. 透明な画素に輪郭の色を広げる
.venv/bin/python dev-samples/3d-stage1/bleed-alpha.py
git checkout -- src/arlq/assets/effects/slash.png
```

合わせて10分以上かかるので、続けてバックグラウンドで実行するとよい。全体プレビューを含めて実行すると、Blender が描画中に Embree の中で落ちることがあった（2026-10-28）。そのときは `--save-only` でシーンを作ってから、もう一度実行する。

### 直していないキャラクターの画像を戻す

全キャラクターを書き出すと、モデルを直していないキャラクターの画像も、描画のノイズでわずかに変わる。不要な差分を入れないよう、コミット済みの画像と比べて、直したキャラクター以外は戻す。

```bash
# コミット済みの画像との差（RMSE の括弧内。0〜1）を一覧にする
mkdir -p /tmp/arlq-head
for f in $(git status --short src/arlq/assets | awk '{print $2}'); do
  b=$(basename "$f"); git show HEAD:"$f" > /tmp/arlq-head/"$b"
  if [ "$(identify -format %wx%h /tmp/arlq-head/"$b")" = "$(identify -format %wx%h "$f")" ]; then
    echo "$b $(compare -metric RMSE /tmp/arlq-head/"$b" "$f" null: 2>&1)"
  else
    echo "$b size changed"
  fi
done
# 直したキャラクター以外を戻す（例: 直したのが explorer と jester のとき）
git status --short src/arlq/assets | awk '{print $2}' | grep -Ev 'explorer-|jester-' | xargs git checkout --
```

- RMSE が 0.001 未満なら、見ても分からないノイズの差。
- 0.01 を超える差が、直していないキャラクターに出たら、戻す前に並べて見比べる。前回の書き出しのあとに、共通のコード（たとえば宝箱・ミミック・おもちゃの宝箱で共有する `treasure()`）が変わったのに、書き出し直していなかったことがある。
- 大きさ（画像のサイズ）が変わったものは、モデルの変更で変わったもの。

## 全体プレビューとキャラクター画像の照明の違い

全体プレビューとキャラクター画像は、同じシーンから描くが、照明の扱いが違う。プレビューで良く見えても、キャラクター画像では見え方が変わることがある。

- 全体プレビューは、広い範囲を同じように照らすため、エリアライトを同じ向きの太陽光に置き換えて描く。キャラクター画像は、照明をキャラクターの位置へ動かして、エリアライトのまま描く。
- 全体プレビューは、描画時間を減らすため、発光する材質が周りを照らさない設定（`emission_sampling = 'NONE'`）で描く。キャラクター画像では、発光する材質が周りを照らす。光る部品の近くの面が明るくなりすぎるときは、その材質だけ `mat.cycles.emission_sampling = 'NONE'` にする（おもちゃの宝箱の中の光など）。
- 黒く見せたい面（ミミックの口の中など）も、つやがあると照明が映り込んで灰色に見える。`Specular IOR Level` を0にし、`roughness` を1にする。

## 確認用の比較画像

モデルを直したら、全体プレビューの前に、対象のキャラクターと比べたいキャラクターを並べた比較画像で確認する。比較画像はスクラッチ領域に作り、リポジトリにはコミットしない。

```bash
# 書き出した画像を、下端をそろえて横に並べる（同じ倍率なので大きさも比べられる）
cd src/arlq/assets/characters
convert -background '#46423c' chimera.png comodo-dragon.png dragon.png \
  +repage -gravity south +append +repage -flatten /tmp/compare.png
# メンバーの一覧（肌の色3段）
for t in light medium dark; do
  convert -background '#46423c' player.png jester-$t.png healer-$t.png rogue-$t.png \
    knight-$t.png guardian-$t.png explorer-$t.png +repage -gravity south +append +repage /tmp/row-$t.png
done
convert -background '#46423c' /tmp/row-light.png /tmp/row-medium.png /tmp/row-dark.png \
  +repage -gravity center -append +repage -flatten /tmp/members-preview.png
```

- 変更前の画像と並べるときは、書き出す前にアセットをスクラッチ領域へコピーしておくか、`git show HEAD:src/arlq/assets/characters/<名前>.png` で取り出す。
- 書き出した画像は、透明な部分の外側に余白がない大きさに切り詰められていて、画像ごとに大きさが違う。`+repage` を付けないと、並べたときに位置がずれたり、1枚しか見えなかったりする。

## コミットの仕方

- モデルのコード（`3d-stage1/build-heroic.py`）と説明（`3d-stage1/README.md`、このファイル）は、変更ごとにコミットする。
- 画像（`src/arlq/assets/...`）、シーン（`.blend`）、全体プレビュー（`.jpg`）は、ある程度変更がまとまってから一緒にコミットする。
- ユーザーが示した参考画像（リポジトリ直下の `shot*.png`）と、確認用の比較画像はコミットしない。
