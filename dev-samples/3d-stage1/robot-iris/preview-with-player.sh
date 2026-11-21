#!/bin/sh
# Player and Iris on adjacent cells at the sprites' common scale (256 px per 2.6 units).
# Cell: 15x20 screen px = 141 x 188 sprite px. Sprite centres sit 0.35 units
# above the ground origin, i.e. 17 px above the feet in the 60-degree view.
set -e
PLAYER=../../../src/arlq/assets/characters/player.png
W=141; H=188; COLS=4; FEETY=260
cw=$((W*COLS)); ch=$((FEETY+H/2+20))
args=""
for c in 0 1 2 3; do
  x0=$((c*W)); y0=$((FEETY-H/2)); col=$([ $((c%2)) -eq 0 ] && echo '#2a2622' || echo '#24201d')
  args="$args -fill \"$col\" -draw \"rectangle $x0,$y0 $((x0+W-1)),$((y0+H-1))\""
done
eval convert -size ${cw}x${ch} xc:'#0b0d12' $args floor.png
pw=$(identify -format %w $PLAYER); ph=$(identify -format %h $PLAYER)
iw=$(identify -format %w iris.png); ih=$(identify -format %h iris.png)
px=$((W*1+W/2-pw/2)); py=$((FEETY-17-ph/2))
ix=$((W*2+W/2-iw/2)); iy=$((FEETY-17-ih/2))
convert floor.png $PLAYER -geometry +$px+$py -composite iris.png -geometry +$ix+$iy -composite \
  -filter point -resize 200% \
  -fill '#c8d0dc' -pointsize 22 -annotate +$((W*3-40))+$((ch*2-14)) 'PLAYER' -annotate +$((W*5-24))+$((ch*2-14)) 'IRIS' \
  preview-iris-with-player.png
rm floor.png
