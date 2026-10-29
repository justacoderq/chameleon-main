# Challenge sample assets

These are stand-in assets and fonts supplied for the three sample designs. They
are useful for reproducing the repository's sample renders; they are not
production Adobe brand assets. The engine treats asset IDs and font properties
as input data and does not special-case these filenames.

## Images

| File | Sample use |
|---|---|
| `solstice_bg_gradient.png` | Full-bleed background |
| `solstice_logo_lockup.png` | Transparent white logo lockup |
| `solstice_bottle.png` | Product image |

The Level 3 sample intentionally references `solstice_holiday_badge_2025.png`,
which is not present. Keep it absent when reproducing that missing-asset test.
The renderer handles it as a placeholder rather than failing the task.

## Fonts

The seven Solstice-named font files are stand-ins matching the sample schema:
Lora-derived serif files and Poppins-derived sans-serif files. Their metadata
supports the sample `font_family`, weight, and style values. They are retained
to make the supplied examples reproducible; they should not be represented as
the final organizer asset kit.
