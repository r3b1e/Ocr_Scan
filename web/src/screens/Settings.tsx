import { useRef, useState } from 'react';
import { BellRing, Download, HardDrive, ShieldCheck, Trash2, Upload, User } from 'lucide-react';
import { backupFileName, makeBackup, mergeBackup, parseBackup, type BackupFile } from '@shared/index';
import { store, useStore } from '../store';
import { notifyPermission, requestNotifyPermission, type NotifyPermission } from '../reminders';
import { Sheet } from '../components/Sheet';

export function Settings() {
    const { meds, doses, settings, storageOk } = useStore();
    const [perm, setPerm] = useState<NotifyPermission>(notifyPermission());
    const [pending, setPending] = useState<BackupFile | null>(null);
    const [msg, setMsg] = useState<{ tone: 'ok' | 'err'; text: string } | null>(null);
    const fileRef = useRef<HTMLInputElement>(null);

    const exportData = () => {
        const blob = new Blob([JSON.stringify(makeBackup({ meds, doses, settings }), null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = backupFileName();
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        setMsg({ tone: 'ok', text: 'Backup downloaded.' });
    };

    const onFile = async (f: File | undefined) => {
        if (!f) return;
        const r = parseBackup(await f.text());
        if (fileRef.current) fileRef.current.value = '';
        if (!r.ok) return setMsg({ tone: 'err', text: r.error });
        setMsg(null);
        setPending(r.data);
    };

    const applyImport = (mode: 'merge' | 'replace') => {
        if (!pending) return;
        store.replaceAll(mergeBackup({ meds, doses, settings }, pending, mode));
        setMsg({ tone: 'ok', text: `Imported ${pending.meds.length} medication${pending.meds.length === 1 ? '' : 's'} and ${pending.doses.length} dose record${pending.doses.length === 1 ? '' : 's'}.` });
        setPending(null);
    };

    const permLabel: Record<NotifyPermission, string> = { granted: 'Allowed', denied: 'Blocked in browser settings', default: 'Not asked yet', unsupported: 'Not supported in this browser' };

    return (
        <div className="space-y-4">
            <h1 className="text-2xl font-extrabold">Settings</h1>

            <section className="card p-4">
                <label className="label flex items-center gap-1.5" htmlFor="name"><User size={14} /> Your name</label>
                <input id="name" className="input mt-2" placeholder="Used in your greeting" value={settings.userName ?? ''} onChange={e => store.setSettings({ userName: e.target.value })} />
            </section>

            <section className="card p-4">
                <div className="flex items-center gap-3">
                    <div className="grid h-10 w-10 place-items-center rounded-xl bg-coral-tint text-coral-dark"><BellRing size={20} /></div>
                    <div className="flex-1">
                        <div className="font-semibold">System notifications</div>
                        <div className={`text-sm ${perm === 'granted' ? 'text-emerald-600' : perm === 'denied' ? 'text-coral-dark' : 'text-muted'}`} data-testid="notify-status">{permLabel[perm]}</div>
                    </div>
                    {perm === 'default' && <button className="btn-primary !py-2" onClick={async () => setPerm(await requestNotifyPermission())}>Allow</button>}
                </div>
                <p className="mt-3 text-xs text-muted leading-relaxed">Reminders ring inside RemindRx while it is open in this browser (tab or installed app). Notifications show even when the tab is in the background. For reminders when your browser is closed, use the RemindRx mobile app.</p>
            </section>

            <section className="card divide-y divide-line">
                <div className="p-4">
                    <div className="font-semibold flex items-center gap-2"><HardDrive size={18} className="text-primary" /> Backup</div>
                    <p className="mt-1 text-sm text-muted">Your data stays on this device. Export a file to keep a copy or move it to your phone.</p>
                    <div className="mt-3 grid grid-cols-2 gap-2">
                        <button className="btn-soft !py-2.5" onClick={exportData}><Download size={17} /> Export</button>
                        <button className="btn-soft !py-2.5" onClick={() => fileRef.current?.click()}><Upload size={17} /> Import</button>
                        <input ref={fileRef} type="file" accept="application/json,.json" className="hidden" onChange={e => void onFile(e.target.files?.[0])} data-testid="import-input" />
                    </div>
                    {msg && <p className={`mt-3 text-sm ${msg.tone === 'ok' ? 'text-emerald-700' : 'text-coral-dark'}`} role="status">{msg.text}</p>}
                </div>
                <div className="p-4">
                    <button
                        className="btn w-full py-2.5 text-coral-dark hover:bg-coral-tint"
                        onClick={() => {
                            if (!confirm('Erase every medication and dose record from this browser? Export a backup first if you want to keep them.')) return;
                            store.wipe();
                            setMsg({ tone: 'ok', text: 'All data erased.' });
                        }}
                    >
                        <Trash2 size={17} /> Erase all data
                    </button>
                </div>
            </section>

            <section className="flex items-start gap-3 px-1 text-xs text-muted">
                <ShieldCheck size={16} className="mt-0.5 shrink-0 text-primary" />
                <p>RemindRx has no account and no server. Nothing you enter leaves this {storageOk ? 'browser' : 'tab — storage is blocked, so data is lost when you close it'}. {meds.length} medication{meds.length === 1 ? '' : 's'}, {doses.length} dose record{doses.length === 1 ? '' : 's'} stored.</p>
            </section>

            <Sheet
                open={!!pending}
                title="Import backup"
                onClose={() => setPending(null)}
                footer={
                    <div className="grid grid-cols-2 gap-2">
                        <button className="btn-soft !py-3" onClick={() => applyImport('merge')}>Merge</button>
                        <button className="btn-coral !py-3" onClick={() => applyImport('replace')}>Replace</button>
                    </div>
                }
            >
                {pending && (
                    <div className="space-y-2 text-sm">
                        <p>This file has <b>{pending.meds.length}</b> medication{pending.meds.length === 1 ? '' : 's'} and <b>{pending.doses.length}</b> dose record{pending.doses.length === 1 ? '' : 's'}{pending.exportedAt ? <>, exported {new Date(pending.exportedAt).toLocaleString()}</> : null}.</p>
                        <p className="text-muted"><b>Merge</b> keeps what's here and adds the file's records (the file wins on duplicates). <b>Replace</b> erases this browser's data first.</p>
                    </div>
                )}
            </Sheet>
        </div>
    );
}
