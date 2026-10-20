/**
 * Scan a prescription: upload or photograph it, send it to the extraction
 * service, review every medicine against the highlighted image, correct the
 * structured values, then add each one through the normal MedForm (which the
 * user still confirms). Nothing is saved without that confirmation.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Camera, Check, CircleAlert, ImageUp, Loader2, Plus, RotateCcw, ScanLine, Sparkles } from 'lucide-react';
import type { MedicationDraft } from '@shared/index';
import {
    documentImageUrl, ExtractApiError, extractPrescription, getHealth, sendFeedback,
    type ExtractedMedication, type FieldStatus, type PrescriptionExtraction, type ServiceHealth, type Slot, type Timing,
} from '../api/extract';
import { Banner } from '../components/Banner';
import { prescriptionToDraft } from '../lib/prescriptionToDraft';

type Phase = 'idle' | 'extracting' | 'done' | 'error';

const STATUS_STYLE: Record<FieldStatus, { label: string; chip: string; box: string }> = {
    ok: { label: 'Looks right', chip: 'bg-emerald-50 text-emerald-700', box: 'border-emerald-500 bg-emerald-500/10' },
    corrected: { label: 'Auto-corrected', chip: 'bg-orange-tint text-orange', box: 'border-orange bg-orange/10' },
    unverified: { label: 'Please check', chip: 'bg-coral-tint text-coral-dark', box: 'border-coral bg-coral/10' },
};

const SLOTS_FOR_COUNT: Record<number, Slot[]> = {
    1: ['morning'],
    2: ['morning', 'night'],
    3: ['morning', 'afternoon', 'night'],
    4: ['morning', 'afternoon', 'evening', 'night'],
};

const TIMING_OPTIONS: { value: Timing; label: string }[] = [
    { value: 'before_food', label: 'Before food' },
    { value: 'with_food', label: 'With food' },
    { value: 'after_food', label: 'After food' },
    { value: 'bedtime', label: 'Bedtime' },
    { value: 'any', label: 'Anytime' },
];

const describeFrequency = (m: ExtractedMedication) => {
    if (m.frequency.as_needed) return 'Only when needed';
    const n = m.frequency.times_per_day;
    if (!n) return 'Frequency unknown';
    const slots = m.frequency.slots.length ? ` (${m.frequency.slots.join(', ')})` : '';
    return `${n}× a day${slots}`;
};

export function ScanPrescription({ onAddMedication }: { onAddMedication: (draft: MedicationDraft, onSaved: () => void) => void }) {
    const [health, setHealth] = useState<ServiceHealth | null>(null);
    const [healthError, setHealthError] = useState<string | null>(null);
    const [backend, setBackend] = useState<string | undefined>(undefined);
    const [file, setFile] = useState<File | null>(null);
    const [phase, setPhase] = useState<Phase>('idle');
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<PrescriptionExtraction | null>(null);
    const [meds, setMeds] = useState<ExtractedMedication[]>([]);
    const [added, setAdded] = useState<Set<number>>(new Set());
    const [selected, setSelected] = useState<number | null>(null);
    const [imageSize, setImageSize] = useState<{ w: number; h: number } | null>(null);
    const [feedbackNote, setFeedbackNote] = useState<string | null>(null);
    const fileInput = useRef<HTMLInputElement>(null);
    const cameraInput = useRef<HTMLInputElement>(null);

    useEffect(() => {
        let alive = true;
        getHealth()
            .then(h => {
                if (!alive) return;
                setHealth(h);
                setBackend(h.backend);
            })
            .catch((e: Error) => alive && setHealthError(e.message));
        return () => {
            alive = false;
        };
    }, []);

    const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
    useEffect(() => () => {
        if (preview) URL.revokeObjectURL(preview);
    }, [preview]);

    const pick = (f: File | null) => {
        setFile(f);
        setResult(null);
        setMeds([]);
        setAdded(new Set());
        setSelected(null);
        setImageSize(null);
        setError(null);
        setPhase('idle');
    };

    const extract = async () => {
        if (!file) return;
        setPhase('extracting');
        setError(null);
        try {
            const r = await extractPrescription(file, backend);
            setResult(r);
            setMeds(r.medications.map(m => ({ ...m, frequency: { ...m.frequency, slots: [...m.frequency.slots] } })));
            setPhase('done');
        } catch (e) {
            setError(e instanceof ExtractApiError ? e.message : 'Something went wrong while reading the prescription.');
            setPhase('error');
        }
    };

    const update = (i: number, patch: Partial<ExtractedMedication>) => setMeds(cur => cur.map((m, j) => (j === i ? { ...m, ...patch } : m)));

    const setTimesPerDay = (i: number, n: number | 'sos') => {
        const m = meds[i];
        const frequency = n === 'sos'
            ? { ...m.frequency, as_needed: true, times_per_day: null, slots: [] }
            : { ...m.frequency, as_needed: false, times_per_day: n, slots: SLOTS_FOR_COUNT[n] ?? [], pattern: null, interval_hours: null };
        update(i, { frequency });
    };

    const add = (i: number) => {
        const m = meds[i];
        onAddMedication(prescriptionToDraft(m), () => {
            setAdded(cur => new Set(cur).add(i));
            if (result?.document_id != null) {
                sendFeedback(result.document_id, { ...result, medications: meds })
                    .then(() => setFeedbackNote('Your corrections were saved to improve future scans.'))
                    .catch(() => setFeedbackNote('Could not send your corrections to the service (the medication was still added).'));
            }
        });
    };

    const busy = phase === 'extracting';
    const backendReady = health?.backend_ready ?? false;

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-extrabold">Scan prescription</h1>
                {health && (
                    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${health.status === 'ok' ? 'bg-emerald-50 text-emerald-700' : 'bg-orange-tint text-orange'}`}>
                        {health.backend} · {health.model}
                    </span>
                )}
            </div>

            {healthError && <Banner tone="warn">{healthError}</Banner>}
            {health && !backendReady && <Banner tone="warn">{health.backend_message}</Banner>}
            {health && health.status === 'ok' && (
                <Banner>Photos are read by your own extraction service. Check every value before you add a medicine.</Banner>
            )}

            <section className="card p-4 space-y-3">
                <input ref={fileInput} type="file" accept="image/*" className="hidden" onChange={e => pick(e.target.files?.[0] ?? null)} />
                <input ref={cameraInput} type="file" accept="image/*" capture="environment" className="hidden" onChange={e => pick(e.target.files?.[0] ?? null)} />
                <div className="grid grid-cols-2 gap-2.5">
                    <button className="btn-soft !py-3" onClick={() => cameraInput.current?.click()} disabled={busy}><Camera size={18} /> Take photo</button>
                    <button className="btn-soft !py-3" onClick={() => fileInput.current?.click()} disabled={busy}><ImageUp size={18} /> Choose image</button>
                </div>

                {health && health.backends.length > 1 && (
                    <div>
                        <span className="label">Read with</span>
                        <div className="mt-2 flex flex-wrap gap-2">
                            {health.backends.map(b => (
                                <button key={b} className={backend === b ? 'chip-on' : 'chip-off'} onClick={() => setBackend(b)} disabled={busy}>{b}</button>
                            ))}
                        </div>
                    </div>
                )}

                {preview && phase !== 'done' && (
                    <img src={preview} alt="Selected prescription" className="max-h-80 w-full rounded-xl object-contain bg-ice" />
                )}

                {file && phase !== 'done' && (
                    <button className="btn-primary w-full !py-3.5" onClick={extract} disabled={busy || (health !== null && !backendReady)}>
                        {busy ? <Loader2 size={18} className="animate-spin" /> : <ScanLine size={18} />}
                        {busy ? 'Reading the prescription… this can take up to a minute' : 'Read prescription'}
                    </button>
                )}
                {error && <p className="flex items-start gap-1.5 text-sm text-coral-dark"><CircleAlert size={16} className="mt-0.5 shrink-0" /> {error}</p>}
            </section>

            {result && phase === 'done' && (
                <>
                    <Banner>
                        <span className="font-semibold">{result.medications.length} medicine{result.medications.length === 1 ? '' : 's'} found</span>
                        {result.patient_name && <> · Patient: {result.patient_name}</>}
                        {result.doctor_name && <> · {result.doctor_name}</>}
                        {result.prescribed_on && <> · {result.prescribed_on}</>}
                        <span className="block text-xs text-muted mt-0.5">
                            {result.handwritten ? 'Handwritten' : 'Printed'} · {result.backend}/{result.model} · {(result.processing_ms / 1000).toFixed(1)} s
                        </span>
                    </Banner>
                    {result.warnings.length > 0 && (
                        <Banner tone="warn">
                            <ul className="list-disc pl-4 space-y-0.5">
                                {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
                            </ul>
                        </Banner>
                    )}

                    {result.document_id != null && (
                        <div className="card p-2">
                            <div className="relative">
                                <img
                                    src={documentImageUrl(result.document_id)}
                                    alt="Processed prescription"
                                    className="w-full rounded-xl"
                                    onLoad={e => setImageSize({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
                                />
                                {imageSize && meds.map((m, i) => {
                                    if (!m.bbox) return null;
                                    const xs = m.bbox.map(p => p[0]);
                                    const ys = m.bbox.map(p => p[1]);
                                    const left = (Math.min(...xs) / imageSize.w) * 100;
                                    const top = (Math.min(...ys) / imageSize.h) * 100;
                                    const width = ((Math.max(...xs) - Math.min(...xs)) / imageSize.w) * 100;
                                    const height = ((Math.max(...ys) - Math.min(...ys)) / imageSize.h) * 100;
                                    return (
                                        <button
                                            key={i}
                                            aria-label={`Highlight ${m.name}`}
                                            onClick={() => setSelected(i)}
                                            className={`absolute rounded-md border-2 transition ${STATUS_STYLE[m.status].box} ${selected === i ? 'ring-4 ring-primary/40' : ''}`}
                                            style={{ left: `${left}%`, top: `${top}%`, width: `${width}%`, height: `${height}%` }}
                                        />
                                    );
                                })}
                            </div>
                        </div>
                    )}

                    {meds.length === 0 && (
                        <div className="card p-8 text-center text-muted">No medicines were found on this image. Try a sharper, straighter photo.</div>
                    )}

                    <ul className="space-y-3">
                        {meds.map((m, i) => {
                            const style = STATUS_STYLE[m.status];
                            const isAdded = added.has(i);
                            const unverified = Object.entries(m.field_status).filter(([, s]) => s === 'unverified').map(([k]) => k);
                            return (
                                <li key={i} className={`card p-4 space-y-3 ${selected === i ? 'ring-4 ring-primary/25' : ''}`} onClick={() => setSelected(i)}>
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="min-w-0 flex-1">
                                            <input
                                                className="input !py-2 font-bold"
                                                value={m.name}
                                                aria-label="Medicine name"
                                                onChange={e => update(i, { name: e.target.value, brand_matched: null })}
                                            />
                                            <p className="mt-1 text-xs text-muted">
                                                {m.brand_matched && <>Matched <span className="font-semibold">{m.brand_matched}</span></>}
                                                {m.composition && <> · {m.composition}</>}
                                                {m.frequency_text && <> · as written: “{m.frequency_text}{m.timing_text ? ` ${m.timing_text}` : ''}{m.duration_text ? ` ${m.duration_text}` : ''}”</>}
                                            </p>
                                        </div>
                                        <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${style.chip}`}>{style.label}</span>
                                    </div>

                                    <div className="grid grid-cols-2 gap-2.5 text-sm">
                                        <label className="space-y-1">
                                            <span className="label">Strength</span>
                                            <input className="input !py-2" value={m.strength ?? ''} placeholder="e.g. 650 mg" onChange={e => update(i, { strength: e.target.value || null })} />
                                        </label>
                                        <label className="space-y-1">
                                            <span className="label">Dose each time</span>
                                            <input className="input !py-2" value={m.dose ?? ''} placeholder="e.g. 1 or 5 ml" onChange={e => update(i, { dose: e.target.value || null })} />
                                        </label>
                                    </div>

                                    <div>
                                        <span className="label">How often</span>
                                        <div className="mt-2 flex flex-wrap gap-2">
                                            {[1, 2, 3, 4].map(n => (
                                                <button key={n} className={!m.frequency.as_needed && m.frequency.times_per_day === n ? 'chip-on' : 'chip-off'} onClick={() => setTimesPerDay(i, n)}>
                                                    {n}× a day
                                                </button>
                                            ))}
                                            <button className={m.frequency.as_needed ? 'chip-on' : 'chip-off'} onClick={() => setTimesPerDay(i, 'sos')}>When needed</button>
                                        </div>
                                        <p className="mt-1.5 text-xs text-muted">{describeFrequency(m)}</p>
                                    </div>

                                    <div>
                                        <span className="label">Food</span>
                                        <div className="mt-2 flex flex-wrap gap-2">
                                            {TIMING_OPTIONS.map(o => (
                                                <button key={o.value} className={(m.timing ?? 'any') === o.value ? 'chip-on' : 'chip-off'} onClick={() => update(i, { timing: o.value })}>{o.label}</button>
                                            ))}
                                        </div>
                                    </div>

                                    <label className="flex items-center justify-between gap-3">
                                        <span className="font-medium">For how many days</span>
                                        <input
                                            type="number"
                                            min={1}
                                            max={365}
                                            className="w-24 rounded-lg border border-line py-1.5 text-center font-bold outline-none focus:border-primary"
                                            value={m.duration_days ?? ''}
                                            placeholder="?"
                                            onChange={e => update(i, { duration_days: e.target.value ? Number(e.target.value) : null })}
                                        />
                                    </label>

                                    {unverified.length > 0 && (
                                        <p className="flex items-center gap-1.5 text-xs text-coral-dark"><CircleAlert size={14} /> Check: {unverified.join(', ')}</p>
                                    )}

                                    <button className={`w-full ${isAdded ? 'btn-soft' : 'btn-primary'}`} disabled={isAdded} onClick={e => { e.stopPropagation(); add(i); }}>
                                        {isAdded ? <><Check size={18} /> Added to medications</> : <><Plus size={18} /> Review and add</>}
                                    </button>
                                </li>
                            );
                        })}
                    </ul>

                    {feedbackNote && <p className="flex items-center gap-1.5 text-xs text-muted"><Sparkles size={14} /> {feedbackNote}</p>}

                    <button className="btn-ghost w-full" onClick={() => pick(null)}><RotateCcw size={16} /> Scan another prescription</button>
                </>
            )}
        </div>
    );
}
