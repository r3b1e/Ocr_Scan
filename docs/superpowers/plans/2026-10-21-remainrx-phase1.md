# remainRX Extraction - Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a prescription image into validated `PrescriptionExtraction` JSON through a FastAPI service, with Claude and Ollama vision backends switchable in `.env`, an Indian drug lexicon and a sig grammar validating the result, and persistence for documents, extractions and corrections.

**Architecture:** New `core/` modules compose a pure pipeline (`prescription_pipeline.run_extraction`) that takes bytes and injected collaborators (OCR engine, extractor, lexicon, repository). Backends implement one `PrescriptionExtractor` protocol. The service layer is thin: FastAPI endpoints call the pipeline and the repository. Tests never touch the network: backends are exercised with fake clients and recorded fixtures.

**Tech Stack:** Python 3.12, pydantic v2, anthropic SDK, ollama SDK, rapidfuzz, fastapi + uvicorn + python-multipart, httpx (tests), existing EasyOCR/OpenCV/MySQL/SQLite layers.

**Spec:** `docs/superpowers/specs/2026-10-21-remainrx-extraction-design.md`

## Global Constraints

- Schema field names, status values and endpoint shapes exactly as in spec §2.
- No network in `pytest` by default; live calls only under `-m live`.
- No silent fallback between backends; configured backend failure -> plain error.
- Every exception logged with traceback; responses carry plain messages only.
- ruff + compileall clean; typed, docstring'd code; TDD per task.
- Phase 1 includes the documents/extractions/corrections tables and `/feedback` because `/extract` must return a `document_id`.

---

## Shared interfaces (exact)

```python
# core/prescription.py  (pydantic v2)
Form, Timing, Slot, Status = Literal[...] as spec §2.2
class RawMedication(BaseModel): name, strength, form, dose, frequency_text, timing_text, duration_text, instructions, confidence
class RawPrescription(BaseModel): patient_name, patient_age, doctor_name, prescribed_on, medications: list[RawMedication], notes
class Frequency(BaseModel): pattern, times_per_day, slots, interval_hours, as_needed
class Medication(RawMedication): brand_matched, composition, frequency, timing, duration_days, status, bbox, field_status
class PrescriptionExtraction(BaseModel): document_id, patient_name, patient_age, doctor_name, prescribed_on, medications: list[Medication], notes, warnings, backend, model, handwritten, processing_ms

# core/imaging.py
class ImageError(ValueError)
def load_image(data: bytes, max_side: int = 1600) -> np.ndarray          # BGR, EXIF-rotated, downscaled; raises ImageError
def encode_jpeg(frame: np.ndarray, quality: int = 85) -> bytes
def prepare_for_ocr(frame: np.ndarray) -> np.ndarray                     # deskew + denoise (reuses core.detector)

# core/sig_grammar.py
@dataclass(frozen=True) class SigParse: frequency: Frequency; timing: Timing | None; dose_fraction: str | None; parsed: bool
def parse_frequency(text: str | None) -> SigParse
def parse_timing(text: str | None) -> Timing | None
def parse_duration(text: str | None) -> int | None
def parse_form(text: str | None) -> Form | None
def normalise_strength(text: str | None) -> str | None      # "500MG" -> "500 mg"; None if invalid
def validate_dose(text: str | None) -> bool

# core/drug_lexicon.py
@dataclass(frozen=True) class DrugEntry: brand: str; composition: str; strengths: tuple[str, ...]; form: str; source: str
@dataclass(frozen=True) class LexiconMatch: entry: DrugEntry | None; score: float; status: Status; matched_on: Literal["brand","composition","none"]
class DrugLexicon:
    def __init__(self, entries: Iterable[DrugEntry])
    @classmethod def load(cls, path: Path) -> "DrugLexicon"           # missing file -> empty lexicon + warning
    def match(self, name: str | None) -> LexiconMatch
    def __len__(self) -> int

# core/locate.py
@dataclass(frozen=True) class Fragment: text: str; bbox: list[list[int]]
def locate(value: str | None, fragments: Sequence[Fragment], min_score: int = 80) -> tuple[list[list[int]] | None, float]
def line_union(anchor: Fragment, fragments: Sequence[Fragment]) -> list[list[int]]

# core/extractors/base.py
class ExtractorError(RuntimeError)
class PrescriptionExtractor(Protocol): name: str; model: str; def extract(self, image_jpeg: bytes, ocr_hint: str | None) -> RawPrescription; def health(self) -> tuple[bool, str]
# core/extractors/prompt.py
SYSTEM_PROMPT: str; def build_instruction(ocr_hint: str | None, include_schema: bool) -> str
# core/extractors/claude.py
class ClaudeExtractor: def __init__(self, model: str, client: Any | None = None)   # client injectable
# core/extractors/ollama.py
class OllamaExtractor: def __init__(self, model: str, host: str, client: Any | None = None)
# core/extractors/__init__.py
def build_extractor(settings: Settings) -> PrescriptionExtractor      # raises ExtractorError when misconfigured

# core/prescription_pipeline.py
@dataclass class OCRPass: fragments: list[Fragment]; mean_confidence: float; handwritten: bool; hint: str | None
def run_ocr_pass(frame, engine, *, min_conf=0.45, min_fragments=4, hint_for_printed=True) -> OCRPass
def validate_medication(raw: RawMedication, lexicon: DrugLexicon, fragments: Sequence[Fragment]) -> tuple[Medication, list[str]]
def run_extraction(image_bytes: bytes, *, engine, extractor, lexicon, settings, repo=None, source="api") -> PrescriptionExtraction

# database/prescription_repository.py
@dataclass class DocumentRecord: id, created_at, source, image_path, backend, model, handwritten, processing_ms, usage_json
class PrescriptionRepository(Protocol):
    def create_document(self, record: DocumentRecord) -> int
    def save_extraction(self, document_id: int, raw_json: str, result_json: str) -> int
    def save_correction(self, document_id: int, corrected_json: str) -> int
    def get_document(self, document_id: int) -> tuple[DocumentRecord, str | None, str | None] | None   # (doc, result_json, latest correction_json)
    def delete_document(self, document_id: int) -> bool
    def count_documents(self) -> int
class SQLitePrescriptionRepository / MySQLPrescriptionRepository  (same bootstrap style as scans)
DatabaseManager gains .prescriptions (built alongside .repo)

# service/api.py
def create_app(settings: Settings, *, extractor=None, engine=None, lexicon=None, db=None) -> FastAPI
# python -m service  -> uvicorn on API_HOST:API_PORT

# config/settings.py additions
extractor_backend, claude_model, ollama_host, ollama_model, extract_max_image_side, ocr_hint_for_printed, confidence_flag_threshold, lexicon_path, api_host, api_port
```

