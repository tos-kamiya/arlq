# ARLQ Release Notes

## 6.8.1 - 2026-11-16

- Keep the player visible in front of the collected treasure chest on the
  sprite-mode victory screen.

## 6.8.0 - 2026-11-16

- Restore one Rare Erebus (`E`) to the initial monster placement on each of
  Stage 6's second and third floors.

## 6.7.11 - 2026-11-16

- Show a golden glow around the collected treasure on the sprite-mode victory
  screen, and sparkling particles around the player in the character GUI and
  terminal. Both effects respect the combat effect duration setting.
- Display treasure and undiscovered Mimics as `[T]` in character modes, and
  hide treasure and Dungeon Core brackets wherever they would obscure other
  map contents.
- Shorten boss and Dungeon Core defeat effects to about 0.93 and 1 second,
  respectively, in all display modes.
- Widen the first room of the Stage 5 training ground by one column.

## 6.7.10 - 2026-11-15

- Apply all settings and exit when confirming the sprite display or gamepad
  button settings submenu.
- Keep the character GUI responsive during combat effects and allow a gamepad
  direction change to interrupt sprite movement animation.
- Continue movement repeat after entity contact; automatic stopping still
  applies before visible entities and known hazards.

## 6.7.9 - 2026-11-15

- Show Loop Fairy movement trails as cyan circles centered in each cell in
  the character and sprite GUIs, improving their visibility near walls.

## 6.7.8 - 2026-11-15

- Show Vortex storms, Dungeon Core bursts and boss afterglows in the character
  GUI and terminal, using pixel graphics and braille respectively. The player
  remains visible, and setting combat effect duration to 0 disables them.

## 6.7.7 - 2026-11-15

- Adjust enemy placement in the Stage 5 training ground and add a Vortex.

## 6.7.6 - 2026-11-15

- In sprite mode, destroying the Dungeon Core swells a dark, see-through dome
  over where it stood, its violet band of light thinning as it grows, before
  it comes apart into faint mist over about 1.5 seconds. It is skipped when
  the combat effect duration is 0.

## 6.7.5 - 2026-11-15

- In sprite mode, defeating a stage boss leaves a lingering afterglow where it
  fell: a pillar of light, a ring spreading over the ground and sparks
  drifting up, for about 1.4 seconds. In Stage 6 it marks the boss party's
  leader, not the Dungeon Core. It is skipped when the combat effect duration
  is 0.

## 6.7.4 - 2026-11-15

- In sprite mode, defeating a Vortex briefly shows its dark storm swirling
  over the floor around where it stood, after the slash and before the
  rearranged floor appears. It lasts 4/3 of the combat effect duration and
  is skipped when that is set to 0.

## 6.7.3 - 2026-11-15

- Add a `Smooth movement` setting to the sprite display settings to turn the
  glide into each step, and the field's scroll along with it, on or off.
- Add `Reset all settings to defaults` at the end of `Settings`, restoring
  every setting, including the sprite display settings and gamepad buttons;
  Enter on the top row then applies the defaults and Esc cancels.

## 6.7.2 - 2026-11-15

- Glide the sprite-mode player, its fairy and following party members from the
  cell they left into the new one, with the field scrolling smoothly along
  with the view instead of jumping a cell.
- While a direction is held, make each glide last until the next key repeat so
  walking keeps moving between steps.

## 6.7.1 - 2026-11-15

- Group sprite display options in a submenu for combat effects, floor
  transitions and character bobbing.
- Open settings submenus with Enter or the gamepad confirm button as well as
  the right direction.

## 6.7.0 - 2026-11-15

- Turn the sprite-mode player toward its last move, with new sprites facing up,
  left and right in every sword state; it faces the screen at the start of a
  stage and after stairs, falls and Loop rewinds.
- Refine the player's look: a shorter cloak, the eye window set into the
  faceplate, and a horn-shaped crest.
- Make characters in view hop gently while waiting for input in sprite mode,
  with a `Character bobbing` on/off setting.
- Cut the sprite-mode slash effect the way the player attacked.
- Animate the sprite-mode floor transition: the old floor fades out, the player
  steps along the stairs, falls or climbs the rope, and the new floor fades in.
- Draw following party members and the Javelin Elf smaller, with a fainter
  outline, so they no longer look larger than the player.
- Mark party members with `@` in the member status (for example `Y@`).

## 6.6.4 - 2026-11-15

- Keep the sprite window responsive during combat and floor-transition effects,
  queueing keyboard input for the next move and handling resizing and closing.
- Hide sprite effects on other floors and unlit cells.
- Play existing effects from turn events after each move is resolved across all
  frontends, preserving gameplay rules and trace compatibility.

## 6.6.3 - 2026-11-14

- Narrow sprite-mode field cells back to 15 px (from 16 px) at scale 1, and
  redraw the floor, wall, stair, pit, bridgehead and Dungeon Core images for
  the 3:4 cell shape.
