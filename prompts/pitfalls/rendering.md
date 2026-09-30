# Event Sheet Pitfalls: Rendering

Sources and the rule for adding an entry are in the index,
[event-sheet-pitfalls.md](../event-sheet-pitfalls.md).

- A Text object has no *Set color*: `set-default-color`, listed in
  `plugins/_common.json` and printed by `lookup_ace.py Text color`, is
  refused by the editor on a Text with `missing action id
  'set-default-color'`, and the project does not open. Text's colour is
  its font colour, *Set font color* (`set-font-color`). A plugin file lists
  the shared ACEs it gets under `commonAces`, and `lookup_ace.py` and
  `check_project.py` follow it. [plugins/text.json `set-font-color`;
  observed in a game project, r495.2 editor, 2026-09-23]
- *Set width* stretches a Sprite's whole image, repeats a Tiled Background's,
  and on a 9-patch stretches or tiles the middle while the corners keep their
  size. A bar with a painted fill is therefore a Tiled Background, which
  shows a cut of the painting below its own width, and a bar with caps is a
  9-patch, whose width must stay positive. [manual:
  plugin-reference/tiled-background.md "display an image in a repeating
  pattern"; plugin-reference/9-patch.md "a Sprite object, which just stretches
  its entire image", "useful for representing things like progress bars";
  reference: references/progress-bars.md]
- A Tiled Background's *Set image X scale* and *Set image Y scale* take a
  percentage, while the layout file writes the same property as a fraction:
  `"image-scale-x": 0.3333` in `layouts/` is `33.33` in an event, and an
  event that writes `Self.Width / Self.ImageWidth` shrinks the tile a
  hundredfold. *Set image Y offset* moves the image down as the offset
  grows, so a pattern that flows upward takes a falling offset, such as
  `P - time * speed % P`, where the wrap `P` is a whole number of tile
  periods, which also keeps the offset small as the manual asks. [manual:
  plugin-reference/tiled-background.md "stretching ... by a percentage",
  "wrapping the image offset back to 0"; observed in a game project, r504
  preview, 2026-10-01: a scale of width ÷ image width read 0.0019 through
  the script interface, and screenshots 0.12 s apart showed the chevrons
  moving down while the offset grew]
- A bar grows from its origin. Every filling bar in the examples has its
  origin on the edge it grows from, (0, 0) or (0, 0.5); a cover that hides
  from the right has (1, 0.5); a 0.5 origin grows both ways from the middle.
  [examples: berry-harvester ProgressBar, jetpack FuelBar, flatland-golf
  PowerBarCover, test-your-might MightLevelBar (0.5, 1)]

- Drawing Canvas *Fill polygon* draws nothing when two consecutive points of
  the polygon coincide, a closing point that repeats the first one included;
  the rest of the sheet runs on and no error is logged. Add a closing point
  only when it is a point of its own, or count the points in a variable and
  loop over that. [observed in a game project, r502 preview, 2026-09-24]
- A blend mode such as *Destination in* only touches the pixels under the
  object's own quad: a mask sprite the size of the shape it reveals leaves
  everything outside its bounding box untouched, and the layer needs *Force
  own texture* or the blend hits the whole screen. Size the mask to cover
  everything it must erase, or keep the content inside its box. [manual:
  project-primitives/layers.md "Force own texture"; example:
  mask-effect-puzzle, layer HiddenWorld; observed in a game project,
  2026-09-17]
