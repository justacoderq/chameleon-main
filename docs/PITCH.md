# Short pitch

One campaign needs to work across a square post, a portrait story and a wide banner.
Stretching the finished picture distorts assets and loses the designer's hierarchy.

Chameleon reads the design's structure — logo, hero image, headline, buttons,
badges — and builds genuinely different layouts for the new canvas: the original
composition rescaled, a stack, a hero-beside-copy split, or a banner row. A small
local model helps tell a headline from legal copy. Text is fitted with the same
fonts and wrapping as the official renderer, and a second independent engine acts
as a safety net: an audit referee ships whichever output is cleaner.

We test both the design data and the visual result. Every element must survive, and
our reports distinguish valid geometry from readable design. That distinction matters:
on the tightest banners, supporting copy becomes fine print so the headline stays
readable, and we show that trade-off openly.

The preview panel lets someone choose a canvas, compare the result with the original,
and export the design. The Express integration adds the rendered preview to the document.
The generated hidden-style suite covers 5,040 cases with zero measured text
overflows. A separate 10,570-case mutation suite had zero crashes and invalid
outputs, but did find two overflows in an extreme long-copy mutation on tiny
canvases. These generated local proxies are not the organizer's hidden test
set; the README and results report include the quality warnings and limitations.

## Demo sequence

1. Start the engine with the real local model and show the source design.
2. Resize the Level 2 design to a wide banner. Compare the stretch baseline with reflow.
3. Show JSON preservation and the visible rendering together.
4. Show the Level 3 design moving across platform formats (docs/media/tour-level3.gif),
   then the 728×90 banner and its fine-print trade-off; do not hide weaknesses.
5. Show the local-model offline test and held-out report. Explain these are local proxies,
   not official Adobe scores or a proof of generalization to every hidden design.
6. After Adobe-host validation, record insertion into Express for the finale video.

The generated 18-second AVI is a silent engine walkthrough made from actual sample
outputs. It is deliberately labeled as development rendering and not live Express footage.
