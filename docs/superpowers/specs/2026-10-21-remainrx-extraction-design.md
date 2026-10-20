# remainRX Prescription Extraction - Design Spec

**Date:** 2026-10-21 · **Status:** approved in discussion, awaiting written review
**Builds on:** the OCR Data Scanning Tool in this repository (EasyOCR, MySQL/SQLite, Tk desktop app)

## 1. Purpose

remainRX is a website where a user uploads or scans a prescription and gets medicine reminders
pre-filled. This spec defines the **extraction service** that turns a prescription image into a
validated, structured list of medications, and the supporting desktop tooling and data loop.

Inputs are Indian prescriptions, a mix of printed and handwritten, in English with Indian brand
names. The user is a solo student developer: the design needs **no human labelling campaign**,
keeps cloud cost tiny and visible, and offers a free offline mode.

### Goals

1. One API call turns an image into `PrescriptionExtraction` JSON with per-field confidence and
   status, good enough to pre-fill a reminder form.
2. Two interchangeable vision backends selected in `.env`: Claude API (default) and a local
   open model via Ollama.
3. A validation layer (Indian drug lexicon + sig grammar) that repairs or flags model output.
4. A correction loop: every user edit is stored and becomes evaluation and training data.
5. Option 4 (LiLT token tagging on printed prescriptions, trained on synthetic data) as a
   later, self-contained component compared against the vision backends.

### Non-goals

- Creating reminders automatically. The website creates them only after user confirmation.
- Medical advice, interaction checks, or dose recommendations.
- Handwriting recognition models trained on collected handwriting (rejected: needs a campaign).
- Multi-page prescriptions and non-English scripts (future work).

## 2. Contract with the website

### 2.1 Endpoints (FastAPI, `service/api.py`)

| Method & path | Request | Response |
|---|---|---|
| `POST /extract` | multipart `image` (JPEG/PNG/WebP, max 10 MB), optional form field `backend` (`claude` or `ollama`) to override `.env` for one call | `200` `PrescriptionExtraction`; `422` invalid image; `502` backend error with a plain message; `503` backend not configured |
| `POST /feedback` | JSON `{document_id, corrected: PrescriptionExtraction}` | `200` `{correction_id}` |
| `GET /documents/{id}` | - | stored extraction + correction, for the website's review page |
| `DELETE /documents/{id}` | - | removes image, extraction and corrections (user deletion right) |
| `GET /health` | - | `{status, backend, model, lexicon_size}` |

The website shows every field beside the highlighted image region (`bbox`), marks fields with
`status == "unverified"` or `confidence < CONFIDENCE_FLAG_THRESHOLD`, and sends the user-approved
JSON to `/feedback` before creating reminders.

### 2.2 Schema (`core/prescription.py`, Pydantic v2)

Two models. `RawPrescription` is what the vision model fills; `PrescriptionExtraction` is the
enriched API response.

```python
Form = Literal[
    "tablet", "capsule", "syrup", "injection", "drops", "cream", "inhaler", "powder", "other"
]
Timing = Literal["before_food", "after_food", "with_food", "bedtime", "empty_stomach", "any"]
Slot = Literal["morning", "afternoon", "evening", "night"]
Status = Literal["ok", "corrected", "unverified"]


class RawMedication(BaseModel):
    name: str  # brand or generic exactly as written
    strength: str | None  # "500 mg", "5 ml"
    form: Form | None
    dose: str | None  # "1", "1/2", "2 tsp", "5 ml"
    frequency_text: str | None  # exactly as written: "1-0-1", "BD", "twice daily"
    timing_text: str | None  # "after food", "A/F", "HS"
    duration_text: str | None  # "5 days", "x 1 week"
    instructions: str | None
    confidence: float  # model's own 0-1 estimate of legibility


class RawPrescription(BaseModel):
    patient_name: str | None
    patient_age: str | None
    doctor_name: str | None
    prescribed_on: str | None  # ISO date if readable, else null
    medications: list[RawMedication]
    notes: str | None  # diagnosis / advice lines, verbatim


class Frequency(BaseModel):
    pattern: str | None  # normalised "1-0-1" style when applicable
    times_per_day: int | None
    slots: list[Slot]
    interval_hours: int | None  # q8h -> 8
    as_needed: bool  # SOS


class Medication(RawMedication):
    brand_matched: str | None  # canonical lexicon brand
    composition: str | None  # from lexicon
    frequency: Frequency
    timing: Timing | None
    duration_days: int | None
    status: Status
    bbox: list[list[int]] | None  # 4 points in image pixels, when located
    field_status: dict[str, Status]  # per field: name, strength, frequency, timing, duration


class PrescriptionExtraction(BaseModel):
    document_id: int | None
    patient_name: str | None
    patient_age: str | None
    doctor_name: str | None
    prescribed_on: str | None
    medications: list[Medication]
    notes: str | None
    warnings: list[str]
    backend: str  # "claude" | "ollama"
    model: str
    handwritten: bool
    processing_ms: int
```

