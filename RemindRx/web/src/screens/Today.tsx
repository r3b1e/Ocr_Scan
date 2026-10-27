import { useMemo, useState } from 'react';
import { AlarmClock, Check, Plus, RotateCcw, SkipForward, Sparkles } from 'lucide-react';
import { addDaysISO, calendarOf, dosesForDay, formatTime, MEAL_RELATIONS, todayISO, type DoseView } from '@shared/index';
import { store, useStore } from '../store';
import { useNow } from '../hooks';
import { clearSnooze, snoozeDose, snoozedUntil } from '../reminders';
import { MedIcon } from '../components/icons';
import { ProgressRing } from '../components/ProgressRing';

const WEEK = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

const greeting = (h: number) => (h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening');

const STATE_STYLE: Record<DoseView['state'], { label: string; cls: string; dot: string }> = {
    upcoming: { label: 'Upcoming', cls: 'bg-slate-100 text-muted', dot: 'bg-slate-300' },
    due: { label: 'Due now', cls: 'bg-coral-tint text-coral-dark', dot: 'bg-coral animate-pulse' },
    missed: { label: 'Missed', cls: 'bg-orange-tint text-orange', dot: 'bg-orange' },
    taken: { label: 'Taken', cls: 'bg-emerald-50 text-emerald-700', dot: 'bg-emerald-500' },
    skipped: { label: 'Skipped', cls: 'bg-slate-100 text-muted', dot: 'bg-slate-400' },
};

export function Today({ onAdd }: { onAdd: () => void }) {
    const { meds, doses, settings } = useStore();
    const now = useNow();
    const today = todayISO(now);
    const [day, setDay] = useState(today);
    const sel = day > addDaysISO(today, 7) || day < addDaysISO(today, -7) ? today : day;

    const views = useMemo(() => dosesForDay(meds, doses, sel, now), [meds, doses, sel, now]);
    const todayViews = useMemo(() => (sel === today ? views : dosesForDay(meds, doses, today, now)), [views, meds, doses, today, sel, now]);
    const taken = todayViews.filter(v => v.state === 'taken').length;
    const next = todayViews.find(v => v.state === 'upcoming' || v.state === 'due');

    const cal = calendarOf(today);
    const weekStart = addDaysISO(today, -cal.weekday);
    const week = Array.from({ length: 7 }, (_, i) => addDaysISO(weekStart, i));
    const [, mo, dd] = today.split('-').map(Number);

    const activeCount = meds.filter(m => m.status === 'active').length;

    return (
        <div className="space-y-5">
            <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-primary via-sky-500 to-primary-dark p-5 text-white shadow-lift">
                <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-white/10" />
                <div className="absolute -right-4 bottom-[-60px] h-40 w-40 rounded-full bg-white/10" />
                <div className="relative flex items-center gap-4">
                    <div className="flex-1 min-w-0">
                        <p className="text-sm text-white/85">{DAYS[cal.weekday]}, {MONTHS[mo - 1]} {dd}</p>
                        <h1 className="mt-0.5 text-2xl font-extrabold leading-tight">
                            {greeting(now.getHours())}{settings.userName ? `, ${settings.userName}` : ''}
                        </h1>
                        <p className="mt-2 text-sm text-white/90">
                            {todayViews.length === 0
                                ? 'Nothing scheduled today.'
                                : next
                                  ? <>Next: <b>{next.med.name}</b> at {formatTime(next.time)}</>
                                  : taken === todayViews.length
                                    ? <span className="inline-flex items-center gap-1"><Sparkles size={14} /> All done for today!</span>
                                    : 'No more doses due today.'}
                        </p>
                    </div>
                    <ProgressRing value={taken} total={todayViews.length} size={104} />
                </div>
            </section>

            <section className="card p-2">
                <div className="grid grid-cols-7 gap-1">
                    {week.map((d, i) => {
                        const isSel = d === sel;
                        const isToday = d === today;
                        const dots = dosesForDay(meds, doses, d, now);
                        const anyMissed = dots.some(v => v.state === 'missed');
                        const allTaken = dots.length > 0 && dots.every(v => v.state === 'taken');
                        return (
                            <button key={d} onClick={() => setDay(d)} className={`flex flex-col items-center rounded-xl py-2 transition ${isSel ? 'bg-primary text-white shadow-lift' : 'hover:bg-ice'}`} aria-pressed={isSel} aria-label={d}>
                                <span className={`text-[11px] font-semibold ${isSel ? 'text-white/80' : 'text-muted'}`}>{WEEK[i]}</span>
                                <span className={`mt-0.5 text-base font-bold ${isToday && !isSel ? 'text-primary' : ''}`}>{Number(d.slice(8))}</span>
                                <span className={`mt-1 h-1.5 w-1.5 rounded-full ${dots.length === 0 ? 'bg-transparent' : allTaken ? (isSel ? 'bg-white' : 'bg-emerald-500') : anyMissed ? 'bg-orange' : isSel ? 'bg-white/70' : 'bg-primary/50'}`} />
                            </button>
                        );
                    })}
                </div>
            </section>

            <section>
                <div className="mb-2 flex items-end justify-between px-1">
                    <h2 className="text-lg font-bold">{sel === today ? "Today's schedule" : sel < today ? 'Past doses' : 'Coming up'}</h2>
                    <span className="text-sm text-muted">{views.length} dose{views.length === 1 ? '' : 's'}</span>
                </div>

                {activeCount === 0 ? (
                    <EmptyState onAdd={onAdd} />
                ) : views.length === 0 ? (
                    <div className="card p-6 text-center text-muted">No doses scheduled on this day.</div>
                ) : (
                    <ol className="relative space-y-3 before:absolute before:left-[27px] before:top-3 before:bottom-3 before:w-px before:bg-line">
                        {views.map(v => (
                            <DoseRow key={v.id} v={v} future={sel > today} />
                        ))}
                    </ol>
                )}
            </section>
        </div>
    );
}

function DoseRow({ v, future }: { v: DoseView; future: boolean }) {
    const st = STATE_STYLE[v.state];
    const meal = MEAL_RELATIONS.find(x => x.value === v.med.mealRelation && x.value !== 'any');
    const [, rerender] = useState(0);
    const snooze = !v.log ? snoozedUntil(v.id) : undefined;
    const snoozing = snooze && snooze > Date.now();
    const inactive = v.med.status !== 'active';
    const urgent = v.state === 'due' || v.state === 'missed';
    const log = (status: 'taken' | 'skipped') => {
        clearSnooze(v.id);
        store.logDose(v, status);
    };
    return (
        <li className="relative flex gap-3" data-testid="dose-row" data-state={v.state}>
            <div className="z-10 flex w-14 shrink-0 flex-col items-center pt-3">
                <span className={`h-3 w-3 rounded-full ring-4 ring-ice ${st.dot}`} />
                <span className="mt-1.5 text-[11px] font-semibold text-muted whitespace-nowrap">{formatTime(v.time)}</span>
            </div>
            <div className={`card flex-1 p-3.5 transition ${urgent ? 'border-coral/40 ring-1 ring-coral/20' : ''} ${inactive ? 'opacity-60' : ''}`}>
                <div className="flex items-start gap-3">
                    <MedIcon type={v.med.type} tone={urgent ? 'coral' : v.state === 'taken' || v.state === 'skipped' ? 'muted' : 'primary'} />
                    <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                            <h3 className={`font-bold leading-tight break-words ${v.state === 'taken' ? 'text-muted line-through decoration-1' : ''}`}>{v.med.name}</h3>
                            <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold ${st.cls}`}>{snoozing ? 'Snoozed' : st.label}</span>
                        </div>
                        <p className="mt-0.5 text-sm text-muted">
                            {v.med.quantityPerDose} {v.med.doseUnit}
                            {meal ? ` · ${meal.label}` : ''}
                            {inactive ? ` · ${v.med.status === 'deleted' ? 'deleted' : 'paused'}` : ''}
                        </p>
                    </div>
                </div>
                {!future && (
                    <div className="mt-3 flex flex-wrap gap-2">
                        {v.log ? (
                            <button className="btn-ghost !py-1.5 text-sm text-muted" onClick={() => store.undoDose(v.id)}>
                                <RotateCcw size={15} /> Undo
                            </button>
                        ) : (
                            <>
                                <button className="btn bg-primary text-white hover:bg-primary-dark px-3.5 py-2 text-sm" onClick={() => log('taken')}>
                                    <Check size={16} /> {v.state === 'upcoming' ? 'Take now' : v.state === 'missed' ? 'Log taken' : 'Taken'}
                                </button>
                                {v.state === 'due' && (
                                    <button className="btn-soft !py-2 text-sm" onClick={() => { snoozeDose(v.id); rerender(n => n + 1); }}>
                                        <AlarmClock size={15} /> Snooze
                                    </button>
                                )}
                                <button className="btn-ghost !py-2 text-sm text-muted" onClick={() => log('skipped')}>
                                    <SkipForward size={15} /> Skip
                                </button>
                            </>
                        )}
                    </div>
                )}
            </div>
        </li>
    );
}

function EmptyState({ onAdd }: { onAdd: () => void }) {
    return (
        <div className="card p-8 text-center">
            <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-primary-tint text-primary-dark">
                <Plus size={30} />
            </div>
            <h3 className="mt-4 text-lg font-bold">Add your first medicine</h3>
            <p className="mx-auto mt-1 max-w-xs text-sm text-muted">Set the dose and times once, and RemindRx will remind you every day.</p>
            <button className="btn-primary mt-5" onClick={onAdd}>
                <Plus size={18} /> Add medication
            </button>
        </div>
    );
}