- A Text object wraps at its own width and draws only the lines that fit its
  height. Text longer than the box sized for the placeholder gains a line
  that is cut off, and with centre or bottom vertical alignment the lines
  already shown move up as it does. Size the box for the longest text at the
  font size and line height, or after *Set text* resize it from
  `Self.TextHeight` plus a margin, with the width fixed: `TextWidth` and
  `TextHeight` measure the text as wrapped inside the current box, so
  `TextWidth` never grows the box past its width. Both are current in the
  action right after *Set text*. Check what else moves the lines before
  choosing the size:
  - Origin: a resize keeps the origin still and grows the box away from it.
    With a top origin the first line stays put; with a centre origin the
    box grows both ways and the first line moves even under top alignment.
    Put the origin on the edge the text must keep, as a bar keeps the edge
    it grows from.
  - Wrapping: *Word* breaks only at spaces and hyphens, so Chinese,
    Japanese or Korean text needs *CJK*, which breaks between characters
    and wraps CJK punctuation properly. The same string takes a
    different number of lines under each mode; size for the mode set.
  - Direction and horizontal alignment decide the edge a line starts from:
    an RTL or right-aligned text widened with a left origin moves.
    [inference from the manual's property descriptions, unverified at
    runtime]

  [manual: plugin-reference/text.md "Wrapping", "Vertical alignment",
  "Text direction", "Origin", "TextWidth"; examples: text-based-adventure
  `Set height to min(Self.TextHeight + 4, 644)`, flowchart-questionnaire
  sizes a background from `TextWidth + 10`, `TextHeight + 10`; observed:
  2026-09-23]
- A single line taller than its Text box is not hidden: it draws with the
  bottom of the glyphs cut off at the box edge. Size is in points, so a
  line needs about `size × 4/3 × 1.2` pixels of height; a 44 pt bold price
  in a 46 px tall box lost the bottom of its digits. A *Set font size* at
  runtime, such as a bigger critical hit number, needs the box sized for
  the largest size. [manual: plugin-reference/text.md "Size"; observed in
  a game project, 2026-09-28]
- *Move to top* moves only the instance it runs on. A hierarchy's children
  keep their places in the Z order, so a dragged piece whose parent went to
  the top still draws its body, face and label under the pieces created after
  it. Pick the children (*Pick children*) and move every part to the top,
  bottom part first, as the parts should stack. [manual:
  plugin-reference/common-features/common-actions.md "Move to top", "top of
  its current layer"; observed in a game project, r503 preview, 2026-09-29]
- *Set color* is a tint: each channel of the image is multiplied by the
  colour, white restoring the original. A part drawn in white takes the
  colour exactly and black outlines stay black, but white highlights are
  tinted too, so a piece coloured by level is drawn with a white fill and its
  highlights on a separate child that keeps its colour. [manual:
  plugin-reference/common-features/common-actions.md "Set color"; observed
  in a game project, r503 preview, 2026-09-29]
- A Text object draws its text into a texture of its own, and a new text
  or a new font size redraws and re-uploads that texture on the next frame.
  *Set font size* every tick during a pop tween therefore redraws the text
  and uploads a new texture every frame, at the device's full resolution;
  in a merge game each damage number that popped this way was redrawn
  every frame, 175 texture uploads a second at 144 Hz, most of the Text
  cost of the whole game. *Set text* to the string already shown costs
  nothing: the runtime compares and returns. Animate a number with things
  that move the finished texture (position, angle, opacity), or draw it
  with a Sprite Font and tween its *Scale*, which redraws nothing: after
  that change the same game redrew no damage number and no countdown.
  *Set resolution mode* to *Fixed* only stops redraws caused by the display
  scale, not by the font size. [manual: plugin-reference/text.md "Set
  resolution mode"; observed in a game project, r504 export, runtime
  `_SetText` source and a counter on `_OnBeforeRender`, 2026-09-30]

- A Sprite Font draws each character as its whole cell of the image and
  moves on by the character's width from *Spacing data*, so a glyph is
  drawn against the left edge of its cell, and an outline that reaches
  past that width into the next cell stays whole: the next character is
  drawn over it. Its colour and *Set color* tint every pixel, the outline
  as well; bake each colour into its own image, one object per colour, as
  white and gold damage numbers take two. A character that would end past
  the box's width is not drawn, and a line taller than the box is drawn
  from the top instead of centred: size the box for the longest text at
  the largest scale a pop tween reaches. [manual:
  plugin-reference/sprite-font.md "Re-coloring SpriteFonts", "Sprite
  font"; editor r504 `plugins/general/spritefont/spritefontText.js`
  `Draw`, `_LayoutText`; observed in a game project, r504 preview,
  2026-09-30]