Status semantics: `ok` = validated (lexicon match >= 90 or parse succeeded); `corrected` = the
validation layer changed the value (e.g. brand spelling fixed) and the original is kept in
`warnings`; `unverified` = could not be validated, user must check.

## 3. Pipeline (`core/prescription_pipeline.py`)

```
image bytes
  -> load + EXIF rotate + downscale (longest side 1600 px)            core/imaging.py
  -> deskew + denoise (reuse core/detector.py helpers)
  -> EasyOCR pass: fragments with boxes + mean confidence             core/ocr_engine.py
       handwritten = mean_conf < 0.45 or fragments < 4
       ocr_hint   = fragments joined in reading order (printed only)
  -> PrescriptionExtractor.extract(image_jpeg, ocr_hint) -> RawPrescription   core/extractors/
  -> validate: lexicon + sig grammar + range checks -> Medication[]   core/drug_lexicon.py, core/sig_grammar.py
  -> locate: fuzzy-match each value to OCR fragments -> bbox          core/locate.py
  -> persist document + extraction (optional, service only)           database/
  -> PrescriptionExtraction
```

- The EasyOCR pass is skipped for the hint when `handwritten` is true (garbage text would
  mislead the model); boxes are still used for locating values.
- Processing budget: EasyOCR about 1 s, Claude 3-8 s, Ollama `qwen3-vl:4b` 10-60 s on a
  laptop CPU/Metal. `processing_ms` is reported.

### 3.1 Extractor interface (`core/extractors/base.py`)

```python
class ExtractorError(RuntimeError):
    """Plain-language failure (auth, network, refusal, bad JSON)."""


class PrescriptionExtractor(Protocol):
    name: str
    model: str

    def extract(self, image_jpeg: bytes, ocr_hint: str | None) -> RawPrescription: ...
    def health(self) -> tuple[bool, str]: ...
```

Both backends share `core/extractors/prompt.py`: one fixed **system prompt** (Indian
conventions: `1-0-1` = morning-afternoon-night counts, `OD/BD/TDS/QID/HS/SOS`, `A/F B/F AC PC`,
`Tab./Cap./Syp./Inj.`, brand names common in India; copy values verbatim; use null when not
present; never guess a dose) and one **user instruction** that includes the OCR hint when given.

### 3.2 Claude backend (`core/extractors/claude.py`)

- SDK: `anthropic` (official). Client from environment (`ANTHROPIC_API_KEY`).
- Call: `client.messages.parse(model=CLAUDE_MODEL, max_tokens=4096, system=[{"type": "text",
  "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}], messages=[{"role": "user",
  "content": [image block (base64 JPEG), text block]}], output_format=RawPrescription)`;
  result in `response.parsed_output`.
- `CLAUDE_MODEL` default `claude-opus-5-5`; `claude-sonnet-5-5` / `claude-haiku-5-5` are
  documented cheaper choices. `output_config.effort` left at the model default.
- `stop_reason == "refusal"` -> `ExtractorError("The model declined to read this image")`.
- Error chain -> `ExtractorError` messages: `AuthenticationError` (key missing/invalid),
  `RateLimitError` (retry later), `APIStatusError` 5xx (service problem), `APIConnectionError`
  (no internet). Request id logged.
- Cost logging: `usage.input_tokens / output_tokens / cache_read_input_tokens` written to the
  log and to `documents.usage_json`.

### 3.3 Ollama backend (`core/extractors/ollama.py`)

