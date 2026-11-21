#!/bin/sh
# One overview of every expression (run after build-robot-iris.py), four to
# a row: per expression, its face straight from the front above, the game-angle
# sprite (enlarged 2x, on the floor colour) below, its name at the bottom.
set -e
cd "$(dirname "$0")/expr"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
LIST="neutral joy worry panic surprise curious idle"
rows=""
row=""
i=0
for n in $LIST; do
  # Face: the head region of the front close-up, on a dark backdrop.
  convert face-$n.png -crop 400x210+40+95 +repage -resize 240x \
    -background '#0b0d12' -flatten "$TMP/f.png"
  # Game sprite: the top part (robot, ring), enlarged 2x, on the floor colour.
  convert iris-$n.png -background none -gravity north -extent 120x105 \
    -filter point -resize 200% -background '#24201d' -flatten \
    -gravity center -extent 240x220 "$TMP/g.png"
  convert "$TMP/f.png" "$TMP/g.png" -append \
    -background '#0b0d12' -fill '#c8d0dc' -font DejaVu-Sans -pointsize 18 \
    label:"$n" -gravity center -append -bordercolor '#0b0d12' -border 4 "$TMP/c-$n.png"
  row="$row $TMP/c-$n.png"
  i=$((i + 1))
  if [ $((i % 4)) -eq 0 ]; then
    convert $row +append +repage "$TMP/r-$i.png"
    rows="$rows $TMP/r-$i.png"
    row=""
  fi
done
if [ -n "$row" ]; then
  convert $row +append +repage "$TMP/r-last.png"
  rows="$rows $TMP/r-last.png"
fi
convert -background '#0b0d12' $rows -append +repage ../preview-expressions.png
