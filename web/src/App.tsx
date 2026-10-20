import { useEffect, useState } from 'react';
import { CalendarCheck, ChartColumn, Pill, Plus, ScanLine, Settings as Cog } from 'lucide-react';
import type { Medication, MedicationDraft } from '@shared/index';
import { store, useStore } from './store';
import { clearSnooze, snoozeDose, useReminderEngine } from './reminders';
import { unlockAudio } from './sound';
import { Today } from './screens/Today';
import { Medications } from './screens/Medications';
import { History } from './screens/History';
import { Settings } from './screens/Settings';
import { MedForm } from './screens/MedForm';
import { ScanPrescription } from './screens/ScanPrescription';
import { AlarmModal } from './components/AlarmModal';
import { Banner } from './components/Banner';

type Tab = 'today' | 'meds' | 'scan' | 'history' | 'settings';
const TABS: { key: Tab; label: string; Icon: typeof Pill }[] = [
    { key: 'today', label: 'Today', Icon: CalendarCheck },
    { key: 'meds', label: 'Medications', Icon: Pill },
    { key: 'scan', label: 'Scan', Icon: ScanLine },
    { key: 'history', label: 'History', Icon: ChartColumn },
    { key: 'settings', label: 'Settings', Icon: Cog },
];

function Logo() {
    return (
        <div className="flex items-center gap-2.5">
            <img src="/icon.svg" alt="" className="h-9 w-9 rounded-xl shadow-lift" />
            <div className="leading-tight">
                <div className="text-lg font-extrabold tracking-tight">Remind<span className="text-primary">Rx</span></div>
                <div className="text-[11px] font-medium text-muted">Private · on-device</div>
            </div>
        </div>
    );
}

export default function App() {
    const { storageOk } = useStore();
    const [tab, setTab] = useState<Tab>('today');
    const [form, setForm] = useState<{ med?: Medication; initial?: MedicationDraft; onSaved?: () => void } | null>(null);
    const { alerts, dismiss } = useReminderEngine();

    useEffect(() => unlockAudio(), []);

    const head = alerts[0];
    const openAdd = () => setForm({});
    const openFromScan = (initial: MedicationDraft, onSaved: () => void) => setForm({ initial, onSaved });

    return (
        <div className="min-h-full lg:flex">
            <aside className="hidden lg:flex lg:w-64 lg:flex-col lg:gap-6 lg:border-r lg:border-line lg:bg-white lg:px-4 lg:py-6 lg:sticky lg:top-0 lg:h-screen">
                <Logo />
                <button className="btn-primary" onClick={openAdd}><Plus size={18} /> Add medication</button>
                <button className="btn-soft -mt-3" onClick={() => setTab('scan')}><ScanLine size={18} /> Scan prescription</button>
                <nav className="flex flex-col gap-1">
                    {TABS.map(t => (
                        <button key={t.key} onClick={() => setTab(t.key)} className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] font-semibold transition ${tab === t.key ? 'bg-primary-tint text-primary-dark' : 'text-muted hover:bg-ice hover:text-ink'}`} aria-current={tab === t.key ? 'page' : undefined}>
                            <t.Icon size={20} /> {t.label}
                        </button>
                    ))}
                </nav>
            </aside>

            <div className="flex-1 min-w-0">
                <header className="lg:hidden sticky top-0 z-30 flex items-center justify-between bg-ice/85 backdrop-blur px-4 py-3">
                    <Logo />
                </header>
                <main className="mx-auto max-w-2xl px-4 pb-28 pt-2 lg:pt-8 lg:pb-12 space-y-4">
                    {!storageOk && <Banner tone="warn">This browser is blocking storage (private window?). RemindRx works, but your data disappears when you close the tab.</Banner>}
                    <Banner>Reminders ring only while RemindRx is open in this browser — keep it open, or use the mobile app.</Banner>
                    <div key={tab} className="animate-fade-in">
                        {tab === 'today' && <Today onAdd={openAdd} />}
                        {tab === 'meds' && <Medications onAdd={openAdd} onEdit={med => setForm({ med })} />}
                        {tab === 'scan' && <ScanPrescription onAddMedication={openFromScan} />}
                        {tab === 'history' && <History />}
                        {tab === 'settings' && <Settings />}
                    </div>
                </main>
            </div>

            {(tab === 'today' || tab === 'meds') && (
                <button className="lg:hidden fixed right-4 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-30 grid h-14 w-14 place-items-center rounded-2xl bg-primary text-white shadow-lift transition active:scale-90" onClick={openAdd} aria-label="Add medication">
                    <Plus size={26} />
                </button>
            )}

            <nav className="lg:hidden fixed inset-x-0 bottom-0 z-30 border-t border-line bg-white/95 backdrop-blur pb-[env(safe-area-inset-bottom)]">
                <div className="mx-auto grid max-w-2xl grid-cols-5">
                    {TABS.map(t => {
                        const on = tab === t.key;
                        return (
                            <button key={t.key} onClick={() => setTab(t.key)} className={`flex flex-col items-center gap-0.5 py-2.5 text-[11px] font-semibold transition ${on ? 'text-primary' : 'text-muted'}`} aria-current={on ? 'page' : undefined}>
                                <span className={`grid h-8 w-14 place-items-center rounded-full transition ${on ? 'bg-primary-tint' : ''}`}><t.Icon size={21} /></span>
                                {t.label}
                            </button>
                        );
                    })}
                </div>
            </nav>

            {form && <MedForm med={form.med} initial={form.initial} onSaved={form.onSaved} onClose={() => setForm(null)} />}

            {head && (
                <AlarmModal
                    alert={head}
                    queued={alerts.length - 1}
                    onTaken={() => { clearSnooze(head.view.id); store.logDose(head.view, 'taken'); dismiss(head.view.id); }}
                    onSkip={() => { clearSnooze(head.view.id); store.logDose(head.view, 'skipped'); dismiss(head.view.id); }}
                    onSnooze={() => { snoozeDose(head.view.id); dismiss(head.view.id); }}
                    onDismiss={() => dismiss(head.view.id)}
                />
            )}
        </div>
    );
}
