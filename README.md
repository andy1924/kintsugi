# Kintsugi

A React visible-mending studio with a FastAPI API, private photo storage, asynchronous segmentation, physical-scale PDF/SVG repair plans, and a paid maker network with quote, collection, repair, return-shipping and payout reconciliation workflows.

## Run locally

Python 3.12 is recommended. Node 22+ is required.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
npm ci
.venv/bin/python scripts/dev.py
```

Open **http://127.0.0.1:5173/**. API documentation: **http://127.0.0.1:8000/docs**. The launcher creates random local secrets, runs migrations, and starts the API, CPU processing worker, and React app. Ctrl-C stops all three. Add `--preview` to the launcher to build and serve a stable local preview without hot reload. It preserves existing accounts and repairs in `.data/` between runs. `.env`, uploads, model weights, and the virtual environment are ignored by Git.

Create an account in **My studio** and upload a photo. Textile uploads start damage analysis automatically, without requesting a width or manual marking. When an OpenAI key is configured, OpenAI vision identifies the likely damage, proposes a boundary, describes severity and fabric, and recommends a repair approach and stitch style. Otherwise a local contrast heuristic proposes the area. The configured segmentation model then traces that area. Review the boundary and choose a design; **Adjust damage or size** lets you change the rectangle with two corner clicks or keyboard-editable coordinates and optionally enter its width in millimetres. Without a physical reference, the app uses a clearly labelled 35 mm suggested template width (reduced for unusually tall regions), not a measured physical width. Check template coverage on the garment before cutting. The worker then compiles a printable guide and SVG. Finish the physical repair and submit an after-photo to record it. Or request a paid specialist repair for textiles or decorative ceramics.

## OpenAI damage assessment

Add the following entries to the existing private `.env` file, preserving the local secrets already there. See `.env.example` for these settings. Never put an API key in a `VITE_` variable or frontend code.

```dotenv
OPENAI_API_KEY=your-api-key
OPENAI_VISION_MODEL=gpt-5.6-terra
DAMAGE_ANALYSIS_PROVIDER=auto
```

Restart the local launcher (or recreate the API and worker containers). `auto` selects OpenAI when a key exists and local detection otherwise. `openai` explicitly requires the key; `local` disables external analysis. The health route reports the selected provider and whether a key is configured, without exposing credentials. No OpenAI key is committed or provided by this repository.

The worker calls the [OpenAI Responses API with image input](https://developers.openai.com/api/docs/guides/images-vision) using [strict structured output](https://developers.openai.com/api/docs/guides/structured-outputs). The default [GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra) model is configurable; the default uses `reasoning.effort=none` for a bounded, low-latency assessment. It receives only the normalized photo and optional boundary/fabric adjustments, not account details or the user's personal memory text. EXIF has already been removed. The upload screen explains that enabled AI analysis sends the textile photo to OpenAI. Requests set `store=false`; this does not imply zero provider retention. Private object storage and access controls still apply to the application's saved photos.

The assessment includes damage type, severity, likely fabric, a qualitative confidence level (not a calibrated probability), repair advice and a suggested stitch style. User boundary, size and fabric corrections take precedence. An inconclusive AI assessment requires a user-adjusted area or clearer upload before compilation. Physical millimetres are never invented by the model; uncalibrated plans retain the suggested-size label. Model localisation can be inaccurate, so boundary review remains part of the flow.

Each assessment has a 60-second HTTP timeout, bounded output and at most three queue attempts for connection failures, rate limits or provider server errors. Key/access errors, invalid structured results and refusals fail with safe, actionable messages. OpenAI failures never silently claim a successful AI analysis or switch to the contrast heuristic. Pattern compilation reuses the saved assessment without another API call. Retries after interrupted requests may incur additional API usage; existing per-user analysis limits still apply. Tests use an in-memory HTTP transport and never call the paid API. A real API request must be checked after configuring a valid key.

## Models

The default, **OpenCV GrabCut**, fits foreground/background Gaussian mixture models to each image. It needs no checkpoint or GPU. It is not labelled as a deep learning model. If segmentation is inconclusive, the full user-marked area is retained with a warning. Every repair backing covers that full area plus a 10 mm anchoring margin (12 mm for knit/unknown fabric), regardless of a model proposing a smaller defect.

The **SAM 2.1 tiny** backend is implemented and can run on CPU. Install it separately:

```sh
.venv/bin/python -m pip install torch torchvision setuptools wheel
SAM2_BUILD_CUDA=0 .venv/bin/python -m pip install --no-build-isolation -r backend/requirements-ml.txt
.venv/bin/python scripts/download_model.py
.venv/bin/python scripts/dev.py --sam2
```

The official Meta repository is pinned to commit `2b90b9f5ceec907a1c18123530e92e794ad901a4`. The downloader pins the checkpoint SHA-256. Model loading happens once in each worker, not in HTTP requests. A missing package/checkpoint fails worker startup explicitly; it never silently claims to run SAM. `MODEL_DEVICE=cpu` is the default; a separately provisioned PyTorch/CUDA runtime can use `MODEL_DEVICE=cuda`.

The branch motif traces a simplified medial-axis graph from the segmentation contours. Other patterns are deterministic vector patterns fitted to the repair dimensions. When creative previews are enabled, the AI designs unique stitch paths which replace these defaults, and an image-editing model generates a realistic concept photograph. The downloadable guide uses the same saved paths and instructions as that concept. Physical scale comes only from an optional user measurement of a flat photo; otherwise exports remain labelled as suggested template sizes. Local damage localisation uses a contrast heuristic; OpenAI mode uses a general vision model rather than a validated textile-damage classifier. Both can confuse seams, prints and shadows with damage. A photo with no distinct candidate receives a broad review area and an uncertainty message. Automatic ruler recognition, homography calibration and structural textile testing are not implemented. Print at 100% and measure the included 20 mm calibration bar.

SAM integration follows [Meta's official implementation](https://github.com/facebookresearch/sam2). Background inference is isolated from HTTP serving, consistent with [FastAPI's guidance on heavy work](https://fastapi.tiangolo.com/tutorial/background-tasks/).

## Guided DIY or a skilled hand

Every saved piece offers two explicit choices: **Guide me through it** and **Find a maker**. Textile DIY begins with measurement and segmentation, then a scaled pattern and six illustrated steps: prepare, back the tear, baste, practise the running stitch, follow the design, and finish. The stitch diagram advances one stitch at a time. A practice guide is available before compiling a pattern.

The guide saves checked steps to the owner's project, so users can leave and return. At every step, **Let a maker help** carries the design and completed-step context into a paid service request. This records self-reported progress; it does not certify work quality. An after-photo records the finished repair.

Decorative ceramics get a separate visual guide covering suitability, preparation, dry fitting, manufacturer-directed adhesive use, cure time and inspection. It links to [the adhesive manufacturer's ceramic guidance](https://www.loctiteproducts.com/ideas/fix-stuff/how-to-fix-broken-ceramic-tips-for-breaks-cracks-and-chinks.html); application ratios, compatibility and cure times are not invented. Users can switch to a ceramic specialist at any step. No textile stitch pattern is generated for ceramics.

## Independent maker network

There are no points, credits, rewards or gated pattern packs. All DIY patterns are available. The alternative is paid craft work: customers keep a valued item; independent makers can earn from a skill the customer does not have.

- **Customer:** save a textile or decorative ceramic piece; share its photo and brief with consent; choose an available maker or request matching; review a full INR quote; accept it and provide a private collection/return address; track both shipment legs and repair events.
- **Maker:** apply with a workroom profile, skills and private collection address; opt into public listing; wait for operator approval; set labour/materials prices and craft time; decline jobs or pause new work; report repair progress; view reserved, payable and reconciled earnings.
- **Operator:** review applications, match requests, add both carrier estimates, publish the itemised quote, record externally received payments, coordinate both shipping legs, and reconcile maker payouts after delivery.

Makers receive their entire labour + materials quote. A separate customer-facing service fee funds coordination (default **5%**, configurable with `SERVICE_FEE_BPS` from 0 to 2500). Shipping is shown separately for each leg. Quotes are versioned, expire after seven days, and cannot be changed after acceptance. Stale acceptance is rejected. Request locks, unique quote/earning/shipment constraints and idempotent acceptance prevent duplicate bookings or obligations on retries.

A customer can optionally enter a replacement-price estimate. The app compares it with the complete repair quote, including shipping and fee. It does not guarantee that every repair costs less. Sentimental value remains the customer's decision. Maker pay is not discounted to manufacture savings.

The `women_led` and `community_enterprise` descriptions are optional, self-declared workroom descriptions, not demographic inference or independently verified claims. Only approved, consenting, currently available makers appear in the directory. No fake businesses are seeded. If no maker is available, a request stays **awaiting match**. Photos are visible only to the customer, their assigned maker and operators. Street addresses and phone numbers are excluded from public listings and the maker's customer-request view; operations uses them for logistics.

**Carrier, payments and payouts are manual orchestration in this build.** The operator records actual external payment references, carrier booking/tracking references and payout references. No payment is collected, courier label purchased or money transferred by these endpoints. Real payment/carrier integrations and commercial partnerships must be configured before offering automatic fulfilment. Accepted quotes create two pending shipment records, not fictitious carrier bookings. Pickup cannot be scheduled until an operator records received payment; a return cannot be scheduled until the maker marks the repair finished. A maker earning becomes payable only after recorded return delivery.

Operator access is never selectable during registration. After an operator registers, a server administrator grants access explicitly:

```sh
.venv/bin/python scripts/manage.py grant-operator operator@example.com
# Revoke when needed:
.venv/bin/python scripts/manage.py revoke-operator operator@example.com
```

Domestic India logistics and INR pricing are supported initially. Decorative ceramics go to specialist assessment, not the textile stitch compiler. The ceramic tutorial does not claim that restored ceramics are food-safe, heat-safe or structurally certified. Fragile-item packing guidance and carrier acceptance must be confirmed before shipment. Cancellations before quote acceptance are self-service; accepted-order cancellations/refunds require an operator and are not automatic.

## Deployment

Docker Compose provides PostgreSQL 17, a migration job, FastAPI, independently scalable workers, and Nginx serving the built React app with a same-origin API proxy.

```sh
.venv/bin/python scripts/init_dev.py
docker compose --env-file .env up --build
```

Open **http://localhost:8080/**. For the SAM worker, download the checkpoint first, then:

```sh
docker compose --env-file .env -f compose.yaml -f compose.sam2.yaml up --build
```

The CPU-only SAM image installs the official CPU PyTorch wheels. Model weights are mounted read-only. For the base CPU stack, scale workers with `docker compose up --scale worker=3`. Each worker loads one model; size replicas to available memory.

**Production configuration:** terminate HTTPS at the edge; set `SECURE_COOKIE=true`, a strong shared `KINTSUGI_SECRET`, the exact first-party `WEB_ORIGINS`, and a PostgreSQL `DATABASE_URL`. Never expose the internal API port directly if enabling trusted proxy headers. Use a stable same-origin `/api` reverse proxy. Configure backups, object retention, monitoring and password recovery before a public launch. The current account flow has no email verification or password recovery.

For multiple hosts, configure **all API and worker replicas** with `S3_BUCKET` and AWS credentials/region (or `S3_ENDPOINT_URL` for an S3-compatible service). The storage adapter keeps objects private and serves them only through owner-authorized API routes. The default shared Docker volume is for a single host. Back up PostgreSQL and the upload/object store together.

The prior hosted landing page is a static Sites deployment. It **cannot host this Python API or worker**. This repo includes the functioning local stack and deployment configuration; a cloud Python host, database and storage must be provisioned before switching that hosted frontend to the full application. No cloud backend has been claimed as deployed.

## Architecture and job guarantees

- `src/Studio.jsx`: account flow, saved projects, marking/review, job polling, plan downloads, completion and repair-service handoff.
- `backend/kintsugi/main.py`: versioned API and authorization.
- `backend/kintsugi/imaging.py`: upload normalization, pixel/size limits, EXIF removal, GrabCut and SAM adapters.
- `backend/kintsugi/compiler.py`: mask-derived geometry, materials/instructions, vector SVG and tiled A4 PDF export.
- `backend/kintsugi/worker.py`: durable leased job processing, retries and crash recovery.
- `backend/kintsugi/network.py`: maker approvals, consent-based matching, versioned quotes, shipping state machine and earnings reconciliation.
- `backend/migrations/`: versioned Alembic schema migrations.

API state and job creation commit in the same database transaction, eliminating a database-to-broker dispatch gap. Workers claim jobs with PostgreSQL `FOR UPDATE SKIP LOCKED`, plus a conditional claim update. Jobs use 15-minute leases and up to three attempts with backoff. Expired exhausted jobs are marked failed. Each result commit checks its lease token and project revision, so a stale worker cannot overwrite newer work. Delivery is at least once; result application and service acceptance are idempotent. SQLite is a local-development option, not the multi-host database.

Model inference is serial within a worker process, avoiding concurrent mutation of a shared SAM predictor. Increase worker processes rather than threads. Inputs are capped at 12 MB / 24 megapixels and resized to 1600 px. Upload routes have per-user limits and a 200-project account quota. Jobs have bounded attempts, not a GPU execution timeout; provision process supervision for hung inference. `/api/v1/health` reports database connectivity, configured model, and recent worker availability. A separate heartbeat thread continues updating liveness during inference.

Security includes Argon2 password hashes, hashed opaque sessions, HTTP-only cookies, CSRF tokens for mutations, origin checks, database-backed login/upload limits, no-store private asset responses, no EXIF/location metadata, and ownership checks on every project/asset endpoint. Run `.venv/bin/python scripts/maintenance.py` daily to expire session, rate-limit and worker-heartbeat rows. The Compose API is internal-only and trusts the Nginx-overwritten `X-Real-IP` header for per-IP limits. `TRUST_PROXY_HEADERS` defaults to false outside Compose. Enable it only behind a trusted proxy that overwrites this header; do not expose that API directly.

## Verify

```sh
.venv/bin/python -m pytest backend/tests -q
npm run build
docker compose --env-file .env config --quiet
```

The integration tests exercise real image processing and PDF generation, authentication, CSRF, upload validation, cross-account isolation, review gates, queue contention and lease recovery, duplicate completions, geometry-driven paths, quote acceptance, maker authorization, price breakdowns, address privacy and shipment progression. The Docker daemon is not required for these checks. PostgreSQL/Compose integration should also be run on the deployment host; local tests use SQLite.

`backend/requirements.lock` is the tested base environment. `backend/requirements-ml.lock` records the tested optional ML environment. The repository does not contain model weights, real user photos, credentials or the local database.


### Nearby makers on OpenStreetMap

“Find a maker” and the repair request screen have an OpenStreetMap view. **Use my location** requests browser permission on click (HTTPS in production, localhost in development). It rounds the coordinates to two decimal places before searching, never adds them to the account, and lists approved, available, consenting makers within 25–200 km, ordered by straight-line distance. A denied or unavailable location has a map/coordinate fallback. Existing workrooms without pins remain in the all-makers list; there are no fabricated map listings.

Makers optionally choose a public neighbourhood pin during application or under **Maker workroom → Manage my public map location**. This is separate from their private collection address; the server enforces rounding and pins can be removed. Run the migrations before starting the updated API (`alembic upgrade head` through the normal development launcher).

Map tiles load directly from OpenStreetMap with visible attribution, normal browser caching, and an origin referrer. No offline download or prefetch is implemented. The public tile service is best-effort and has usage limits: follow the [OSM tile usage policy](https://operations.osmfoundation.org/policies/tiles/). Configure `OSM_TILE_URL` on the API to switch to a compatible OSM tile provider or self-hosted tiles for higher traffic (and retain/add any provider-required attribution). No geocoder is used, and private street addresses are never sent to a geocoding service.


### Creative repair photographs and fresh ideas

With `OPENAI_API_KEY` configured, uploading a textile first queues damage assessment, then a separate creative-preview job. A vision model designs a hand-sewable motif from the garment and its actual damage (including peacock-inspired feathers, botanical branches and other visible-mending ideas). The image-editing model receives the original photo, a raster stitch guide and a transparent repair-area mask. The result is composited back over the original: **pixels outside the detected repair rectangle plus the necessary anchoring margin remain unchanged**. It is labelled as an AI concept, not proof of a finished or structurally safe repair.

The same saved design supplies six practical steps, materials and normalized stitch paths for the measured PDF/SVG and illustrated tutorial. Users still review the damage and physical size before cutting. **Another idea** generates a fresh concept; changing stitch direction can also create a matching preview. A new concept gets its own version, invalidates the old guide selection, and requires **Make this design** to prepare matching exports. Maker requests snapshot the shared preview and guide so later refreshes cannot silently change the agreed concept.

Set `OPENAI_IMAGE_MODEL` (default `gpt-image-2.5-sunburst`) and `REPAIR_PREVIEW_PROVIDER=auto|openai|off` on both API and worker. `auto` enables image edits when a server key is present; `off` keeps the geometry-only workflow. No key is sent to the browser. This uses the [OpenAI image edits API](https://developers.openai.com/api/reference/resources/images/methods/edit). Text design calls have a 120-second timeout and image edits 300 seconds. Preview jobs do not automatically retry paid image calls, including expired leases: errors leave the damage assessment and any existing plan intact and offer a manual refresh. Refreshes are limited to six per user per hour; existing upload/assessment limits bound initial generations. Tests mock provider requests and never use the paid API.


### Generation backend operations

- Preview submissions accept an optional UUID `request_id`. Retrying the same request returns its current generation without spending another attempt; reusing it for different input is rejected. Older requests are retrievable through generation history.
- `GET /api/v1/projects/{id}/generations` returns versioned states and stages; `/generations/{version}/image` serves an owner-only historical image. `POST /generations/{version}/cancel` cancels pending work and suppresses stale results. It cannot undo an already-started external request.
- `GET /api/v1/projects/{id}/jobs` exposes sanitized job progress. `GET /api/v1/generation-usage` gives the signed-in user’s allowance. Operators can inspect worker pools and queue failures at `GET /api/v1/ops/queue`.
- Atomic database admission counters apply to automatic and manually refreshed concepts, with configurable `GENERATION_USER_DAILY_LIMIT=12` and `GENERATION_GLOBAL_DAILY_LIMIT=300`, resetting at midnight UTC. These count reserved attempts, not currency. Rejected global reservations roll back the associated user reservation. Assessments remain usable when capacity is exhausted.
- Set `WORKER_JOB_KINDS=analyze`, `compile`, or `preview` on separate worker deployments to scale CPU inference separately from remote image calls; the local default handles all queues. Preview-only workers do not load SAM/Torch. Inference and remote requests run after releasing database connections. The validated design is checkpointed before the paid image request. Paid image jobs never automatically replay on timeout or lease expiry.