- Rebalance Stage 4 and Stage 6 monster rosters and Stage 6 progression,
  including recovery encounters and the Dungeon Core deadline.
- Refine party member behavior and the Stage 5 healer's trial and training area.
- Show the Dungeon Core growing toward its rampage as the deadline approaches.

## 6.6.2 - 2026-11-11

- Add the Stage 6 Dungeon Core objective, activated after defeating the Fire
  Drake, with the treasure chest and Mimic tied to the core.
- Allow monster spawns and respawns to clear caltrops and barriers beneath
  them; place the core anywhere eligible on the final floor.
- Make Vortex map-memory loss follow a repeating 2×2 hatch, erasing all cells
  within 90% of its radius and 75% of cells in the outer 10%.

## 6.6.1 - 2026-11-10

- Restore Loop Fairy rewinds from saved game states while continuing the
  current random sequence. Older traces containing Loop rewinds may replay
  differently.

## 6.6.0 - 2026-11-10

- Revise Stage 6 monster ranks, initial and periodic spawns, and party formation;
  monsters can join the boss party and spawn on barriers, clearing those cells.
- Keep monster spawns and respawns away from the player's immediate vicinity.
- Keep the first recruited party member, replace the second when recruiting
  another, and show members following the player's path. The Jester leaves
  at level 80 and cannot rejoin.
- Widen Stage 6's ordinary openings, remove boss route markers and the narrow
  corridor command-line option, and mark explored Golem rubble with `+` in
  the character GUI and terminal.
- Remove overshoot assist so movement and LP costs remain in the trace. Older
  traces that omitted actions during overshoot assist may not replay exactly.

## 6.5.1 - 2026-11-10

- Replace the Stage 6 tavern with a bridgehead and its new sprite artwork;
  add Ivy artwork and refine the Caltrop Plant sprite.
- Add Ivy to Stage 6, adjust Wyrm experience and encounters, and revise monster
  spawning, movement, and party formation.
- Scatter unrecruited members after changing floors by a different staircase
  or pit, and preserve sword drops when defeating monster parties.

## 6.5.0 - 2026-11-10

- Redesign Stage 6 as a three-floor dungeon with periodically spawning and
  moving monsters that can form parties, a revised monster roster, and an
  empowered Fire Drake boss party.
- Restore LP to 50 when returning to the first-floor tavern, and make entering
  the tavern a new rewind point.
- Apply terrain placement priorities to barriers, walls, caltrops, and Golem
  rocks, protecting hidden passages and pit landings. Vortex no longer moves
  Collapse terrain.
- Replace the game's random generator with an independent MT19937
  implementation. Existing seeds generate different layouts, and older traces
  may no longer replay correctly.

## 6.4.2 - 2026-11-09

- Give ordinary Flame Cobras barriers on their left and right.

## 6.4.1 - 2026-11-08

- Revise the Stage 5 training map and rebalance party members and Stage 6
  encounters, equipment, and recruitment.
- Add the Seer fairy and new character sprite variants, and update fairy names.
- Show barrier protection in the interface, including a smaller sprite when
  the Guardian reduces damage, and raise the tavern floor onto a stone plinth.
- Let Golem rocks replace barriers when they scatter.

## 6.4.0 - 2026-11-08

- Rebuild Stage 6 as a four-floor dungeon with looping corridors, revised
  enemy parties and growth, and a new boss encounter. Taverns on the first
  two floors gather party candidates and reveal their surroundings; route
  markers guide players on earlier floors.
- Add the Yawning Cat party member, which explores nearby areas over time,
  and new tavern and cat artwork in sprite mode.
- Adjust Pegasus landings on barriers and Golem rubble according to the
  player's protections and party members.
- Improve sprite rendering and transitions, respawn effects, and pit landings.

## 6.3.3 - 2026-11-04

- Place both Stage 6 Rare Chimeras on floor 3 and replace those removed from
  floors 2 and 4 with regular Chimeras.

## 6.3.2 - 2026-11-03

- Widen sprite-mode field cells to a 4:5 shape, align the floor tiles with
  the cells, and redraw the floor, wall, stair and pit images for the new
  cell shape so they are no longer stretched.
- Refresh several character sprites: the Lifebringer Elf floats on a soft,
  slightly see-through cloud and has thick brows; the Isolated Elf wears a
  hermit's homespun robe and a cape of grass and moss; the Sylvan Elf loses
  its wings and offers a pot of flower nectar; the Flame Cobra's hood is made
  of glowing flame tongues.

## 6.3.1 - 2026-11-03

- Draw walls surrounded by other walls as flat gray cells in sprite mode,
  including buried walls at the dungeon's edges. Restore the regular wall
  rendering when adjacent or diagonally adjacent terrain is opened.
- Fix pit entrance markers remaining visible after a rewind restores the pit
  above them to its unopened state.
