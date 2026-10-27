/** All medicines grouped by Active / Paused / Finished, with quick pause/resume. */
import React, { useMemo } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { BellOff, BellRing, Bell, ChevronRight, Pause, Play, Plus } from 'lucide-react-native';
import { Medication, MedicationStatus, formatTime, frequencySummary, parseISODateLocal, formatDateShort, todayISO } from '@shared/index';
import { useStore } from '../state/Store';
import { colors } from '../theme';
import { iconForType } from '../icons';
import { Card, PressScale, SectionTitle, useToast } from '../components/ui';

export const MedicationsScreen: React.FC = () => {
    const insets = useSafeAreaInsets();
    const nav = useNavigation<any>();
    const store = useStore();
    const toast = useToast();
    const today = todayISO(store.now);

    const groups = useMemo(() => {
        const live = store.meds.filter(m => m.status !== MedicationStatus.Deleted);
        const finished = (m: Medication) => m.endDate.slice(0, 10) < today || m.status === MedicationStatus.Completed;
        return [
            { title: 'Active', items: live.filter(m => m.status === MedicationStatus.Active && !finished(m)) },
            { title: 'Paused', items: live.filter(m => m.status === MedicationStatus.Paused && !finished(m)) },
            { title: 'Finished', items: live.filter(finished) },
        ].filter(g => g.items.length);
    }, [store.meds, today]);

    const toggle = async (m: Medication) => {
        const next = m.status === MedicationStatus.Paused ? MedicationStatus.Active : MedicationStatus.Paused;
        await store.setStatus(m.id, next);
        toast.show(next === MedicationStatus.Paused ? `${m.name} paused: no reminders` : `${m.name} resumed`);
    };

    return (
        <View style={{ flex: 1, backgroundColor: colors.background, paddingTop: insets.top }}>
            <ScrollView contentContainerStyle={{ paddingTop: 12, paddingHorizontal: 18, paddingBottom: 120 }}>
                <View style={styles.header}>
                    <Text style={styles.title}>Medications</Text>
                    <PressScale onPress={() => nav.navigate('AddMedication')} style={styles.add} testID="meds-add">
                        <Plus size={18} color="#FFFFFF" strokeWidth={3} />
                        <Text style={styles.addText}>Add</Text>
                    </PressScale>
                </View>

                {groups.length === 0 && <Text style={styles.empty}>No medicines yet. Tap Add to set one up.</Text>}

                {groups.map(g => (
                    <View key={g.title}>
                        <SectionTitle>{`${g.title} · ${g.items.length}`}</SectionTitle>
                        {g.items.map(m => {
                            const Icon = iconForType(m.type);
                            const paused = m.status === MedicationStatus.Paused;
                            const ModeIcon = !m.remindersEnabled ? BellOff : m.reminderMode === 'alarm' ? BellRing : Bell;
                            return (
                                <PressScale key={m.id} onPress={() => nav.navigate('AddMedication', { medication: m })} style={{ marginBottom: 12 }} testID={`med-${m.name}`}>
                                    <Card style={[styles.card, paused && { opacity: 0.7 }] as any}>
                                        <View style={[styles.icon, { backgroundColor: paused ? colors.secondary : colors.primaryTint }]}>
                                            <Icon size={24} color={paused ? colors.textSecondary : colors.primary} />
                                        </View>
                                        <View style={{ flex: 1 }}>
                                            <Text style={styles.name} numberOfLines={1}>{m.name}</Text>
                                            <Text style={styles.meta} numberOfLines={1}>{m.quantityPerDose} {m.doseUnit} · {frequencySummary(m.frequencyType, m.frequencyConfig)}</Text>
                                            <View style={styles.timesRow}>
                                                <ModeIcon size={12} color={colors.textSecondary} />
                                                <Text style={styles.times} numberOfLines={1}>{m.scheduleTimes.map(formatTime).join(' · ')}</Text>
                                            </View>
                                            <Text style={styles.until}>Until {formatDateShort(parseISODateLocal(m.endDate))}</Text>
                                        </View>
                                        {g.title !== 'Finished' ? (
                                            <Pressable onPress={() => toggle(m)} hitSlop={8} style={styles.toggle} testID={`toggle-${m.name}`}>
                                                {paused ? <Play size={16} color={colors.primary} /> : <Pause size={16} color={colors.textSecondary} />}
                                            </Pressable>
                                        ) : (
                                            <ChevronRight size={18} color={colors.textSecondary} />
                                        )}
                                    </Card>
                                </PressScale>
                            );
                        })}
                    </View>
                ))}
            </ScrollView>
            {toast.node}
        </View>
    );
};

const styles = StyleSheet.create({
    header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    title: { fontSize: 26, fontWeight: '800', color: colors.text },
    add: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: colors.primary, paddingHorizontal: 14, paddingVertical: 9, borderRadius: 14 },
    addText: { color: '#FFFFFF', fontWeight: '800' },
    empty: { color: colors.textSecondary, marginTop: 40, textAlign: 'center' },
    card: { flexDirection: 'row', alignItems: 'center', gap: 14 },
    icon: { width: 50, height: 50, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
    name: { fontSize: 16, fontWeight: '800', color: colors.text },
    meta: { fontSize: 13, color: colors.textSecondary, marginTop: 2 },
    timesRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 6 },
    times: { fontSize: 12, color: colors.primaryDark, fontWeight: '700', flexShrink: 1 },
    until: { fontSize: 11, color: colors.textSecondary, marginTop: 3 },
    toggle: { width: 38, height: 38, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' },
});
