import type { ReactNode } from 'react';
import { Info, TriangleAlert } from 'lucide-react';

export function Banner({ tone = 'info', children, action }: { tone?: 'info' | 'warn'; children: ReactNode; action?: ReactNode }) {
    const warn = tone === 'warn';
    const Icon = warn ? TriangleAlert : Info;
    return (
        <div className={`flex items-start gap-2.5 rounded-xl px-3.5 py-2.5 text-[13px] leading-snug ${warn ? 'bg-orange-tint text-orange-900' : 'bg-primary-tint/70 text-sky-900'}`}>
            <Icon size={16} className={`mt-0.5 shrink-0 ${warn ? 'text-orange' : 'text-primary-dark'}`} />
            <div className="flex-1">{children}</div>
            {action}
        </div>
    );
}
