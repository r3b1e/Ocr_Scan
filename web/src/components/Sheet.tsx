import { useEffect, type ReactNode } from 'react';
import { X } from 'lucide-react';

/** Bottom sheet on phones, centered dialog on wider screens. */
export function Sheet({ open, title, onClose, children, footer }: { open: boolean; title: string; onClose: () => void; children: ReactNode; footer?: ReactNode }) {
    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [open, onClose]);
    if (!open) return null;
    return (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center" role="dialog" aria-modal="true" aria-label={title}>
            <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-[2px] animate-fade-in" onClick={onClose} />
            <div className="relative w-full sm:max-w-md max-h-[85vh] flex flex-col bg-white rounded-t-3xl sm:rounded-3xl shadow-2xl animate-sheet-up sm:animate-pop-in">
                <div className="sm:hidden mx-auto mt-2.5 h-1.5 w-10 rounded-full bg-slate-200" />
                <div className="flex items-center justify-between px-5 pt-3 pb-2">
                    <h3 className="text-lg font-bold">{title}</h3>
                    <button className="btn-ghost !p-2 rounded-full" onClick={onClose} aria-label="Close">
                        <X size={20} />
                    </button>
                </div>
                <div className="overflow-y-auto px-5 pb-4">{children}</div>
                {footer && <div className="px-5 pb-5 pt-2 border-t border-line">{footer}</div>}
            </div>
        </div>
    );
}