- Package `ollama`; `ollama.Client(host=OLLAMA_HOST)`.
- Call: `client.chat(model=OLLAMA_MODEL, messages=[{"role": "system", "content": SYSTEM_PROMPT},
  {"role": "user", "content": instruction, "images": [image_jpeg]}],
  format=RawPrescription.model_json_schema(), options={"temperature": 0})`;
  parse with `RawPrescription.model_validate_json(response.message.content)`.
- `OLLAMA_MODEL` default `qwen3-vl:4b` (3.3 GB; `qwen3-vl:2b` for weaker machines; requires
  Ollama >= 0.12.7). The schema is also included as text in the instruction, as Ollama's docs
  recommend.
- Errors: connection refused -> "Ollama is not running (start it with `ollama serve`)"; model
  missing -> "Run `ollama pull qwen3-vl:4b`"; invalid JSON -> one retry, then `ExtractorError`.

No automatic cross-backend fallback: the configured backend failing is reported, so cost and
privacy expectations never change silently.

### 3.4 Validation layer

**Drug lexicon** (`data/drug_lexicon_in.csv`, columns `brand, composition, strengths, form,
source`; `strengths` pipe-separated). Seeded from open Indian sources (NPPA ceiling-price
lists, CDSCO approved-drug lists, Jan Aushadhi generics list) plus common OTC brands; grown by
appending corrected brands. Matching (RapidFuzz `WRatio` on normalised names, strength tokens
stripped): >= 90 -> `ok`, `brand_matched` + `composition` filled; 75-89 -> `corrected`
(name replaced by lexicon brand, original kept in `warnings`); < 75 -> `unverified`. A
composition written instead of a brand matches the composition column the same way.

**Sig grammar** (`core/sig_grammar.py`, pure functions, table-driven tests):

| Input (case-insensitive) | Output |
|---|---|
| `1-0-1`, `1-1-1`, `0-0-1`, `1/2-0-1/2`, `1-0-0-1` (4 slots) | `pattern`, `times_per_day` = non-zero count, `slots` from positions; fractional entries copied into `dose` when dose is empty |
| `OD`, `once daily`, `daily` | 1/day, `morning` |
| `BD`, `BID`, `twice daily` | 2/day, `morning`, `night` |
| `TDS`, `TID`, `thrice daily`, `three times` | 3/day, `morning`, `afternoon`, `night` |
| `QID`, `four times` | 4/day, all four slots |
| `HS`, `at bedtime`, `nocte` | 1/day, `night`, timing `bedtime` |
| `SOS`, `PRN`, `when required`, `if needed` | `as_needed = true` |
| `q6h`, `q8h`, `every 8 hours`, `8 hourly` | `interval_hours`, `times_per_day = 24 // h` |
| `A/F`, `AF`, `after food`, `after meals`, `PC` | timing `after_food` |
| `B/F`, `BF`, `before food`, `AC`, `empty stomach` | `before_food` / `empty_stomach` |
| `x 5 days`, `5 days`, `for 1 week`, `1 month`, `5/7` | `duration_days` (week=7, month=30) |
| `Tab`, `Tab.`, `T.`, `Cap`, `Syp`, `Syr`, `Inj`, `Oint`, `Drops`, `gtt`, `Inh`, `Pwd` | `form` |

Unparseable text keeps the raw string and marks that field `unverified`.

**Range checks**: strength must be number + unit (`mg`, `mcg`, `g`, `ml`, `%`, `IU`); dose
numeric or fraction or volume; `duration_days` 1-365; `times_per_day` 1-6. Violations ->
`unverified` plus a warning.

**Overall confidence** per medication = weighted mean of model confidence (0.4), lexicon score
(0.3), sig parse success (0.2), locate score (0.1).

### 3.5 Locate (`core/locate.py`)

For each medication: fuzzy-match (`partial_ratio` >= 80) `name` against EasyOCR fragments;
the medication `bbox` is the union of that fragment and fragments on the same text line
(vertical overlap >= 50 %). Strength/frequency/duration are matched the same way for
`field_status` only. No match -> `bbox = None` (the website shows the field without highlight).

## 4. Data model

New tables in both MySQL and SQLite repositories (same `ScanRepository` style, new
`PrescriptionRepository`):