## Tasks

### Task 1: Settings + schema + imaging
- [x] tests: settings defaults/overrides for the new keys; schema round-trip + validation (status literal, confidence 0-1 clamp, JSON schema generation works); imaging: EXIF rotation, downscale to max side, invalid bytes -> ImageError, encode_jpeg size > 0, prepare_for_ocr returns BGR same shape
- [x] implement `config/settings.py` additions, `core/prescription.py`, `core/imaging.py`

### Task 2: Sig grammar
- [x] tests: table-driven cases from spec §3.4 (60+), unparseable -> parsed False, None handling, strength normalisation, dose validation
- [x] implement `core/sig_grammar.py`

### Task 3: Drug lexicon
- [x] write `data/drug_lexicon_in.csv` (~150 common Indian brands; `source=seed-verify`)
- [x] tests: exact brand -> ok/score 100; misspelling "Dolo 650" vs "Dolo" strength stripped; "Amoxicilin" -> corrected to Amoxicillin-containing brand/composition; nonsense -> unverified; composition name matches; missing file -> empty lexicon; CSV parse of strengths
- [x] implement `core/drug_lexicon.py`

### Task 4: Locate
- [x] tests: exact, fuzzy >= 80, no match -> None; line union of same-line fragments; empty fragments
- [x] implement `core/locate.py`

### Task 5: Extractors
- [x] fixtures: `tests/fixtures/claude_response.json`, `tests/fixtures/ollama_response.json`, `tests/fixtures/sample_rx.jpg` (rendered printed prescription)
- [x] tests: prompt builder includes hint and schema when asked; Claude extractor with fake client (parse -> parsed_output; refusal -> ExtractorError; each SDK exception -> plain message; usage captured); Ollama extractor with fake client (valid JSON; invalid JSON retried once then error; connection error message mentions `ollama serve`; missing model mentions `ollama pull`); `build_extractor` picks backend / errors when misconfigured
- [x] implement `core/extractors/{base,prompt,claude,ollama,__init__}.py`

### Task 6: Pipeline
- [x] tests: run_ocr_pass printed vs handwritten decision; validate_medication statuses + warnings + confidence formula; run_extraction end-to-end with fake extractor and real EasyOCR on the rendered image -> boxes located, processing_ms set, document persisted when repo given; zero medications -> warning; ExtractorError propagates
- [x] implement `core/prescription_pipeline.py`

### Task 7: Repository
- [x] tests: SQLite + MySQL (skip when unreachable): create/save/get/delete/count; delete cascades; DatabaseManager exposes `.prescriptions`
- [x] implement `database/prescription_repository.py`, schema additions in `database/schema.sql`, `DatabaseManager` wiring

### Task 8: Service
- [x] tests (TestClient, fake extractor): /health; /extract happy path + backend override + 422 bad image + 502 extractor error + 503 misconfigured; /feedback; GET/DELETE documents
- [x] implement `service/api.py`, `service/__main__.py`, `service/__init__.py`

### Task 9: Live verification + docs
- [ ] `pytest -m live` against whichever backends are available on this machine (Ollama pulled model / Claude credentials); record results honestly
- [x] README section "remainRX extraction service", `.env.example` keys, `requirements.txt` pins, CHANGELOG 1.1.0
- [x] ruff, compileall, full pytest; commit
