# Real-Time OCR Data Scanning Tool — Specification

This is the brief the project was built from (verbatim from the requester, 2026-09-20). Decisions taken where the brief is silent are listed in `README.md` → "Design Decisions".

## 1. Project goal
A desktop GUI application that:
1. Opens a live webcam feed.
2. Detects and extracts text from the camera frame in real time using EasyOCR.
3. Draws bounding boxes + recognized text overlays on the live video.
4. Captures/scans text on demand, logs progress to an in-app console, shows a progress bar.
5. Persists every scan (text, confidence, timestamp, image path) to a MySQL database.
6. Lets the user browse, search, export (CSV/TXT/JSON) and delete past scans.

## 2. Tech stack (mandatory)
Python 3.10–3.12; easyocr (English default, configurable); opencv-python; tkinter + ttk (Canvas, Label, Text, Listbox, Scrollbar, Progressbar, Frames, padding); Pillow; matplotlib (scans per day, confidence distribution); pygame (beep, fail gracefully); MySQL via mysql-connector-python; python-dotenv + .env; pytest + pytest-mock; VS Code on Windows/Linux, also plain terminal.

## 3. Hardware assumptions
Any USB/built-in webcam (index 0 default, selectable). CPU-only must work: EasyOCR `gpu=False` default, auto-detect CUDA, config flag. Must not freeze UI on low-end machine.

## 4. Architecture
Package layout: `main.py`, `config/settings.py`, `core/{camera,ocr_engine,detector,audio}.py`, `database/{db_manager.py,schema.sql}`, `gui/{app,control_panel,console_panel,progress_panel,history_view,stats_view}.py`, `utils/{logger,helpers}.py`, `captures/`, `exports/`, `logs/`, `tests/{test_ocr_engine,test_db_manager,test_camera,test_helpers}.py`.

Threading: camera capture in background thread → queue; OCR in separate worker thread; GUI updates only from main thread via `root.after()` / thread-safe queue; clean shutdown (threads joined, camera released, `cv2.destroyAllWindows()`, DB closed, no zombies on Quit / `WM_DELETE_WINDOW`).

## 5. GUI
Resizable main window, min size, title "OCR Data Scanning Tool", app icon. Left/centre video canvas (aspect preserved, "Camera Off" placeholder). Right control panel: Launch Camera, Scan, Stop, Clear Screen, History, Stats, Export, Quit; enable/disable by state. Bottom console: Listbox + Scrollbar, timestamped, auto-scroll, colour/prefix by level `[INFO] [OK] [WARN] [ERROR]`. Above console: progress bar (determinate for scan steps, indeterminate while OCR runs) + status label (FPS, detected count, last confidence). Shortcuts: L launch, S scan, Q quit, Esc stop. Consistent ttk theme, readable fonts, no overlap on resize, grid/pack weights.

## 6. OCR / detection
Live preview: OCR every Nth frame (default 10), green rectangles, text + confidence above box. Scan: grab frame, full-accuracy OCR, save annotated image to `captures/`, insert MySQL rows, log each string, beep, progress steps "Capturing frame → Preprocessing → Running OCR → Writing to DB → Done". Preprocessing function (grayscale, optional resize, denoise, adaptive threshold / CLAHE) with UI toggle. Confidence threshold slider default 0.4. Zero detections handled gracefully.

## 7. Database
Auto-create DB and tables on first run; ship `schema.sql`:
```sql
CREATE DATABASE IF NOT EXISTS ocr_scanner;
CREATE TABLE IF NOT EXISTS scan_sessions (id INT AUTO_INCREMENT PRIMARY KEY, started_at DATETIME NOT NULL, ended_at DATETIME NULL, total_detections INT DEFAULT 0);
CREATE TABLE IF NOT EXISTS scans (id INT AUTO_INCREMENT PRIMARY KEY, session_id INT NULL, detected_text TEXT NOT NULL, confidence FLOAT NOT NULL, bbox JSON NULL, image_path VARCHAR(512) NULL, language VARCHAR(20) DEFAULT 'en', created_at DATETIME NOT NULL, INDEX idx_created (created_at), FULLTEXT KEY ft_text (detected_text), FOREIGN KEY (session_id) REFERENCES scan_sessions(id) ON DELETE SET NULL);
```
Parameterized queries only; credentials from `.env` only; `.env.example`. MySQL unreachable → offline mode (SQLite or JSONL), warning in console, never crash.

## 8. Error handling
Camera missing/in use/disconnected (reconnect then inform); EasyOCR model download failure; MySQL wrong credentials/server down/DB missing/table missing; missing dirs / permission errors; empty/black frames; pygame mixer failure; window closed while threads run. Every exception logged with traceback to `logs/app.log`; plain-language console line or messagebox; no silent failures; no raw tracebacks in GUI.

## 9. Testing & verification
Clean venv install; pytest unit tests (OCR on synthetic PIL image with known text; preprocessing shapes/dtypes; DB CRUD; camera with mocked `cv2.VideoCapture`; export validity); headless smoke test running a full scan cycle from a synthetic frame source asserting a DB row; `compileall` + `ruff`; manual GUI verification; iterate to green.

## 10. Deliverables
All source; pinned `requirements.txt`; `.env.example`; `schema.sql`; `README.md` (overview, requirements, setup incl. VS Code + MySQL Workbench, run, tests, config, troubleshooting table, screenshots section, Design Decisions); `notebooks/demo.ipynb`; `CHANGELOG.md`; final tree, test output, run commands, decision list.

## Definition of done
Clone → `pip install -r requirements.txt` → set MySQL credentials in `.env` → `python main.py` → point webcam at printed text → Scan → text detected on screen, logged in console, stored in MySQL, zero errors.