- Reorganize the interface and options descriptions and simplify the Stage 6
  introduction in the documentation.

## 6.3.0 - 2026-11-03

- Improve sprite-mode responsiveness by drawing the checkerboard floor as a
  cached image. Explored floors have the same brightness inside and outside
  the current view; walls retain their existing visibility shading.
- Draw buried outer walls as dark, flat surfaces, exposing columns when walls
  are broken. Align edge shading with the dungeon walls and stop enlarging
  characters when the mouse cursor hides.
- Use narrower Stage 6 maze sections, reserve the boss party's section before
  placing other parties, and adjust Buffalo food recovery and party placement.
- Add Stage 6 emergency ration support when rations are enabled; rations remain
  disabled by default.

## 6.2.1 - 2026-11-03

- Restore the sprite GUI's previous window size after maximizing on
  Ubuntu/Wayland by accepting window-manager resize dimensions without
  requesting another size during the resize callback.
- Keep the window height unchanged when resizing only its width, and update
  the English and Japanese READMEs to describe this behavior.

## 6.2.0 - 2026-11-03

- Spread the initial Stage 6 parties across fixed sections of the dungeon.
- Darken sprite-mode floors toward the outer walls and refresh creature and
  party-member sprites, including a spiral-funnel Loop, an almond-framed Ocular
  eye, a longbow for the Marksman, and a Romanesco-like Caltrop Plant head.
  Adjust member and Bison/Buffalo sizes and refine the Chimera's serpent tail.
- Make each Loop Companion rewind destination the new anchor. Subsequent
  rewinds cannot return to an earlier point, even when using a Loop Companion
  on another floor; later rewind destinations advance the anchor.
- Shorten the Loop Companion row in the English and Japanese READMEs and move
  details about anchors, retained knowledge, and trail markers below the table.

## 6.1.6 - 2026-11-02

- Offer to quit when F finds no reachable monsters, companions, elves, waiting
  members, stairs, or Collapse pits within the remaining LP. Check unexplored
  areas too, including hidden passages and exits beneath upper-floor pits when
  accompanied by the Dungeon Explorer. Count untriggered Collapses but exclude
  treasure chests and inactive Mimics.
- Support the confirmation in GUI and terminal modes. Choosing yes quits as Q
  does; choosing no returns to the normal F preview without consuming a turn
  or revealing unexplored terrain.

## 6.1.5 - 2026-11-02

- Arrange the stage selector in two columns of three stages, `[1]` through
  `[6]`, in both GUI and terminal modes. Navigate with arrow keys or the
  gamepad, or select a stage directly by number.
- Redraw several sprites in sprite mode:
  - Loop: a calm whirl of green ribbons with small cyan sparks, replacing the
    pocket watch.
  - Dungeon Explorer: a khaki pith helmet with a glowing amber stone as its
    headlamp, and a modern red-shafted ice axe.
  - Jester: a fuller two-pointed cap, a narrower mask, and loose puffed
    sleeves.
  - Healer: wide robe sleeves that hang down.
  - Komodo Dragon and Flame Cobra: wet, spotted amphibian skin in small
    triangular facets. The Komodo Dragon is larger, with a bigger, raised head.
  - Ocular: a clear cornea over an orange iris patterned with a cyan gear
    outline, replacing the cyan light in the pupil.
  - Toy chest (Stage 5): a softer glow inside.

## 6.1.4 - 2026-11-01

- Enlarge hovered field characters to twice their usual size in sprite mode,
  keeping their feet fixed and drawing them and their rank marks above the
  player's LP gauge. Restore their size when the pointer leaves the cell.
- Show hovered characters' localized names above their heads, using the status
  popup font and size; place names below characters at the dungeon's top edge
  to avoid clipping. Keep unidentified characters' names hidden.
- Include character glyphs in Japanese hover names, and show `Marksman(k)` and
  `Komodo Dragon(d)` in English through the translation catalogs.
- Show the mouse cursor in sprite mode for three seconds after its last
  movement, extending the time whenever it moves again.
- Round all LP and LVL changes in status popups to one decimal place, omitting
  trailing `.0`, including damage and level loss. Keep gameplay values unchanged.

## 6.1.3 - 2026-11-01

- Mark hidden passages discovered by the Dungeon Explorer with green ground
  light instead of text in sprite mode, matching pit entrance markers.

## 6.1.2 - 2026-10-31

- Show combat victory and defeat effects across all monsters or party members
  in Stage 5 and 6 party encounters.
- Update monster barrier rings when monsters are placed, moved, or respawned
  instead of recreating them each turn. Prevent new barriers beneath the player
  and on broken walls, including during Vortex rearrangements.
- Preserve overlapping and permanent barriers when barrier-bearing monsters
  move, and retain the Dread Wyrm's barriers after its defeat.
