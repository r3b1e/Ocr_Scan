import { useMemo, useState } from 'react';
import { Award, Flame, TrendingUp } from 'lucide-react';
import { adherence, calendarOf, dosesForDay, formatTime, todayISO } from '@shared/index';
import { useStore } from '../store';
import { useNow } from '../hooks';
import { MedIcon } from '../components/icons';

const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export function History() {
    const { meds, doses } = useStore();
    const now = useNow(60_000);
    const today = todayISO(now);
    const a = useMemo(() => adherence(meds, doses, 7, now), [meds, doses, now]);
    const [sel, setSel] = useState(today);
    const views = useMemo(() => dosesForDay(meds, doses, sel, now).filter(v => v.state !== 'upcoming'), [meds, doses, sel, now]);

    const pctColor = a.pct == null ? 'text-muted' : a.pct >= 80 ? 'text-emerald-600' : a.pct >= 50 ? 'text-orange' : 'text-coral-dark';

    return (
        <div className="space-y-4">
            <h1 className="text-2xl font-extrabold">History</h1>

            <div className="grid grid-cols-2 gap-3">
                <div className="card p-4">
                    <div className="flex items-center gap-1.5 text-sm font-semibold text-muted"><TrendingUp size={16} /> 7-day adherence</div>
                    <div className={`mt-2 text-4xl font-extrabold ${pctColor}`} data-testid="adherence-pct">{a.pct == null ? '—' : `${a.pct}%`}</div>
                    <div className="mt-1 text-xs text-muted">{a.taken} of {a.scheduled} doses taken</div>
                </div>
                <div className="card p-4">
                    <div className="flex items-center gap-1.5 text-sm font-semibold text-muted"><Flame size={16} className="text-orange" /> Streak</div>
                    <div className="mt-2 text-4xl font-extrabold text-ink">{a.streak}<span className="ml-1 text-base font-semibold text-muted">day{a.streak === 1 ? '' : 's'}</span></div>
                    <div className="mt-1 text-xs text-muted">{a.streak >= 7 ? <span className="inline-flex items-center gap-1 text-emerald-600"><Award size={12} /> A full week!</span> : 'Every dose taken'}</div>
                </div>
            </div>

            <div className="card p-4">
                <div className="mb-3 text-sm font-semibold text-muted">Last 7 days</div>
                <div className="flex h-36 items-end gap-2">
                    {a.days.map(d => {
                        const pct = d.counted ? d.taken / d.counted : 0;
                        const isSel = d.dateISO === sel;
                        return (
                            <button key={d.dateISO} className="group flex h-full flex-1 flex-col items-center justify-end gap-1.5" onClick={() => setSel(d.dateISO)} aria-pressed={isSel} aria-label={`${d.dateISO}: ${d.taken} of ${d.counted}`}>
                                <span className="text-[10px] font-semibold text-muted">{d.counted ? `${Math.round(pct * 100)}%` : ''}</span>
                                <div className={`relative w-full max-w-[36px] flex-1 overflow-hidden rounded-lg ${isSel ? 'bg-primary-tint ring-2 ring-primary' : 'bg-slate-100 group-hover:bg-slate-200'}`}>
                                    <div className={`absolute inset-x-0 bottom-0 rounded-lg transition-all duration-500 ${pct >= 0.8 ? 'bg-primary' : pct > 0 ? 'bg-orange' : 'bg-transparent'}`} style={{ height: `${pct * 100}%` }} />
                                </div>
                                <span className={`text-xs font-semibold ${isSel ? 'text-primary-dark' : 'text-muted'}`}>{d.dateISO === today ? 'Today' : WD[calendarOf(d.dateISO).weekday]}</span>
                            </button>
                        );
                    })}
                </div>
            </div>

            <div>
                <h2 className="mb-2 px-1 text-lg font-bold">{sel === today ? 'Today' : sel}</h2>
                {views.length === 0 ? (
                    <div className="card p-6 text-center text-muted">No doses logged or missed on this day.</div>
                ) : (
                    <ul className="card divide-y divide-line">
                        {views.map(v => (
                            <li key={v.id} className={`flex items-center gap-3 px-4 py-3 ${v.med.status === 'deleted' ? 'opacity-50' : ''}`}>
                                <MedIcon type={v.med.type} size={36} tone={v.state === 'missed' ? 'coral' : 'muted'} />
                                <div className="min-w-0 flex-1">
                                    <div className="font-semibold break-words">{v.med.name}{v.med.status === 'deleted' && <span className="ml-1 text-xs font-normal">(deleted)</span>}</div>
                                    <div className="text-xs text-muted">{formatTime(v.time)}{v.log ? ` · logged ${new Date(v.log.at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}` : ''}</div>
                                </div>
                                <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${v.state === 'taken' ? 'bg-emerald-50 text-emerald-700' : v.state === 'missed' ? 'bg-orange-tint text-orange' : v.state === 'due' ? 'bg-coral-tint text-coral-dark' : 'bg-slate-100 text-muted'}`}>
                                    {v.state === 'due' ? 'Due' : v.state[0].toUpperCase() + v.state.slice(1)}
                                </span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}
