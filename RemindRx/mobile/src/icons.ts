import {
    Bath, Brush, Candy, Container, Cookie, Droplet, Droplets, FlaskConical, Leaf,
    Package, Pill, SprayCan, Syringe, Tablets, TestTube, Wind,
} from 'lucide-react-native';
import { IconKey, MedicationType, TYPE_ICON } from '@shared/index';

export const ICONS: Record<IconKey, React.ComponentType<any>> = {
    Bath, Brush, Candy, Container, Cookie, Droplet, Droplets, FlaskConical, Leaf,
    Package, Pill, SprayCan, Syringe, Tablets, TestTube, Wind,
};

export const iconForType = (type: MedicationType): React.ComponentType<any> => ICONS[TYPE_ICON[type]] ?? Pill;
