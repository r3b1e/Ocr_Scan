import { useState } from 'react';
import { Bell, BellOff, BellRing, Pause, Pencil, Play, Plus, Trash2 } from 'lucide-react';
import { formatTime, frequencySummary, MedicationStatus, todayISO, type Medication } from '@shared/index';
import { store, useStore } from '../store';
import { MedIcon } from '../components/icons';

export function Medications({ onAdd, onEdit }: { onAdd: () => void; onEdit: (m: Medication) => void }) {
    const { meds } = useStore();
    const today = todayISO();
    const [tab, setTab] = useState<'active' | 'paused' | 'finished'>('active');

    const live = meds.filter(m => m.status !== MedicationStatus.Deleted);
    const groups = {
        active: live.filter(m => m.status === MedicationStatus.Active && m.endDate >= today),
        paused: live.filter(m => m.status === MedicationStatus.Paused),
        finished: live.filter(m => m.status === MedicationStatus.Completed || (m.status === MedicationStatus.Active && m.endDate < today)),
    };
    const list = groups[tab];

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-extrabold">Medications</h1>
                <button className="btn-primary !py-2.5" onClick={onAdd}>
                    <Plus size={18} /> Add
                </button>
            </div>
            <div className="card grid grid-cols-3 gap-1 p-1" role="tablist">
                {(['active', 'paused', 'finished'] as const).map(k => (
                    <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={`rounded-xl py-2 text-sm font-semibold capitalize transition ${tab === k ? 'bg-primary text-white shadow-lift' : 'text-muted hover:bg-ice'}`}>
                        {k} <span className={`ml-0.5 text-xs ${tab === k ? 'text-white/80' : 'text-slate-400'}`}>{groups[k].length}</span>
                    </button>
                ))}
            </div>

            {list.length === 0 ? (
                <div className="card p-8 text-center text-muted">
                    {tab === 'active' ? (
                        <>
                            <p>No active medications.</p>
                            <button className="btn-soft mt-4" onClick={onAdd}><Plus size={16} /> Add medication</button>
                        </>
                    ) : tab === 'paused' ? 'Nothing paused.' : 'No finished courses yet.'}
                </div>
            ) : (
                <ul className="grid gap-3 sm:grid-cols-2">
                    {list.map(m => (
                        <MedCard key={m.id} m={m} finished={tab === 'finished'} onEdit={() => onEdit(m)} />
                    ))}
                </ul>
            )}
        </div>
    );
}

function MedCard({ m, finished, onEdit }: { m: Medication; finished: boolean; onEdit: () => void }) {
    const paused = m.status === MedicationStatus.Paused;
    const ModeIcon = !m.remindersEnabled ? BellOff : m.reminderMode === 'alarm' ? BellRing : Bell;
    return (
        <li className={`card p-4 transition hover:shadow-lg ${paused || finished ? 'opacity-75' : ''}`} data-testid="med-card">
            <div className="flex items-start gap-3">
                <MedIcon type={m.type} tone={paused || finished ? 'muted' : 'primary'} />
                <div className="min-w-0 flex-1">
                    <h3 className="font-bold leading-tight break-words">{m.name}</h3>
                    <p className="text-sm text-muted">{m.quantityPerDose} {m.doseUnit} · {frequencySummary(m.frequencyType, m.frequencyConfig)}</p>
                </div>
                <ModeIcon size={18} className={m.reminderMode === 'alarm' && m.remindersEnabled ? 'text-coral' : 'text-muted'} aria-label={!m.remindersEnabled ? 'Reminders off' : m.reminderMode} />
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
                {m.scheduleTimes.map((t, i) => (
                    <span key={i} className="rounded-lg bg-primary-tint px-2 py-1 text-xs font-semibold text-primary-dark">{formatTime(t)}</span>
                ))}
            </div>
            <p className="mt-2 text-xs text-muted">{m.startDate} → {m.endDate}</p>
            <div className="mt-3 flex gap-1 border-t border-line pt-2">
                <button className="btn-ghost !px-2.5 text-sm" onClick={onEdit}><Pencil size={15} /> Edit</button>
                {!finished && (
                    paused ? (
                        <button className="btn-ghost !px-2.5 text-sm text-primary-dark" onClick={() => store.setMedStatus(m.id, MedicationStatus.Active)}><Play size={15} /> Resume</button>
                    ) : (
                        <button className="btn-ghost !px-2.5 text-sm" onClick={() => store.setMedStatus(m.id, MedicationStatus.Paused)}><Pause size={15} /> Pause</button>
                    )
                )}
                <button
                    className="btn-ghost !px-2.5 text-sm text-coral-dark ml-auto"
                    onClick={() => confirm(`Delete ${m.name}? Its reminders stop; past history is kept.`) && store.setMedStatus(m.id, MedicationStatus.Deleted)}
                    aria-label={`Delete ${m.name}`}
                >
                    <Trash2 size={15} />
                </button>
            </div>
        </li>
    );
}
