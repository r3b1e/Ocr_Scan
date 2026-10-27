import { AlarmClock, BellRing, Check, SkipForward } from 'lucide-react';
import { formatTime, MEAL_RELATIONS } from '@shared/index';
import type { ActiveAlert } from '../reminders';
import { typeIcon } from './icons';

export function AlarmModal({ alert, queued, onTaken, onSkip, onSnooze, onDismiss }: { alert: ActiveAlert; queued: number; onTaken: () => void; onSkip: () => void; onSnooze: () => void; onDismiss: () => void }) {
    const m = alert.view.med;
    const Icon = typeIcon(m.type);
    const early = alert.kind === 'early';
    const meal = MEAL_RELATIONS.find(x => x.value === m.mealRelation && x.value !== 'any');
    const mins = Math.max(0, Math.round((alert.view.scheduledAt.getTime() - Date.now()) / 60_000));
    return (
        <div className="fixed inset-0 z-[60] grid place-items-center p-4" role="alertdialog" aria-modal="true" aria-label={`Reminder: ${m.name}`}>
            <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm animate-fade-in" />
            <div className="relative w-full max-w-sm overflow-hidden rounded-3xl bg-white shadow-2xl animate-pop-in">
                <div className={`px-6 pt-7 pb-6 text-center text-white ${early ? 'bg-gradient-to-br from-primary to-primary-dark' : 'bg-gradient-to-br from-coral to-orange'}`}>
                    <div className="mx-auto grid h-20 w-20 place-items-center rounded-full bg-white/20 animate-pulse2">
                        <Icon size={38} className={early ? '' : 'animate-ring'} />
                    </div>
                    <div className="mt-4 text-sm font-semibold uppercase tracking-widest opacity-90 flex items-center justify-center gap-1.5">
                        {early ? <AlarmClock size={14} /> : <BellRing size={14} />}
                        {early ? `Coming up in ${mins} min` : alert.kind === 'snooze' ? 'Snoozed reminder' : 'Time for your medicine'}
                    </div>
                    <h2 className="mt-1 text-3xl font-extrabold break-words">{m.name}</h2>
                    <p className="mt-1 text-white/90">
                        {m.quantityPerDose} {m.doseUnit} · {formatTime(alert.view.time)}
                    </p>
                    {meal && <span className="mt-3 inline-block rounded-full bg-white/20 px-3 py-1 text-xs font-semibold">{meal.label}</span>}
                </div>
                <div className="p-4 grid gap-2.5">
                    <button className="btn-primary w-full !py-3.5 text-base" onClick={onTaken} autoFocus>
                        <Check size={20} /> {early ? 'Taken early' : 'Taken'}
                    </button>
                    {early ? (
                        <button className="btn-soft w-full !py-3" onClick={onDismiss}>Got it</button>
                    ) : (
                        <div className="grid grid-cols-2 gap-2.5">
                            <button className="btn-soft !py-3 whitespace-nowrap text-sm" onClick={onSnooze}>
                                <AlarmClock size={17} /> Snooze 10 min
                            </button>
                            <button className="btn !py-3 text-sm bg-slate-100 text-ink hover:bg-slate-200" onClick={onSkip}>
                                <SkipForward size={18} /> Skip
                            </button>
                        </div>
                    )}
                    {queued > 0 && <p className="text-center text-xs text-muted">+{queued} more reminder{queued > 1 ? 's' : ''} waiting</p>}
                </div>
            </div>
        </div>
    );
}