- Clarify party member descriptions and stage headings, add the Buffalo entry,
  and explain the Vortex's effect on map memory in the English and Japanese
  READMEs.

## 6.1.1 - 2026-10-30

- Add a saved combat and barrier damage effect duration setting, selectable
  from 0 to 0.5 seconds in 0.1-second steps; selecting 0 skips the effects.
  Apply the saved duration to graphical and terminal modes.
- Tighten settings-menu item spacing while keeping the control hints separate.

## 6.1.0 - 2026-10-30

- Make Stage 5 a fixed-map member-ability training ground and Stage 6 the
  four-floor boss and treasure dungeon.
- Add companion dialogue bubbles and training-room terrain to Stage 5,
  refine its layout, and support the same ASCII map markers on both floors.
- Reduce Guardian barrier damage to one third and correct tutorial pit
  landings and party rewind interactions.
- Add brief blue victory and red defeat effects, with slash and splash
  overlays in sprite mode; show the defeat effect after barrier damage.
- Refresh creature, treasure, and unidentified-object sprites, and dim
  unidentified sprites' ground discs.

## 6.0.1 - 2026-10-29

- Allow swords to break undiscovered hidden passages into ordinary floor.
- Keep Stage 5 monsters from appearing side by side, and prevent placement or
  respawning on Collapse pits and their landing cells.
- Prevent Stage 4 monsters from respawning on Collapse landing cells.

## 6.0.0 - 2026-10-29

- Add Stage 5, a four-floor dungeon with recruitable party members, monster
  parties, a Dread Wyrm boss, and treasure. Six professions offer distinct
  combat, healing, exploration, and experience-sharing abilities.
- Add Stage 6 as a two-floor test stage for trying all party member abilities,
  with repeat recruitment and a dedicated label in the GUI stage menu.
- Add Flame cobras and Buffalo, and update monster encounters, hazards, and
  rewards for the new dungeon. Dungeon Explorers can reveal hidden passages
  and climb pits; Rogues detect dangers and counter selected hazards.
- Add party member sprites with varied skin tones, and refresh character and
  terrain visuals, including Buffalo, Flame cobras, the Marksman, and barriers.
- Show brief status popups and the movement trail after a Loop Companion
  rewind, and improve sprite-view scrolling and party progress displays.
- Localize Japanese party member names in recruitment and warning messages.

## 5.9.0 - 2026-10-22

- Reduce poisoned attack power to one third, rounded up, and update the
  status display to match.
- Reduce Golem rock scatter to two tiles in each diagonal direction.
- Show identified monster types in white and unidentified types in gray in
  the strength column of the text GUI and terminal mode.
- Start with 120 LP and ease respawn penalties: lose 6 LP with a minimum of
  20, preserving LP above the normal maximum.
- Float the sprite GUI's LP gauge above the player and show the player's
  sword and Collector Elf upgrade on the sprite.
- Refine sprite visuals with irregular Collapse pits, fewer and larger rocks,
  fallen rocks on the floor below pits, and darker wall bases.
- Shrink the Wyrm sprite and enlarge the rare Erebus's stolen halo to make
  their appearances easier to distinguish.

## 5.8.7 - 2026-10-21

- Speed up the sprite GUI, especially while scrolling, by skipping offscreen
  terrain processing and drawable creation while preserving image overhangs,
  rank marks, and the field beneath the translucent strength panel.

## 5.8.6 - 2026-10-21

- Redraw the sprite GUI's stairs as marble plates floating by magic, turning
  back at a landing: the way up hovers above the floor with shadows beneath,
  the way down sinks into a dark opening.
- Draw stairs and Collapse pits larger than their cell, spreading over the
  explored floor beside them; pits are 1.2 times their former size.
- Redraw the sprite GUI's walls, floor, stairs and pits for the wider 15:20
  field cells instead of stretching the former images.

## 5.8.5 - 2026-10-21

- Widen the sprite GUI's field cells (13 to 15 px at scale 1) so characters
  overflow their cells less; sprites, ground discs and the strength column
  keep their size.
- Open the sprite GUI window at about 16:9, showing part of the field and
  scrolling with the player.
- Size the strength sidebar labels and spacing to fit the HUD text, and draw
  checkerboard floors faster from a cached fixed pixel grid.

## 5.8.4 - 2026-10-20

- Clarify sprite GUI resizing: field zoom follows window height while the HUD
  keeps the configured interface size.

## 5.8.3 - 2026-10-20

- Make the sprite GUI resizable, with field scrolling, visible edge margins, and
  HUD rows that size themselves from the window width.
- Scale status, progress, and floor displays with the configured font, and keep
  the LP gauge compact.
- Improve large-window rendering performance with a reduced-resolution game
  frame while keeping menus and HUD overlays at native resolution.
- Show the stage beneath a translucent strength panel while scrolling, and
  improve visibility of the FOV boundary.
- Refine sprite rendering with white rank marks, a recolored Komodo dragon, and
  consistent translucent green companion effects.

