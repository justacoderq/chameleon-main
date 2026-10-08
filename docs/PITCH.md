# Short pitch

One campaign needs to work across a square post, a portrait story and a wide banner.
Stretching the finished picture distorts assets and loses the designer's hierarchy.

Chameleon takes the original design's elements and searches for a new arrangement.
A small Hugging Face model runs on our laptop to interpret the role of the copy.
Our layout engine preserves groups, measures text with the brand fonts, keeps images
proportional, and compares candidate arrangements for fit, hierarchy and contrast.

We test both the design data and the visual result. Every element must survive, and
our reports distinguish valid geometry from readable design. That distinction matters:
our extreme banner still has tiny copy, and we show that limitation openly.

The preview panel lets someone choose a canvas, compare the result with the original,
and export the design. The Express integration adds the rendered preview to the document.
Our next improvements target dense groups, extreme ratios, and the verified official renderer.

## Demo sequence

1. Start the engine with the real local model and show the source design.
2. Resize the Level 2 design to a wide banner. Compare the stretch baseline with reflow.
3. Show JSON preservation and the visible rendering together.
4. Show the extreme Level 3 result and its readability warning; do not hide weaknesses.
5. Show the local-model offline test and held-out report. Explain these are local proxies,
   not official Adobe scores or a proof of generalization to every hidden design.
6. After Adobe-host validation, record insertion into Express for the finale video.

The generated 18-second AVI is a silent engine walkthrough made from actual sample
outputs. It is deliberately labeled as development rendering and not live Express footage.
