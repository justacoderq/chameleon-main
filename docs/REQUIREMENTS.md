# Brief-to-deliverable map

Source: Final Chameleon Challenge.pdf, especially pages 5-8 and 10-14.

| Brief requirement | Implementation / evidence | Remaining work |
| --- | --- | --- |
| Standalone source+target to resized JSON | engine.resize.resize, batch main | Hidden official evaluation |
| Same elements/IDs, no asset regeneration | Deep copies, immutable-field audit, tests | Official scorer confirmation |
| Preserve copy/font families/brand properties | Only geometry/font size change | Pixel-level font parity |
| Images proportional and rotated bounds inside | Uniform image/group transforms, rotated audit | More real designs |
| Readable, intentional layouts | Structure-aware reflow (preserve/stack/split/row) refereed against partition search; renderer-exact text fitting | Fine print on the smallest banners |
| Offline local model | Bundled FLAN snapshot, required mode, socket-blocked inference test | Organizer model approval |
| Standard container | Dockerfile, build-time weights, offline environment | Verified: FAQ command, `--network none`, 51/51 tasks valid |
| Official PNG output | Explicit official renderer entry point, cr-renderer pinned | Verified locally and in Docker |
| Engine README | README.md and architecture notes | Freeze dependency lock after verified build |
| Adobe engineering explanation | Architecture, results and work log | Live walkthrough |
| Express add-on | Panel + local engine service + SDK image insertion | Panel verified in Chrome; Adobe-host validation |
| Short pitch | docs/PITCH.md | Rehearse with measured live outputs |
| Brief demo video | Generated AVI walkthrough, reproducible script | Player QA; live Express recording for finale |

The Express panel accepts structured Chameleon JSON and inserts its rendered result
as one image. It does not extract an arbitrary native Express document or import output
as individually editable Express nodes. The JSON download preserves the separate elements.

## Ambiguities to confirm, without inventing rules

- The exact approved model list and parameter/size limit are absent from the supplied brief
  ("being finalized"). FLAN-T5-small is 77M parameters; `--model off` runs without it.
- Reference hardware is described as Apple M5 Pro but CPU/RAM/GPU limits are unfinished.
- The provided Docker command uses linux/amd64; confirm how this maps to the reference Mac.
- The complete target catalogue, weighted rubric, code-freeze date and submission portal
  are not provided. Development target sizes are representative, not an official catalogue.
- FAQ.md references a stage-one viewer, but PDF page 8 places the add-on in the finale.
- The finale creativity section mentions imagery regeneration, while page 12 calls it
  disqualifying. This baseline always preserves the supplied assets.

Do not claim submission readiness until official rendering, offline Docker execution,
model eligibility and the organizer's delivery instructions are confirmed.