## 5.8.2 - 2026-10-20

- Draw a faint yellow ground disc around stairs in the `--sprites` GUI so they stand out.

## 5.8.1 - 2026-10-20

- Fix sprite GUI rendering when its drawable cache is not initialized, and
  preserve dim sprite shading in map mode.

## 5.8.0 - 2026-10-20

- Add the `arlq --sprites` GUI, which draws characters as transparent images
  rendered from 3D models seen 60 degrees from above. Characters without a
  sprite, and unidentified ones, keep their text display. Controls, rules,
  FOV and menus are shared with the original Pyglet GUI.
- Show strength and status colors (including low-LP warnings, poison and
  beatable bosses) as fading discs on the ground under each sprite, and
  empowered ranks as raised apostrophes at the sprite's upper right.
- Surround companions with a faint green light pillar, show the travelling
  companion small at the player's shoulder, darken elves already met, and
  enlarge characters next to the player.
- Draw walls as marble colonnades, walls a Golem raised as its rubble, floors
  as checkerboard flagstones, barriers as fires on the floor (smoke near a
  protected player), stairs as marble flights, and Collapse pits as holes
  broken through the floor. Explored areas outside the view are darker.
- Show identified characters' sprites in the strength column.

## 5.7.3 - 2026-10-03

- Keep the game-over screen interactive when continuing a fast-forward trace
  replay.
- Use the current UI language during trace replay instead of overriding it
  with the language saved in the trace.

## 5.7.2 - 2026-10-03

- Add overshoot assist, which restores position, LP, and turns when returning
  to an eligible recent cell within five turns. Mark possible return cells
  with a dark gray dot.
- Remove defeated Mimics from the floor.
- Exclude marksman damage from the reachable-area estimate and clarify that
  the preview may differ from actual reachability.

## 5.7.1 - 2026-10-03

- Preserve the restored LP when a Loop Companion rewind reaches the normal
  turn-end processing.

## 5.7.0 - 2026-10-03

- Automatic repeat stop: Improve movement feel by stopping only just before
  moving into a visible monster, companion, elf, or known `O` pit. It no longer
  stops while an entity is still two Manhattan cells away.
- Make Collapse a level-1 monster with no LP recovery. Entering its cell reveals
  neighboring pits except at walls; entering a pit drops the player to the next
  floor. Defeated Collapses disappear and do not respawn.
- Allow Vortex to reposition Collapse only where the center is floor and its
  neighbors are floor or wall on both the current and next floors.

## 5.6.0 - 2026-10-03

- Add configurable gamepad buttons for the controls help and range/floor
  preview, with hold or toggle behavior. Allow loading the defaults from the
  settings screen.
- Support assigning supported controller buttons or leaving either mode
  button unassigned, and reflect custom assignments in the help text.

## 5.5.4 - 2026-10-03

- Add linked screenshot thumbnails to the English and Japanese READMEs.

## 5.5.3 - 2026-10-03

- Show “No repeat” for the disabled movement repeat interval in the settings menu.

## 5.5.2 - 2026-10-02

- Add gamepad controls to hold button 2 for reachable-area previews and floor
  inspection, and use button 3 to open or close the controls help.
- Ignore diagonal D-pad input so it cannot cause unsupported diagonal movement.
- Clarify the Japanese gamepad button labels.

## 5.5.1 - 2026-10-02

- Reduce the GUI message font slightly to make event messages easier to read.

## 5.5.0 - 2026-10-02

- Add GUI gamepad navigation and movement with the D-pad or left stick, with
  repeat timing shared with keyboard movement.
- Add configurable automatic repeat stopping near known hazards and displayed
  entities, and after encounters and other movement events. It is enabled by
  default and can be changed in Settings or with `--auto-repeat-stop` and
  `--no-auto-repeat-stop`.

## 5.4.1 - 2026-10-02

- Organize CLI options into general, GUI, terminal, and development groups.
- Keep GUI-only options out of `arlq-cli` and order general and development
  options consistently.
- Apply `--replay-interval` to trace replay in both GUI and terminal modes, and
  document the option in the developer notes.

## 5.4.0 - 2026-10-01

- Refactor command-line startup and shared display calculations into dedicated
  modules without changing gameplay behavior.

## 5.3.6 - 2026-10-01

- Unify Stage 1 and 2 turn processing while preserving Stage 2's passive High
  Elf and rank-1 monster respawns.
- Make the amulet ineffective against barriers while carrying the Cursed Sword,
  and show the barrier's red background only when it causes damage.
- Add irregular notches to Stage 1's filled side columns and filled rooms, and
  prevent wall features from enclosing floor cells.

## 5.3.5 - 2026-10-01

- Allow interrupting trace replay with the window close button, `q`, or `Esc`.
- Make terminal trace replay instant by default and add `--replay-interval` to
  control its pacing independently of key repeat.

