import { createNavigationContainerRef } from '@react-navigation/native';
import type { Medication } from '@shared/index';
import type { MedData } from './reminders/ReminderService';

export type RootStackParamList = {
    Tabs: undefined;
    AddMedication: { medication?: Medication } | undefined;
    Alarm: MedData;
};

export const navigationRef = createNavigationContainerRef<RootStackParamList>();

/** Show the ringer for an alarm, unless one is already up. */
export const openAlarm = (data: MedData) => {
    if (!navigationRef.isReady()) return false;
    if (navigationRef.getCurrentRoute()?.name === 'Alarm') return true;
    navigationRef.navigate('Alarm', data);
    return true;
};
