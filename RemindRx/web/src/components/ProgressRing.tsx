export function ProgressRing({ value, total, size = 112 }: { value: number; total: number; size?: number }) {
    const stroke = 10;
    const r = (size - stroke) / 2;
    const c = 2 * Math.PI * r;
    const pct = total ? value / total : 0;
    return (
        <div className="relative shrink-0" style={{ width: size, height: size }}>
            <svg width={size} height={size} className="-rotate-90">
                <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,.25)" strokeWidth={stroke} />
                <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="white" strokeWidth={stroke} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - pct)} style={{ transition: 'stroke-dashoffset .6s cubic-bezier(.2,.8,.2,1)' }} />
            </svg>
            <div className="absolute inset-0 grid place-items-center text-white text-center">
                <div>
                    <div className="text-2xl font-extrabold leading-none">{value}/{total}</div>
                    <div className="text-[11px] font-medium opacity-90 mt-1">doses taken</div>
                </div>
            </div>
        </div>
    );
}