## 5.3.4 - 2026-10-01

- Configure each stage's boss explicitly and use its configured label in the
  progress display. Link Mimics to their configured boss, including empowered
  variants such as the Stage 4 Fire Drake (`F'`).

## 5.3.3 - 2026-10-01

- Change the Cursed Sword to consume vitality when breaking walls or contacting
  monsters, while keeping its triple attack power and three wall breaks.

## 5.3.2 - 2026-10-01

- Keep Stage 4's fifth floor outside the island-room split layout.

## 5.3.1 - 2026-10-01

- Have the Lifebringer Elf cure poison when met.
- Restrict Stage 4 Collapse traps to floors 2–4.
- Restore Loop Companion rewinds using the game-start turn count, and show both
  the game turn and operation count after a rewind.
- Start the Stage 1 and 2 turn counter at 0, matching Stages 3 and 4.

## 5.3.0 - 2026-10-01

- Add a two-turn cooldown between Marksman shots.
- Rebalance Stage 4 Bison populations.

## 5.2.3 - 2026-09-30

- Make the Stage 2 High Elf a passive decoy and rebalance monster populations
  across Stages 1, 2, and 4. Add a Caltrop Plant to the first four Stage 4 floors
  and reduce the Golem population on each floor.
- Delay Collapse falls until the turn after the player steps onto the affected
  cell. Let Marksman arrows pass through caltrops, Collapse terrain, and barriers,
  and favor spawn and respawn locations with more open firing lanes.
- Expand `--trap-test` with a Marksman, Caltrop Plant, Collapse trap, and Golem,
  plus a 3-by-3 arena and a safe lower-floor landing.

## 5.2.2 - 2026-09-30

- Increase the Stage 2 Bison (`b`) population to six and remove the Sylvan Elf
  (`S`) from Stage 3.
- Update the English and Japanese README stage descriptions to match.

## 5.2.1 - 2026-09-30

- Show empowered monster ranks on the strength gauge and refine GUI field and
  font sizing for clearer alignment.

## 5.2.0 - 2026-09-29

- Add the Sylvan Elf (`S`), which grants Fairy Nectar to extend future companion
  durations, and keep it at its encounter point to respawn the player.
- Move elf floor information onto the field overlay and show discovered or
  fatal-contact floors for the Cursed Chimera (`C`).

## 5.1.4 - 2026-09-29

- Place two Collapse traps in Stage 4 and show their revealed adjacent cells as
  `O` terrain while keeping the trap center marked as `?`.
- Preserve Stage 4's persistent barriers when a Vortex rearranges the floor.

## 5.1.3 - 2026-09-29

- Make the Lifebringer permanently raise the LP maximum to 105 while restoring
  LP to 120, without raising the player's level.
- Keep the respawned Lifebringer identified, and show an elf's floor after its
  identity is revealed by the Nomicon.

## 5.1.2 - 2026-09-28

- Adjust monster rosters and balance across Stages 3 and 4.
- Add a randomly placed extra stair pair to one Stage 3 floor transition.
- Remove the old Life-bringer Elf from its original cell after contact and mark
  its respawned instance as already met.

## 5.1.1 - 2026-09-28

- Match the Vortex effect area to the FOV ellipse proportions and reduce its
  width to 80% of the field.
- Release Stage 4 in the standard stage selection menu and remove the `--dev`
  option previously required to show it.
- Update the English and Japanese README descriptions for Stage 4.

## 4.9.5 - 2026-09-28

- Expand the Vortex's affected area to 90% of the field width.
- Keep the Loop Companion revealed at its new position after a rewind.

## 4.9.4 - 2026-09-28

- Add a yellow low-LP warning when the player's LP is 40 or below.
- Allow the Pegasus to jump over barriers.
- Refine the field-of-view ellipse and limit the Vortex's relocation and map-reset
  effects to its affected area, expanded to 85% of the field width.

## 4.9.3 - 2026-09-28

- Expand experimental Stage 4 to five floors with revised room layouts,
  grouped stairs, barriers, and floor-specific monster placements.
- Add the Lifebringer Elf and random-floor respawns for Rare Erebus (`E`),
  Caltrop Plant (`X`), and Vortex (`V`).
- Improve multi-floor progress, map exploration, and stair navigation.

## 4.9.2 - 2026-09-27

- No player-visible gameplay or UI changes.

## 4.9.1 - 2026-09-27

- Show stacked sword and elf attack bonuses together in the status display.

## 4.9.0 - 2026-09-27

- Keep Stage 4 behind the `--dev` stage-selection option while it remains
  experimental; move its detailed description to `docs/stage4.md`.
- Add a keyboard controls help screen and an LP-based preview of reachable
  explored cells.
- Improve terminal map display and combat-loss respawn placement.

## 5.1.0 (dev) - 2026-09-27