```sql
CREATE TABLE documents (
  id INT AUTO_INCREMENT PRIMARY KEY,
  created_at DATETIME NOT NULL,
  source VARCHAR(16) NOT NULL,          -- 'api' | 'desktop_upload' | 'desktop_camera'
  image_path VARCHAR(512) NOT NULL,
  backend VARCHAR(16) NOT NULL, model VARCHAR(64) NOT NULL,
  handwritten TINYINT(1) NOT NULL, processing_ms INT NOT NULL,
  usage_json JSON NULL
);
CREATE TABLE extractions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  document_id INT NOT NULL, created_at DATETIME NOT NULL,
  raw_json JSON NOT NULL,               -- RawPrescription
  result_json JSON NOT NULL,            -- PrescriptionExtraction
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);
CREATE TABLE corrections (
  id INT AUTO_INCREMENT PRIMARY KEY,
  document_id INT NOT NULL, created_at DATETIME NOT NULL,
  corrected_json JSON NOT NULL,         -- PrescriptionExtraction after user edits
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);
```

Images live under `data/documents/<id>.jpg`. `DELETE /documents/{id}` removes the file and rows.
Existing `scans` tables are untouched.

## 5. Desktop app: Prescription mode

- New menu/tab "Prescription": **Upload image** (file dialog) or **Use camera frame**, **Extract**
  (runs the pipeline on the worker thread, progress steps: Preparing image -> Reading text ->
  Asking <backend> -> Validating -> Done), results in an editable `ttk.Treeview` (one row per
  medication, columns name / strength / form / dose / frequency / timing / duration / status),
  double-click to edit a cell, **Save correction**, **Export JSON**.
- The image canvas shows the uploaded image with coloured boxes: green `ok`, amber
  `corrected`, red `unverified`.
- Backend and model are shown in the status line; a Settings entry switches backend at runtime.
- Console logs cost (tokens) for Claude calls.

## 6. Evaluation

- **Gold set** `data/gold/` : 30-50 prescription images gathered by the developer (own
  printouts, a few handwritten by self or friends) each with a hand-checked
  `PrescriptionExtraction` JSON. Corrections collected through `/feedback` extend it.
- `training/evaluate.py` runs any backend over the gold set and reports: per-field accuracy
  (name after lexicon, strength, times_per_day, slots, timing, duration_days), medication-row
  exact match, **whole-schedule-correct rate** (headline), mean processing time, and Claude cost.
  Output: Markdown table + JSON; the Stats window shows the latest run.

## 7. Phase 3: option 4 on printed prescriptions

- `training/synthetic/generate.py` renders Indian-style printed prescriptions (clinic header,
  Rx, list and table layouts, Tab./Cap./Syp., `1-0-1` columns, varied fonts, camera augmentation:
  blur, shadow, perspective, JPEG noise) with word boxes and BIO labels (MED_NAME, STRENGTH,
  FORM, DOSE, FREQUENCY, TIMING, DURATION, PATIENT_NAME, DOCTOR, DATE, O).
- `training/train_lilt.ipynb` fine-tunes `SCUT-DLVCLab/lilt-roberta-en-base` (MIT) on Colab;
  `core/extractors/lilt.py` is a third `PrescriptionExtractor` that builds `RawPrescription`
  from tagged EasyOCR tokens grouped by line.
- `training/compare.py` scores LiLT vs Claude vs Ollama on the printed part of the gold set.

## 8. Configuration (`.env` additions)

| Key | Default | Meaning |
|---|---|---|
| `EXTRACTOR_BACKEND` | `claude` | `claude` or `ollama` |
| `CLAUDE_MODEL` | `claude-opus-5-5` | any current Claude model id |
| `ANTHROPIC_API_KEY` | - | read by the SDK |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama server |
| `OLLAMA_MODEL` | `qwen3-vl:4b` | vision model tag |
| `EXTRACT_MAX_IMAGE_SIDE` | `1600` | downscale limit in pixels |
| `OCR_HINT_FOR_PRINTED` | `true` | send EasyOCR text to the model for printed images |
| `CONFIDENCE_FLAG_THRESHOLD` | `0.6` | below this the website highlights the field |
| `LEXICON_PATH` | `data/drug_lexicon_in.csv` | drug lexicon |
| `API_HOST` / `API_PORT` | `127.0.0.1` / `8000` | FastAPI bind |

## 9. Error handling

