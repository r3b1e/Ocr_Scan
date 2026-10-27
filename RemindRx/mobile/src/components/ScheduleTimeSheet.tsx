/**
 * "Schedule Time" sheet for multi-dose courses — one row per required intake
 * (1st, 2nd, 3rd …) showing its time. Tapping a row opens the native Material
 * time picker to edit that slot; edits apply live to the form. The user closes
 * the sheet themselves. (Single-dose courses skip this sheet and open the
 * native picker directly.)
 */
import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { AlarmClock, Pencil } from 'lucide-react-native';
import { useTheme } from '../theme';
import { formatTime } from '@shared/logic';
import { TimeOfDay } from '@shared/types';
import BottomSheet from './BottomSheet';

interface Props {
    visible: boolean;
    times: TimeOfDay[];
    onClose: () => void;
    onEditSlot: (index: number) => void;
}

const ORDINALS = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th'];

export const ScheduleTimeSheet: React.FC<Props> = ({ visible, times, onClose, onEditSlot }) => {
    const { theme } = useTheme();

    return (
        <BottomSheet visible={visible} title="Schedule Time" onClose={onClose} maxHeightRatio={0.7}>
            <Text style={[styles.hint, { color: theme.colors.textSecondary }]}>
                Tap a dose to set its time
            </Text>
            <ScrollView showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="always" contentContainerStyle={{ paddingBottom: 8 }}>
                {times.map((t, i) => (
                    <Pressable
                        key={i}
                        onPress={() => onEditSlot(i)}
                        style={({ pressed }) => [
                            styles.row,
                            {
                                backgroundColor: pressed ? theme.colors.primary + '0A' : theme.colors.background,
                                borderColor: theme.colors.border,
                            },
                        ]}>
                        <View style={[styles.ordBadge, { backgroundColor: theme.colors.primary + '14' }]}>
                            <Text style={{ fontSize: 12, fontWeight: '700', color: theme.colors.primary }}>{ORDINALS[i]}</Text>
                        </View>
                        <Text style={[styles.dose, { color: theme.colors.text }]}>{ORDINALS[i]} dose</Text>
                        <View style={styles.right}>
                            <AlarmClock size={16} color={theme.colors.primary} />
                            <Text style={[styles.time, { color: theme.colors.primary }]}>{formatTime(t)}</Text>
                            <Pencil size={15} color={theme.colors.textSecondary} />
                        </View>
                    </Pressable>
                ))}
            </ScrollView>
        </BottomSheet>
    );
};

const styles = StyleSheet.create({
    hint: { fontSize: 13, fontWeight: '500', marginBottom: 10, paddingHorizontal: 2 },
    row: {
        flexDirection: 'row',
        alignItems: 'center',
        borderRadius: 14,
        borderWidth: 1,
        paddingVertical: 14,
        paddingHorizontal: 14,
        marginBottom: 10,
        gap: 12,
    },
    ordBadge: {
        width: 44,
        height: 30,
        borderRadius: 9,
        alignItems: 'center',
        justifyContent: 'center',
    },
    dose: { flex: 1, fontSize: 15, fontWeight: '600' },
    right: { flexDirection: 'row', alignItems: 'center', gap: 7 },
    time: { fontSize: 15, fontWeight: '700' },
});

export default ScheduleTimeSheet;