- Add a keyboard controls help screen accessible with `H` from the stage
  selection screen and during gameplay.
- Clarify that `M` enters map and entity display mode and cannot be undone.

## 5.0.3 (dev) - 2026-09-27

- Add an `F`-key preview of explored cells reachable with the player's
  remaining LP.
- In terminal `--dots` mode, omit dots from known field cells.
- Prefer combat-loss respawn locations at least 25 Manhattan steps from the
  monster, falling back to the existing random placement after ten attempts.

## 5.0.2 (dev) - 2026-09-27

- Show Mimics as `M` in mapping mode before they are defeated, and remove them
  from the map after defeat.

## 5.0.1 (dev) - 2026-09-26

- Fix Stage 4 initialization when selecting random monster floors.
- Show the current floor as a fraction on multi-floor stages, including the
  result screen, and label the elapsed turn count as `TURN`.
- Use the King's Dread Wyrm slaying request as the Stage 4 opening message.

## 5.0.0 (dev) - 2026-09-26

- Add experimental Stage 4, a four-floor stage with new monsters, traps,
  floor transitions, and a rematchable trap test arena.
- Add Collapse traps that drop the player to the floor below, and allow
  players to inspect explored maps on adjacent floors in Stages 3 and 4.
- Adjust monster placement and combat balance, and unify stage completion
  objectives across Stages 3 and 4.
- Preserve companion and treasure state across gameplay events, and make Loop
  Companion rewinds deterministic and repeatable.

## 4.8.1 - 2026-09-25

- Improve terminal UI contrast on light themes: use the terminal's default
  text color for the strength column and player, and show the LP gauge with
  explicit `#` and `-` characters.
- Clarify that `--dots` applies to terminal UI launches only.

## 4.8.0 - 2026-09-25

- Add a color-based `arlq-cli` map view, with `--dots` as an alternative for
  unexplored areas. Preserve map-cell backgrounds behind characters and the
  Stage 3 Javelin Elf follower.
- Pace terminal trace-watch playback using the configured GUI key-repeat
  interval.

## 4.7.2 - 2026-09-25

- Show the destination floor immediately after using stairs in Stage 3.
- In `arlq-cli`, keep stair symbols visible when a respawn checkpoint shares
  their cell.

## 4.7.1 - 2026-09-25

- No player-visible gameplay or UI changes. Add the Japanese catalog entry
  for the experimental Stage 4 message and regression tests for GUI Settings
  Escape navigation.

## 4.7.0 - 2026-09-25

- Add configurable key repeat to GUI movement, with an option to disable it,
  and support configuring its interval from Settings or the command line.
- Expand the GUI scale range to 50%-400% and improve the Settings and stage
  selection screens, including Japanese localization and Escape handling.
- Document GUI-only command-line options separately from shared options.

## 4.6.9 - 2026-09-24

- Add a configurable Pyglet GUI scale with a persistent Settings menu and
  the `--scale` command-line option.
- Keep the experimental Stage 4 implementation in the source while limiting
  released game entry points to Stages 1-3.

## 4.6.8 - 2026-09-23

- Ease Stage 2 by increasing ordinary Bison (`b`) from three to four,
  reducing empowered Bison (`b'`) from three to two, and adding one Rare
  Amoeba (`A`).
- Set empowered monster strength to three times its base level plus 10.

## 4.6.7 - 2026-09-23

- Fix Pegasus wall jumps after a Stage 3 rewind. The restored companion is
  recognized by its tribe character even when rewinding creates a copy of
  its tribe data.

## 4.6.6 - 2026-09-22

- No player-visible gameplay or UI changes.
- Separate legacy gameplay event results from trace JSON serialization so
  gameplay rules no longer depend directly on `TraceRecorder`.

## 4.6.5 - 2026-09-22

- No player-visible gameplay or UI changes.
- Refactor shared item and movement handling, keep command-line gameplay
  options local to each run, type the Stage 3 floor state, make renderer
  calls keyword-only, and replace exception-based Stage 3 turn control with
  explicit contact results.

## 4.6.4 - 2026-09-22

- No player-visible gameplay or UI changes.
- Add internal developer/testing CLI options `--trace-record`,
  `--trace-replay`, `--trace-replay-output`, and `--trace-replay-watch`
  for recording a play session's inputs and results to a JSON trace file
  and replaying it headlessly, to help catch behavior regressions across
  code changes. Not documented in `README.md`/`README-ja_JP.md`; see
  `docs/gameplay-trace-spec.md` and `docs/developer.md`.

## 4.6.3 - 2026-09-22

- Revise the English and Japanese event messages so both languages
  describe the same outcome. The stage-clear banner now says the
  treasure chest was obtained, and the defeat banner says the player
  collapsed from hunger.
- In English, drop an initial letter when the creature's name already
  shows it, such as in the Dragon's treasure-chest message. Japanese
  messages keep the alphabet letter beside the katakana name.