| Situation | Behaviour |
|---|---|
| Not an image / corrupt / too large | `422` with message; desktop console `[ERROR]` |
| Backend not configured (no key, Ollama down, model not pulled) | `503` with the exact fix (`ollama pull ...`, set `ANTHROPIC_API_KEY`) |
| Backend timeout / network / rate limit | `502`, message says retry; SDK retries first |
| Model returns invalid JSON (Ollama) | one retry, then `502` |
| Model refusal (Claude `stop_reason == "refusal"`) | `502` "The model declined to read this image" |
| Zero medications found | `200` with empty list and a warning "No medications found" |
| Lexicon file missing | service starts, every name `unverified`, warning in `/health` |
| EasyOCR unavailable | pipeline continues without hint/boxes, warning added |

All exceptions logged with traceback to `logs/app.log`; no tracebacks in responses or GUI.

## 10. Testing strategy

- Unit: schema validation, sig grammar (table-driven, 60+ cases), lexicon matching, range
  checks, locate, confidence formula, imaging (downscale/EXIF).
- Backends: tested with fake clients returning recorded responses stored under
  `tests/fixtures/` (no network, no key). Error mapping tested for each exception class.
- Pipeline: fake extractor + real EasyOCR on a rendered prescription image -> end-to-end
  `PrescriptionExtraction` with boxes.
- Service: FastAPI `TestClient` with the fake extractor, all endpoints and error codes.
- Repository: SQLite always, MySQL when reachable (existing pattern).
- `pytest -m live` (opt-in) calls the real backends on one fixture image.
- Static: ruff, compileall, as today.

## 11. Repository changes and dependencies

```
core/prescription.py  core/imaging.py  core/drug_lexicon.py  core/sig_grammar.py  core/locate.py
core/prescription_pipeline.py  core/extractors/{__init__,base,prompt,claude,ollama}.py
service/{__init__,api,deps}.py          # FastAPI app, uvicorn entry: python -m service
database/prescription_repository.py     # MySQL + SQLite implementations, schema additions
gui/prescription_view.py                # Prescription mode
data/drug_lexicon_in.csv  data/gold/    # lexicon + gold set
training/{evaluate.py, compare.py, synthetic/generate.py, train_lilt.ipynb}   # phase 3
tests/test_{prescription_schema,sig_grammar,drug_lexicon,locate,extractors,prescription_pipeline,service_api,prescription_repository}.py
```

New pinned dependencies: `anthropic`, `ollama`, `rapidfuzz`, `fastapi`, `uvicorn`,
`python-multipart`, `pydantic` (v2), `httpx` for tests. Phase 3 adds `transformers`,
`datasets`, `seqeval` in `requirements-train.txt`.

## 12. Phases and acceptance

| Phase | Deliverable | Done when |
|---|---|---|
| 1 | schema, both backends, lexicon, sig grammar, locate, pipeline, API, tests | `pytest` green without network; `POST /extract` on a printed and a handwritten sample returns validated JSON from both backends |
| 2 | Prescription mode in the desktop app, feedback endpoint, documents tables, gold set + `evaluate.py` | 30+ gold items scored; corrections saved and exported |
| 3 | synthetic generator, LiLT extractor, comparison report | LiLT scored against both backends on printed gold set |

## 13. Risks

- **Handwriting legibility**: some prescriptions stay unreadable for any model; the confirm
  screen and `unverified` status are the safety net. Measured, not assumed, via the gold set.
- **Lexicon coverage**: unknown brands become `unverified`; corrections grow the list.
- **Cost drift**: per-call token usage is logged; the model id is a config value.
- **Privacy**: health data; images stored locally only, deletable; consent text on the website;
  the Ollama mode keeps everything on the machine.

## 14. Decisions taken

1. Vision-model-first instead of OCR + layout tagging for handwriting (no labelling campaign).
2. Both backends behind one interface, no silent fallback between them.
3. Structured outputs on both backends with the same Pydantic schema; raw text fields
   (`frequency_text` etc.) are parsed by our grammar rather than trusting the model's structure.
4. Confidence is composed from validation signals, not taken from the model alone.
5. The dataset `paraloq/json_data_extraction` is used only as schema inspiration and a few
   text-to-JSON test cases (text-only, synthetic, research-only licence note).
6. LiLT (option 4) is deferred to phase 3 and trained on synthetic data only.
