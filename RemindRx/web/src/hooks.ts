import { useEffect, useState } from 'react';

/** Current time, refreshed every `ms` and whenever the tab becomes visible. */
export function useNow(ms = 15_000): Date {
    const [now, setNow] = useState(() => new Date());
    useEffect(() => {
        const tick = () => setNow(new Date());
        const id = window.setInterval(tick, ms);
        document.addEventListener('visibilitychange', tick);
        return () => {
            window.clearInterval(id);
            document.removeEventListener('visibilitychange', tick);
        };
    }, [ms]);
    return now;
}