- Show the "terminal is too small" prompt in Japanese when the UI
  language is Japanese.

## 4.6.2 - 2026-09-22

- Fix the High Elf (`H`) and Stage 3's Collector Elf (`K`) so that, while
  their condition remains unmet, contacting them a first time only shows
  their refusal message, but any contact after that now sends the player
  to a random location on the map (previously Stage 2's High Elf ignored
  the shared "twice in a row" escape mechanic entirely, and Stage 3's
  Collector Elf never escaped at all).

## 4.6.1 - 2026-09-21

- Fix the GUI window title when launching with `LC_ALL=C`.
- Align the `arlq-cli` stage-selection heading with its options.

## 4.6.0 - 2026-09-21

- Fix a soft-lock: losing combat twice in a row to the very same monster
  (with no other monster contact in between) now sends the player to a
  random location instead of back to the checkpoint, so a too-strong
  monster occupying the only corridor into an area can no longer
  permanently block progress.
- Fix a soft-lock in Stage 3: contact with the Isolated Elf (`I`) after
  the first now always sends the player elsewhere, so a player who
  reaches the elf's sealed room (e.g. via a Pegasus jump) can no longer
  get trapped inside.
- Align the English README's Game Description section structure with the
  Japanese version, and document the new escape mechanics above.

## 4.5.1 - 2026-09-21

- Fix Stage 3 monster color coding (red/beatable-blue) to include the
  Javelin Elf and Collector Elf attack bonuses, matching actual combat
  resolution. Previously an empowered monster could be shown as
  unbeatable (red) while still dying on contact.

## 4.5.0 - 2026-09-21

- Add Japanese localization: in-game event/status messages and the
  stage-select screen, in both the GUI and terminal frontends, can now
  display in Japanese. Status-bar abbreviations and item names stay in
  English to avoid breaking fixed-width layouts.
- Add the `--lang {auto,en,ja}` option. `auto` (the default) detects the
  language from the environment: an explicit `LC_ALL`/`LC_MESSAGES`/`LANG`
  environment variable is honored first, then falls back to a native
  per-OS UI-language lookup (Windows, macOS) when none is set.

## 4.4.2 - 2026-09-20

- Fix the low-LP and poisoned player indicators so both can be shown at
  once: low LP now always highlights the "@" background red and poisoned
  always tints its text magenta, switching to black text when both apply,
  in both the GUI and terminal renderers.

## 4.4.1 - 2026-09-20

- Replace the ">X" beatable-monster status indicator with a right-edge
  strength column that ranks the stage's monsters and the player by
  strength, in both the GUI and terminal renderers.
- In the GUI, give the strength column a tinted background and padding so
  it reads as distinct from the field, and shrink the field's wall-only
  edge columns to keep the window compact.
- Fix the Stage 3 status line spacing and the message overlapping the
  C/I/J/K/H/W/T progress flags in the GUI.
- Fix the player's low-LP and poisoned indicators so they no longer use the
  same colors as dangerous/beatable monsters.

## 4.4.0 - 2026-09-19

- Shrink Stage 1 to a smaller introductory map.
- Note that the Pegasus companion appears from Stage 2 onward.

## 4.3.1 - 2026-09-19

- Add a CPython compatibility matrix for Python 3.10 through 3.14.
- Update installation documentation with PyPI and GitHub installation paths,
  terminal requirements, and package and Python-version badges.

## 4.3.0 - 2026-09-19

- Replace the curses terminal UI with a Blessed terminal UI and add Blessed as
  a runtime dependency.
- Add the `--terminal` option and retain `--curses` as a deprecated alias.
- Pause the terminal game when the terminal is smaller than 80x24, then resume
  and redraw the game after the terminal is enlarged.
- Remove the separate curses UI implementation.

## 4.2.1 - 2026-09-19

- Adjust monster spawn populations and update the corresponding gameplay
  documentation.
- Clarify the Stage 3 objectives, floor behavior, companions, and progression.

## 4.2.0 - 2026-09-19

- Rebalance empowered monsters in Stages 2 and 3, including their populations
  and combat difficulty.

## 4.1.2 - 2026-09-18

- Fix Stage 3 rewind handling so encountered-elf state is restored together
  with the corresponding Stage 3 flags.

## 4.1.1 - 2026-09-18

- Place the Nomicon companion on every Stage 3 floor.

## 4.1.0 - 2026-09-18

- Replace the Pygame graphical backend with Pyglet.
- Respawn carried Stage 3 companions on their origin floors.
- Refactor Stage 3 state handling and fix Escape-key and related rule issues.

## 4.0.0 - 2026-09-18

- Add Stage 3, including multiple floors, elves, the Dread Wyrm, and its
  related objectives and progression.
- Add `--rematch` support for replaying the most recently started stage with
  the same seed.
- Align Stage 3 status, rewind, and high-elf behavior across game stages.
