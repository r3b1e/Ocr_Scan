/**
 * Add / Edit Medication — web twin of HealthApp's AddMedicationScreen: same
 * fields, same validation (shared validateDraft) and the same picker sheets.
 */
import { useMemo, useState } from 'react';
import { AlarmClock, Bell, BellRing, Check, ChevronDown, ChevronLeft, CircleAlert, Clock, Minus, Plus, Trash2 } from 'lucide-react';
import {
    buildMedication, createEmptyDraft, DECIMAL_UNITS, defaultUnitForType, draftFromMedication, FREQUENCY_MODES, frequencySummary, FrequencyType,
    hasErrors, LEAD_OPTIONS, MAX_NAME_LENGTH, MEAL_RELATIONS, MEDICATION_TYPES, MULTI_DAILY_MAX, MULTI_DAILY_MIN, reconcileUnit, resizeTimes,
    splitUnitsForType, timesPerDayFor, toISODate, parseISODateLocal, validateDraft, WEEKDAY_LABELS,
    type DoseUnit, type FrequencyConfig, type Medication, type MedicationDraft, type MedicationType, type TimeOfDay,
} from '@shared/index';
import { store, useStore } from '../store';
import { Sheet } from '../components/Sheet';
import { Toggle } from '../components/Toggle';
import { iconFor, MedIcon } from '../components/icons';

const pad = (n: number) => String(n).padStart(2, '0');
const timeValue = (t: TimeOfDay) => `${pad(t.hour)}:${pad(t.minute)}`;
const parseTime = (v: string): TimeOfDay | null => {
    const m = /^(\d{1,2}):(\d{2})/.exec(v);
    return m ? { hour: +m[1], minute: +m[2] } : null;
};

