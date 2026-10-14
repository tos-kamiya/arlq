# ステージ1の3Dキャラクター試作

透明感のある樹脂・水晶風の立体駒を、Blender 4.0.2で作成した検討用素材。
ゲームには組み込んでおらず、ゲームルールや既存GUIは変更していない。

## 採用モデル

ユーザーとの形状確認により、次のモデルを採用する。
以降の素材制作・組み込み検討では、これらを基準にする。

| キャラクター | 採用モデル | 見下ろしプレビュー |
| --- | --- | --- |
| アメーバ `a`、レアアメーバ `A`、バイソン `b`、コモドドラゴン `d` | [attached-cones/stage1-characters.blend](attached-cones/stage1-characters.blend) | [画像](attached-cones/preview-overhead.png) |
| プレイヤー `@` | [player-arms/player.blend](player-arms/player.blend) | [画像](player-arms/preview-overhead.png) |

プレイヤーは2等身に近い頭と円筒形の胴体、短い腕、肩付近から裾へ離れる薄いマントで構成する。
足は付けず、正面を画面下向きに固定する。頭の上面に `@` を重ねる。
ほかのディレクトリのモデルは比較用の過去案として残す。
採用は造形の選択であり、ゲームへの組み込みはまだ行っていない。

### 60度の見下ろしプレビュー

水平から下向きに60度（真上から30度傾けた角度）の比較画像。
採用モデル、照明、平行投影、画角は維持し、カメラの角度だけ変更する。
この60度をプレイヤーと敵の採用角度とする。
元の `.blend` とプレビューは上書きせず、60度カメラを保存した別ファイルを用意する。

- [敵4種類](attached-cones/preview-angle60.png)
- [プレイヤー](player-arms/preview-angle60.png)
- [敵の60度カメラ付きモデル](attached-cones/stage1-characters-angle60.blend)
- [プレイヤーの60度カメラ付きモデル](player-arms/player-angle60.blend)

```bash
blender --background --threads 4 --python dev-samples/3d-stage1/render-angle60.py
```

## 作成したキャラクター

- `a`: アメーバ。丸い分葉と内部の核。
- `A`: レアアメーバ。共通の形に紫の材質と結晶状の突起を追加。
- `b`: バイソン。幅広の頭、角、胴体と四肢。
- `d`: コモドドラゴン。細長い胴体、尾、四肢と背の突起。

キャラクター名と登場ステージは `src/arlq/defs.py` の定義に基づく。
造形、色、突起などは今回のデザイン案であり、新たなゲーム上の能力を示すものではない。
素材の色は比較用の仮配色。ゲームに使う際は既存の強弱・識別・FOV表示を維持する必要がある。

## ファイル

- `stage1-characters.blend`: 4種類の編集可能なモデル、材質、展示用タイル、照明とカメラ。
- `preview-overhead.png`: 少し傾けた見下ろしの比較画像。
- `preview-top.png`: 真上から見た比較画像。
- `build.py`: シーン生成と画像出力を再現するBlender用Pythonスクリプト。

Blenderで `.blend` ファイルを開き、テンキー `0` でカメラビュー、`F12` でレンダリングできる。
各キャラクターは専用のコレクションにまとめている。識別文字はモデルとは別のオブジェクト。
画像は展示用の背景付きで、ゲーム組み込み用の透過画像やモデル書き出しはまだ行っていない。
FOV、未識別の共通駒、擬態、アニメーションも未実装。

## 再生成

リポジトリのルートで実行する。出力ファイルは上書きされる。

```bash
blender --background --threads 4 --python dev-samples/3d-stage1/build.py
```

CPUのCyclesでレンダリングする。使用環境のBlenderにOpenImageDenoiserがないため、デノイズは無効。
プレビューは形と材質の検討用であり、実際のゲーム表示サイズでの視認性・描画負荷は未検証。

## 角ばった形の比較案

`angular/` に、バイソンとコモドドラゴンの形を見直した別案を保存する。
最初の丸い試作は、このディレクトリ直下のファイルとして残す。

- バイソン: 平らな面で構成した幅広の肩、後方へ絞った胴体、角ばった頭、折れ曲がった角と四角い蹄。
- コモドドラゴン: 稜線のある胴体、くさび形の吻、先細りの尾、関節で曲がる脚と爪。
- アメーバ2種類: 最初の造形を維持し、同じ条件で比較する。

ドット絵ではなく、平らな面を持つ3Dメッシュを透明樹脂風に描画する。
全体を単純な箱に置き換えず、動物の輪郭を断面の変化で表現する方針。
色・照明・カメラは最初の案と揃えている。

```bash
blender --background --threads 4 --python dev-samples/3d-stage1/build.py -- --angular
```

出力は `angular/stage1-characters.blend`、`angular/preview-overhead.png`、
`angular/preview-top.png`。ゲームへの組み込みは行っていない。

## 丸みと単純さを調整した案

`refined/` に、角ばった案から次の調整を加えたモデルと画像を保存する。

- バイソン: 角ばった顔と角は維持し、胴体だけ稜線を広めに面取りして少し丸める。
- コモドドラゴン: 爪と背中の突起を省き、脚を各1本の単純な先細り形状にする。胴・頭・尾の角ばった輪郭は維持する。

```bash
blender --background --threads 4 --python dev-samples/3d-stage1/build.py -- --refined
```

出力は `refined/stage1-characters.blend`、`refined/preview-overhead.png`、
`refined/preview-top.png`。前の2案は比較用に残している。

