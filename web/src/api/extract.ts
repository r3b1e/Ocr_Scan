/**
 * Client for the remainRX prescription-extraction service (Python, FastAPI).
 * The base URL comes from VITE_EXTRACT_API (default http://127.0.0.1:8765).
 * Types mirror core/prescription.py in the service repository.
 */

export type FieldStatus = 'ok' | 'corrected' | 'unverified';
export type Form = 'tablet' | 'capsule' | 'syrup' | 'injection' | 'drops' | 'cream' | 'inhaler' | 'powder' | 'other';
export type Timing = 'before_food' | 'after_food' | 'with_food' | 'bedtime' | 'empty_stomach' | 'any';
export type Slot = 'morning' | 'afternoon' | 'evening' | 'night';

export interface Frequency {
    pattern: string | null;
    times_per_day: number | null;
    slots: Slot[];
    interval_hours: number | null;
    as_needed: boolean;
}

export interface ExtractedMedication {
    name: string;
    strength: string | null;
    form: Form | null;
    dose: string | null;
    frequency_text: string | null;
    timing_text: string | null;
    duration_text: string | null;
    instructions: string | null;
    confidence: number;
    brand_matched: string | null;
    composition: string | null;
    frequency: Frequency;
    timing: Timing | null;
    duration_days: number | null;
    status: FieldStatus;
    bbox: number[][] | null;
    field_status: Record<string, FieldStatus>;
}

export interface PrescriptionExtraction {
    document_id: number | null;
    patient_name: string | null;
    patient_age: string | null;
    doctor_name: string | null;
    prescribed_on: string | null;
    medications: ExtractedMedication[];
    notes: string | null;
    warnings: string[];
    backend: string;
    model: string;
    handwritten: boolean;
    processing_ms: number;
}

export interface ServiceHealth {
    status: 'ok' | 'degraded';
    backend: string;
    model: string;
    backend_ready: boolean;
    backend_message: string;
    backends: string[];
    lexicon_size: number;
    database: string;
    database_offline: boolean;
    ocr_ready: boolean;
    ocr_error: string | null;
}

export const API_BASE = (import.meta.env.VITE_EXTRACT_API || 'http://127.0.0.1:8765').replace(/\/$/, '');

export class ExtractApiError extends Error {
    constructor(message: string, public readonly status: number) {
        super(message);
        this.name = 'ExtractApiError';
    }
}

async function detail(res: Response): Promise<string> {
    try {
        const body = await res.json();
        if (typeof body?.detail === 'string') return body.detail;
        if (Array.isArray(body?.detail)) return body.detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join('; ');
    } catch {
        /* not JSON */
    }
    return `${res.status} ${res.statusText}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    let res: Response;
    try {
        res = await fetch(`${API_BASE}${path}`, init);
    } catch {
        throw new ExtractApiError(`Cannot reach the extraction service at ${API_BASE}. Start it with "python -m service".`, 0);
    }
    if (!res.ok) throw new ExtractApiError(await detail(res), res.status);
    return (await res.json()) as T;
}

export const getHealth = () => request<ServiceHealth>('/health');

export function extractPrescription(file: File | Blob, backend?: string): Promise<PrescriptionExtraction> {
    const body = new FormData();
    body.append('image', file, file instanceof File ? file.name : 'capture.jpg');
    if (backend) body.append('backend', backend);
    return request<PrescriptionExtraction>('/extract', { method: 'POST', body });
}

export function sendFeedback(documentId: number, corrected: PrescriptionExtraction): Promise<{ correction_id: number }> {
    return request('/feedback', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ document_id: documentId, corrected }),
    });
}

/** URL of the processed image the `bbox` coordinates refer to. */
export const documentImageUrl = (documentId: number) => `${API_BASE}/documents/${documentId}/image`;