export function MedForm({ med, initial, onSaved, onClose }: { med?: Medication; initial?: MedicationDraft; onSaved?: () => void; onClose: () => void }) {
    const { meds } = useStore();
    const editing = !!med;
    const [draft, setDraft] = useState<MedicationDraft>(() => (med ? draftFromMedication(med) : initial ? { ...createEmptyDraft(), ...initial } : createEmptyDraft()));
    const [touched, setTouched] = useState(false);
    const [sheet, setSheet] = useState<null | 'type' | 'unit' | 'freq'>(null);
    const [unitNote, setUnitNote] = useState<string | null>(null);

    const patch = (p: Partial<MedicationDraft>) => setDraft(d => ({ ...d, ...p }));

    const existingActiveNames = useMemo(
        () => meds.filter(m => m.status === 'active' && m.id !== med?.id).map(m => m.name),
        [meds, med?.id],
    );
    const result = useMemo(() => validateDraft(draft, { existingActiveNames }), [draft, existingActiveNames]);
    const err = (k: string) => (touched ? result.errors[k] : undefined);

    const setType = (type: MedicationType) => {
        const { unit, changed } = reconcileUnit(type, draft.doseUnit);
        patch({ type, doseUnit: unit });
        setUnitNote(changed && unit !== draft.doseUnit ? `Dose unit set to ${unit}` : null);
        setSheet(null);
    };

    const setFrequency = (frequencyType: FrequencyType, frequencyConfig: FrequencyConfig) => {
        const n = timesPerDayFor(frequencyType, frequencyConfig);
        patch({ frequencyType, frequencyConfig: { ...frequencyConfig, timesPerDay: n }, scheduleTimes: resizeTimes(draft.scheduleTimes, n) });
        setSheet(null);
    };

    const qty = Number(draft.quantityPerDose) || 0;
    const step = DECIMAL_UNITS.has(draft.doseUnit) ? 0.5 : 1;
    const bumpQty = (d: number) => patch({ quantityPerDose: String(Math.max(step, Math.round((qty + d) * 100) / 100)) });

    const save = () => {
        setTouched(true);
        if (hasErrors(result)) return;
        const built = buildMedication({ ...draft, scheduleTimes: [...draft.scheduleTimes].sort((a, b) => a.hour * 60 + a.minute - (b.hour * 60 + b.minute)) });
        store.saveMed(built);
        onSaved?.();
        onClose();
    };

    return (
        <div className="fixed inset-0 z-40 bg-ice overflow-y-auto animate-fade-in" role="dialog" aria-label={editing ? 'Edit medication' : 'Add medication'}>
            <div className="mx-auto max-w-xl pb-32">
                <header className="sticky top-0 z-10 flex items-center gap-2 bg-ice/90 backdrop-blur px-3 py-3">
                    <button className="btn-ghost !p-2 rounded-full" onClick={onClose} aria-label="Back">
                        <ChevronLeft size={24} />
                    </button>
                    <h1 className="text-lg font-bold">{editing ? 'Edit Medication' : 'Add Medication'}</h1>
                </header>

                <div className="space-y-4 px-4">
                    {/* Name */}
                    <section className="card p-4">
                        <label className="label" htmlFor="med-name">Pill’s Name</label>
                        <div className="mt-2 flex items-center gap-3">
                            <MedIcon type={draft.type} />
                            <input id="med-name" className="input" placeholder="e.g. Metformin 500" maxLength={MAX_NAME_LENGTH + 10} value={draft.name} onChange={e => patch({ name: e.target.value })} autoFocus={!editing} />
                        </div>
                        {err('name') && <p className="mt-2 text-sm text-coral-dark">{err('name')}</p>}
                        {result.warnings.name && <p className="mt-2 text-sm text-orange">{result.warnings.name}</p>}
                    </section>

                    {/* Type + dates */}
                    <section className="card divide-y divide-line">
                        <button className="row w-full text-left hover:bg-ice/60 rounded-t-2xl" onClick={() => setSheet('type')}>
                            <span className="font-medium">Type</span>
                            <span className="flex items-center gap-1 font-semibold">{draft.type} <ChevronDown size={18} className="text-muted" /></span>
                        </button>
                        <label className="row">
                            <span className="font-medium">Start Date</span>
                            <input type="date" className="bg-transparent text-right font-semibold text-primary-dark outline-none" value={toISODate(draft.startDate)} onChange={e => e.target.value && patch({ startDate: parseISODateLocal(e.target.value) })} aria-label="Start date" />
                        </label>
                        <label className="row">
                            <span className="font-medium">End Date</span>
                            <input type="date" className="bg-transparent text-right font-semibold text-primary-dark outline-none" value={toISODate(draft.endDate)} min={toISODate(draft.startDate)} onChange={e => e.target.value && patch({ endDate: parseISODateLocal(e.target.value) })} aria-label="End date" />
                        </label>
                    </section>
                    {err('dates') && <p className="-mt-2 px-1 text-sm text-coral-dark">{err('dates')}</p>}
                    {!err('dates') && result.warnings.dates && <p className="-mt-2 px-1 text-sm text-orange">{result.warnings.dates}</p>}

                    {/* Dose */}
                    <section className="card divide-y divide-line">
                        <div className="row">
                            <span className="font-medium">Amount</span>
                            <div className="flex items-center gap-2">
                                <button className="grid h-9 w-9 place-items-center rounded-full bg-primary-tint text-primary-dark transition active:scale-90 disabled:opacity-40" onClick={() => bumpQty(-step)} disabled={qty <= step} aria-label="Decrease amount">
                                    <Minus size={18} />
                                </button>
                                <input className="w-16 rounded-lg border border-line py-1.5 text-center font-bold outline-none focus:border-primary" inputMode="decimal" value={draft.quantityPerDose} onChange={e => patch({ quantityPerDose: e.target.value.replace(/[^\d.]/g, '') })} aria-label="Amount per dose" />
                                <button className="grid h-9 w-9 place-items-center rounded-full bg-primary-tint text-primary-dark transition active:scale-90" onClick={() => bumpQty(step)} aria-label="Increase amount">
                                    <Plus size={18} />
                                </button>
                            </div>
                        </div>
                        <button className="row w-full text-left hover:bg-ice/60 rounded-b-2xl" onClick={() => setSheet('unit')}>
                            <span className="font-medium">Dose unit</span>
                            <span className="flex items-center gap-1 font-semibold">{draft.doseUnit} <ChevronDown size={18} className="text-muted" /></span>
                        </button>
                    </section>
                    {err('quantity') && <p className="-mt-2 px-1 text-sm text-coral-dark">{err('quantity')}</p>}
                    {unitNote && <p className="-mt-2 px-1 text-sm text-primary-dark">{unitNote}</p>}

                    {/* Frequency + times */}
                    <section className="card divide-y divide-line">
                        <button className="row w-full text-left hover:bg-ice/60 rounded-t-2xl" onClick={() => setSheet('freq')}>
                            <span className="font-medium">Frequency</span>
                            <span className="flex items-center gap-1 font-semibold text-primary-dark">{frequencySummary(draft.frequencyType, draft.frequencyConfig)} <ChevronDown size={18} className="text-muted" /></span>
                        </button>
                        <div className="px-4 py-3.5">
                            <div className="flex items-center justify-between">
                                <span className="font-medium">Schedule time{draft.scheduleTimes.length > 1 ? 's' : ''}</span>
                                <Clock size={18} className="text-muted" />
                            </div>
                            <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 gap-2">
                                {draft.scheduleTimes.map((t, i) => (
                                    <label key={i} className="flex items-center gap-2 rounded-xl border border-line bg-ice px-3 py-2 focus-within:border-primary focus-within:ring-4 focus-within:ring-primary/15">
                                        <span className="text-xs font-bold text-muted">#{i + 1}</span>
                                        <input
                                            type="time"
                                            className="w-full bg-transparent font-semibold outline-none"
                                            value={timeValue(t)}
                                            aria-label={`Dose time ${i + 1}`}
                                            onChange={e => {
                                                const v = parseTime(e.target.value);
                                                if (!v) return;
                                                patch({ scheduleTimes: draft.scheduleTimes.map((x, j) => (j === i ? v : x)) });
                                            }}
                                        />
                                    </label>
                                ))}
                            </div>
                        </div>
                    </section>
                    {err('frequency') && <p className="-mt-2 px-1 text-sm text-coral-dark">{err('frequency')}</p>}
                    {err('times') && <p className="-mt-2 px-1 text-sm text-coral-dark">{err('times')}</p>}
                    {result.warnings.times && <p className="-mt-2 px-1 text-sm text-orange">{result.warnings.times}</p>}
                    {result.warnings.frequency && <p className="-mt-2 px-1 text-sm text-orange">{result.warnings.frequency}</p>}

                    {/* Food */}
                    <section className="card p-4">
                        <span className="label">Food</span>
                        <div className="mt-2.5 flex flex-wrap gap-2">
                            {MEAL_RELATIONS.map(m => (
                                <button key={m.value} className={draft.mealRelation === m.value ? 'chip-on' : 'chip-off'} onClick={() => patch({ mealRelation: m.value })}>
                                    {m.label}
                                </button>
                            ))}
                        </div>
                    </section>

                    {/* Reminders */}
                    <section className="card">
                        <div className="row">
                            <span className="flex items-center gap-2 font-medium"><Bell size={18} className="text-primary" /> Reminders</span>
                            <Toggle checked={draft.remindersEnabled} onChange={v => patch({ remindersEnabled: v })} label="Reminders" />
                        </div>
                        {draft.remindersEnabled && (
                            <div className="space-y-4 border-t border-line px-4 py-4">
                                <div>
                                    <span className="label">Alert type</span>
                                    <div className="mt-2.5 grid grid-cols-2 gap-2.5">
                                        {([
                                            { key: 'notification', label: 'Notification', Icon: Bell, hint: 'A gentle chime + popup' },
                                            { key: 'alarm', label: 'Alarm', Icon: BellRing, hint: 'Rings until you respond' },
                                        ] as const).map(o => {
                                            const on = draft.reminderMode === o.key;
                                            return (
                                                <button key={o.key} onClick={() => patch({ reminderMode: o.key })} aria-pressed={on} className={`relative rounded-2xl border-2 p-3 text-left transition ${on ? (o.key === 'alarm' ? 'border-coral bg-coral-tint/50' : 'border-primary bg-primary-tint/50') : 'border-line hover:border-slate-300'}`}>
                                                    <o.Icon size={22} className={on ? (o.key === 'alarm' ? 'text-coral-dark' : 'text-primary-dark') : 'text-muted'} />
                                                    <div className="mt-1.5 font-bold">{o.label}</div>
                                                    <div className="text-xs text-muted">{o.hint}</div>
                                                    {on && <Check size={16} className={`absolute right-3 top-3 ${o.key === 'alarm' ? 'text-coral-dark' : 'text-primary-dark'}`} />}
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>
                                <div>
                                    <span className="label flex items-center gap-1.5"><AlarmClock size={14} /> Remind me early</span>
                                    <div className="mt-2.5 flex flex-wrap gap-2">
                                        {LEAD_OPTIONS.map(n => (
                                            <button key={n} className={draft.reminderLeadMinutes === n ? 'chip-on' : 'chip-off'} onClick={() => patch({ reminderLeadMinutes: n })}>
                                                {n === 0 ? 'On time' : `${n} min before`}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}
                    </section>

                    {editing && (
                        <button
                            className="btn w-full py-3 text-coral-dark hover:bg-coral-tint"
                            onClick={() => {
                                if (!confirm(`Delete ${med!.name}? Its reminders stop; past history is kept.`)) return;
                                store.setMedStatus(med!.id, 'deleted' as Medication['status']);
                                onClose();
                            }}
                        >
                            <Trash2 size={18} /> Delete medication
                        </button>
                    )}
                </div>
            </div>

            <div className="fixed inset-x-0 bottom-0 z-20 bg-gradient-to-t from-ice via-ice to-transparent pt-6 pb-[max(1rem,env(safe-area-inset-bottom))]">
                <div className="mx-auto max-w-xl px-4">
                    {touched && hasErrors(result) && (
                        <p className="mb-2 flex items-center gap-1.5 text-sm text-coral-dark"><CircleAlert size={16} /> Fix the highlighted fields to continue</p>
                    )}
                    <button className="btn-primary w-full !py-4 text-base" onClick={save}>
                        {editing ? 'Save Changes' : 'Done'}
                    </button>
                </div>
            </div>

            <TypeSheet open={sheet === 'type'} value={draft.type} onClose={() => setSheet(null)} onPick={setType} />
            <UnitSheet open={sheet === 'unit'} type={draft.type} value={draft.doseUnit} onClose={() => setSheet(null)} onPick={u => { patch({ doseUnit: u }); setUnitNote(null); setSheet(null); }} />
            {sheet === 'freq' && <FrequencySheet type={draft.frequencyType} config={draft.frequencyConfig} onClose={() => setSheet(null)} onApply={setFrequency} />}
        </div>
    );
}

function TypeSheet({ open, value, onClose, onPick }: { open: boolean; value: MedicationType; onClose: () => void; onPick: (t: MedicationType) => void }) {
    return (
        <Sheet open={open} title="Medication type" onClose={onClose}>
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 pb-2">
                {MEDICATION_TYPES.map(e => {
                    const Icon = iconFor(e.icon);
                    const on = e.type === value;
                    return (
                        <button key={e.type} onClick={() => onPick(e.type)} aria-pressed={on} className={`flex flex-col items-center gap-1.5 rounded-2xl border-2 px-1 py-3 transition ${on ? 'border-primary bg-primary-tint/60 text-primary-dark' : 'border-transparent bg-ice hover:border-line'}`}>
                            <Icon size={24} />
                            <span className="text-xs font-semibold text-center leading-tight">{e.label}</span>
                        </button>
                    );
                })}
            </div>
        </Sheet>
    );
}

function UnitSheet({ open, type, value, onClose, onPick }: { open: boolean; type: MedicationType; value: DoseUnit; onClose: () => void; onPick: (u: DoseUnit) => void }) {
    const { suggested, others } = splitUnitsForType(type);
    const Group = ({ title, units }: { title: string; units: DoseUnit[] }) => (
        <div className="mb-4">
            <div className="label mb-2">{title}</div>
            <div className="flex flex-wrap gap-2">
                {units.map(u => (
                    <button key={u} className={u === value ? 'chip-on' : 'chip-off'} onClick={() => onPick(u)}>{u}</button>
                ))}
            </div>
        </div>
    );
    return (
        <Sheet open={open} title="Dose unit" onClose={onClose}>
            <Group title={`Suggested for ${type}`} units={suggested.length ? suggested : [defaultUnitForType(type)]} />
            <Group title="All units" units={others} />
        </Sheet>
    );
}

function FrequencySheet({ type, config, onClose, onApply }: { type: FrequencyType; config: FrequencyConfig; onClose: () => void; onApply: (t: FrequencyType, c: FrequencyConfig) => void }) {
    const [t, setT] = useState(type);
    const [multi, setMulti] = useState(config.multiCount ?? MULTI_DAILY_MIN);
    const [weekdays, setWeekdays] = useState<number[]>(config.weekdays ?? [1, 3, 5]);
    const [interval, setIntervalDays] = useState(config.intervalDays ?? 2);
    const [dom, setDom] = useState(config.dayOfMonth ?? new Date().getDate());

    const cfg = (): FrequencyConfig => {
        switch (t) {
            case FrequencyType.MultiDaily: return { timesPerDay: multi, multiCount: multi };
            case FrequencyType.SpecificDays: return { timesPerDay: 1, weekdays: [...weekdays].sort() };
            case FrequencyType.EveryXDays: return { timesPerDay: 1, intervalDays: interval };
            case FrequencyType.DayOfMonth: return { timesPerDay: 1, dayOfMonth: dom };
            default: return { timesPerDay: timesPerDayFor(t, { timesPerDay: 1 }) };
        }
    };
    const invalid = t === FrequencyType.SpecificDays && weekdays.length === 0;

    const Stepper = ({ value, set, min, max, suffix }: { value: number; set: (n: number) => void; min: number; max: number; suffix: string }) => (
        <div className="mt-3 flex items-center justify-center gap-4 rounded-2xl bg-ice p-3">
            <button className="grid h-10 w-10 place-items-center rounded-full bg-white shadow-card disabled:opacity-40" onClick={() => set(Math.max(min, value - 1))} disabled={value <= min} aria-label="Decrease"><Minus size={18} /></button>
            <div className="min-w-[110px] text-center"><span className="text-2xl font-extrabold text-primary-dark">{value}</span> <span className="text-sm text-muted">{suffix}</span></div>
            <button className="grid h-10 w-10 place-items-center rounded-full bg-white shadow-card disabled:opacity-40" onClick={() => set(Math.min(max, value + 1))} disabled={value >= max} aria-label="Increase"><Plus size={18} /></button>
        </div>
    );

    return (
        <Sheet
            open
            title="How often?"
            onClose={onClose}
            footer={<button className="btn-primary w-full" disabled={invalid} onClick={() => onApply(t, cfg())}>Apply</button>}
        >
            <div className="space-y-2">
                {FREQUENCY_MODES.map(m => {
                    const on = m.type === t;
                    return (
                        <div key={m.type} className={`rounded-2xl border-2 transition ${on ? 'border-primary bg-primary-tint/40' : 'border-line'}`}>
                            <button className="flex w-full items-center gap-3 px-4 py-3 text-left" onClick={() => setT(m.type)} aria-pressed={on}>
                                <span className={`grid h-5 w-5 place-items-center rounded-full border-2 ${on ? 'border-primary' : 'border-slate-300'}`}>{on && <span className="h-2.5 w-2.5 rounded-full bg-primary" />}</span>
                                <span className="flex-1"><span className="block font-semibold">{m.label}</span><span className="block text-xs text-muted">{m.hint}</span></span>
                            </button>
                            {on && t === FrequencyType.MultiDaily && <div className="px-4 pb-4"><Stepper value={multi} set={setMulti} min={MULTI_DAILY_MIN} max={MULTI_DAILY_MAX} suffix="times a day" /></div>}
                            {on && t === FrequencyType.EveryXDays && <div className="px-4 pb-4"><Stepper value={interval} set={setIntervalDays} min={1} max={30} suffix={interval === 1 ? 'day' : 'days'} /></div>}
                            {on && t === FrequencyType.DayOfMonth && <div className="px-4 pb-4"><Stepper value={dom} set={setDom} min={1} max={31} suffix="of each month" /></div>}
                            {on && t === FrequencyType.SpecificDays && (
                                <div className="flex flex-wrap gap-1.5 px-4 pb-4">
                                    {WEEKDAY_LABELS.map((d, i) => {
                                        const sel = weekdays.includes(i);
                                        return (
                                            <button key={d} className={`h-10 w-10 rounded-full text-sm font-bold transition ${sel ? 'bg-primary text-white' : 'bg-white border border-line'}`} onClick={() => setWeekdays(w => (sel ? w.filter(x => x !== i) : [...w, i]))} aria-pressed={sel}>
                                                {d.slice(0, 2)}
                                            </button>
                                        );
                                    })}
                                    {invalid && <p className="w-full text-sm text-coral-dark">Pick at least one day</p>}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </Sheet>
    );
}
