# Express panel and local engine

The panel supports sample selection, source/task JSON upload, target sizes, local model
execution, before/after preview, JSON/PNG downloads and an Add preview to Express button.
The button uses the documented SDK addImage API. It inserts a flattened preview; it
does not imply that the separate JSON elements are editable Express nodes.

## Local use

    python -m engine.service --renderer pillow --model required

Open http://localhost:5241. For official rendering, omit --renderer pillow after the
cr-renderer dependency has been installed. Brand assets are read from brand_kit/assets.
The service binds only to loopback and does not require a cloud account.

## Adobe-hosted development check

1. Set up a trusted localhost TLS certificate using your normal development tooling.
2. Start the same service with --cert path/to/localhost.pem --key path/to/localhost-key.pem.
3. Enable add-on development in your Adobe Express account and load the local add-on
   from https://localhost:5241 using addon/manifest.json.
4. Allow the browser's local-network access prompt if shown, as described by Adobe.
5. Choose a sample or upload JSON, resize, compare both previews, download JSON, then
   click Add preview to Express and confirm the image appears on the active page.
6. Verify error states: missing model, unavailable engine, malformed JSON, and tiny target.

The service hosts the panel and API on the same origin. It deliberately does not use
wildcard CORS. A separately hosted/public add-on would need an explicit allowed origin,
a deployed engine strategy and authentication. No public deployment was performed.

## Verification status

Panel JavaScript syntax, manifest/DOM references, service validation and generated PNG
responses are tested locally. Browser discovery returned no connected browser, so no
UI clicks, screenshots of this panel, or Adobe host behavior have been verified yet.
Tests of the HTTP service do not substitute for browser or Adobe integration tests.

References: [Adobe add-on development](https://developer.adobe.com/express/add-ons/docs/guides/getting-started/hello-world),
[local network access FAQ](https://developer.adobe.com/express/add-ons/docs/guides/support/faq),
[image import](https://developer.adobe.com/express/add-ons/docs/guides/learn/how-to/use-images).
