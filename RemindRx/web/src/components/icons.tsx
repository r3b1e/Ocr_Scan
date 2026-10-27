import { Bath, Brush, Candy, Container, Cookie, Droplet, Droplets, FlaskConical, Leaf, Package, Pill, SprayCan, Syringe, Tablets, TestTube, Wind, type LucideIcon } from 'lucide-react';
import { TYPE_ICON, type IconKey, type MedicationType } from '@shared/index';

const ICONS: Record<IconKey, LucideIcon> = { Pill, Tablets, FlaskConical, Droplets, SprayCan, Container, Droplet, Syringe, Package, Wind, Candy, Leaf, TestTube, Brush, Bath, Cookie };

export const iconFor = (key: IconKey): LucideIcon => ICONS[key] ?? Pill;
export const typeIcon = (type: MedicationType): LucideIcon => iconFor(TYPE_ICON[type]);

/** Soft rounded tile holding a medicine-type icon. */
export function MedIcon({ type, tone = 'primary', size = 44 }: { type: MedicationType; tone?: 'primary' | 'coral' | 'muted'; size?: number }) {
    const Icon = typeIcon(type);
    const cls = tone === 'coral' ? 'bg-coral-tint text-coral-dark' : tone === 'muted' ? 'bg-slate-100 text-muted' : 'bg-primary-tint text-primary-dark';
    return (
        <div className={`grid place-items-center rounded-xl shrink-0 ${cls}`} style={{ width: size, height: size }}>
            <Icon size={size * 0.5} strokeWidth={2} />
        </div>
    );
}