## アメーバの6つの出っ張りを円錐にした案

`soft-cones/` に、両アメーバの体の周囲の6つの出っ張りを短い円錐状に変更した案を保存する。
円錐は体から外側に向けて配置し、先端は細い点にせず、太さを残して縁を丸める。
レアアメーバ上部の3つの突起は変更していない。
バイソンとコモドドラゴンは `refined/` と同じ形を維持する。

```bash
blender --background --threads 4 --python dev-samples/3d-stage1/build.py -- --soft-cones
```

出力は `soft-cones/stage1-characters.blend`、`soft-cones/preview-overhead.png`、
`soft-cones/preview-top.png`。前の案も比較用に残す。

## 根元を太くしたコーンの案

`broad-cones/` は、周囲の6つのコーンをさらに短く、根元を太くした案。
根元の半径を0.25から0.34、先端の半径を0.075から0.19に増やし、
出っ張りの長さを短縮して先端の丸みも強めた。ほかの形状は維持する。

```bash
blender --background --threads 4 --python dev-samples/3d-stage1/build.py -- --broad-cones
```

モデルと2種類のプレビューを `broad-cones/` に出力する。

## 横から鈍角の二等辺三角形に見える円錐

`obtuse-cones/` は、先端半径を0にして平らな先端をなくした案。
根元半径0.34、軸方向の高さ0.25の円錐で、軸に垂直な横方向から見ると
頂角は約107度の二等辺三角形になる。面取りは行わず、円周方向の陰影は滑らかにする。
アメーバの周囲の6つに適用し、ほかの造形は維持する。

```bash
blender --background --threads 4 --python dev-samples/3d-stage1/build.py -- --obtuse-cones
blender --background --threads 4 --python dev-samples/3d-stage1/render-cone-profile.py
```

モデルと見下ろし・真上のプレビューに加え、`cone-side.png` に円錐単体の横からの画像を出力する。

## コーンを本体へ少し寄せた案

`attached-cones/` は、鈍角の円錐6つをそれぞれ半径方向に0.06だけ内側へ移動した案。
円錐の形・大きさ・頂角は維持し、本体との付け根の重なりを増やした。
ほかのキャラクターは変更していない。

```bash
blender --background --threads 4 --python dev-samples/3d-stage1/build.py -- --attached-cones
```

モデルと見下ろし・真上のプレビューを `attached-cones/` に出力する。

## プレイヤー試作

`player/` は、画面下向きに正面を固定した冒険者の駒。
角を丸めた四角い頭、裾の広いマント、正面の小さなV字の切れ込みで構成する。
顔・手足の細部は省略し、頭の上面に別オブジェクトで `@` を重ねる。
白から淡い青の透明樹脂風材質を使用。照明とカメラ角度は採用した敵の案と揃える。

```bash
blender --background --threads 4 --python dev-samples/3d-stage1/build-player.py
```

`attached-cones/stage1-characters.blend` を読み込み、展示環境を引き継いだ別シーンを作る。
元の敵のファイルは変更しない。出力は `player/player.blend` と見下ろし・真上のプレビュー。
ゲームへの組み込み、LPや毒の表示、方向変化、アニメーションは未実装。

## 胴体と薄いマントを追加したプレイヤー

`player-cloak/` は、厚い駒状のマントを、肩から背中へ垂れる厚さ0.025の薄い曲面に変更した案。
独立した胴体、簡単な腕・脚・靴と首を追加し、頭を小さくして人型の比率に調整する。
マントには控えめなひだを付け、素材は少し粗く曇った半透明にする。
固定の正面方向、見下ろし角度、上面の `@` は維持する。

```bash
blender --background --threads 4 --python dev-samples/3d-stage1/build-player-cloak.py
```

`player/player.blend` の展示環境を読み込み、別案としてモデルとプレビューを出力する。
以前のモデルと採用した敵のモデルは変更しない。

## 足のない円筒形の胴体と湾曲したマント

`player-cylinder/` は、小さな頭の下に大きい円筒形の胴体を重ねた案。
胴体の上下の縁を丸め、腕・脚・靴・首は省略する。
薄いマントは胴体の背面と側面を約220度包む曲面とし、正面を開ける。
見下ろし角度、材質、頭の上面の `@` は維持する。

```bash
blender --background --threads 4 --python dev-samples/3d-stage1/build-player-cloak.py -- --cylinder
```

モデルと見下ろし・真上のプレビューを `player-cylinder/` に出力する。

## 2等身に近い比率と、少しなびくマント

`player-flowing/` は、頭の高さ0.36に対して胴体を高さ0.40・半径0.27に縮めた案。
足のない構成を維持し、頭と胴体を2等身に近い比率にする。
マントは肩付近だけ体に沿わせ、下に行くほど後方へ離し、裾を少し横へ流す。
背面と側面の約180度を覆い、正面は開ける。なびきは固定の造形で、アニメーションではない。

```bash
blender --background --threads 4 --python dev-samples/3d-stage1/build-player-cloak.py -- --flowing
```

モデルと見下ろし・真上のプレビューを `player-flowing/` に出力する。

## 短い腕を戻した案

`player-arms/` は、`player-flowing/` の頭・胴体・マントを維持し、
胴体の左右に短い腕を追加した案。腕は少し前寄りに置き、マントに埋もれにくくする。
脚・靴は追加しない。

```bash
blender --background --threads 4 --python dev-samples/3d-stage1/build-player-cloak.py -- --arms
```

モデルと見下ろし・真上のプレビューを `player-arms/` に出力する。
