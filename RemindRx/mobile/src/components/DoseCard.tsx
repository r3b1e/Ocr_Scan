/** One dose on the Today timeline, with its actions. */
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { AlarmClock, BellRing, Check, Clock, SkipForward, Undo2 } from 'lucide-react-native';
import { DoseView, MEAL_RELATIONS, formatTime } from '@shared/index';
import { colors } from '../theme';
import { iconForType } from '../icons';
import { Pill, PressScale } from './ui';

const STATE: Record<DoseView['state'], { label: string; fg: string; bg: string }> = {
    upcoming: { label: 'UPCOMING', fg: colors.primaryDark, bg: colors.primaryTint },
    due: { label: 'DUE NOW', fg: '#FFFFFF', bg: colors.accentOrange },
    taken: { label: 'TAKEN', fg: '#047857', bg: colors.successTint },
    skipped: { label: 'SKIPPED', fg: colors.textSecondary, bg: colors.secondary },
    missed: { label: 'MISSED', fg: '#FFFFFF', bg: colors.accent },
};

const timeOf = (iso?: string) => {
    if (!iso) return '';
    const d = new Date(iso);
    return formatTime({ hour: d.getHours(), minute: d.getMinutes() });
};

interface Props {
    view: DoseView;
    actionable: boolean;
    onTake(): void;
    onSkip(): void;
    onSnooze(): void;
    onUndo(): void;
}

export const DoseCard: React.FC<Props> = ({ view, actionable, onTake, onSkip, onSnooze, onUndo }) => {
    const { med, state } = view;
    const Icon = iconForType(med.type);
    const s = STATE[state];
    const urgent = state === 'due' || state === 'missed';
    const meal = MEAL_RELATIONS.find(m => m.value === med.mealRelation && m.value !== 'any')?.label;
    const done = state === 'taken' || state === 'skipped';

    return (
        <View style={styles.row} testID={`dose-${med.name}-${view.slot}`}>
            <View style={styles.timeCol}>
                <Text style={[styles.time, urgent && { color: colors.accent }]}>{formatTime(view.time).replace(' ', '\n')}</Text>
                <View style={[styles.dot, { backgroundColor: done ? colors.success : urgent ? colors.accent : colors.primary }]} />
            </View>
            <View style={[styles.card, urgent && styles.cardUrgent, done && styles.cardDone]}>
                <View style={styles.top}>
                    <View style={[styles.icon, { backgroundColor: urgent ? colors.accentTint : colors.primaryTint }]}>
                        <Icon size={22} color={urgent ? colors.accent : colors.primary} strokeWidth={2} />
                    </View>
                    <View style={{ flex: 1 }}>
                        <Text style={[styles.name, done && { color: colors.textSecondary }]} numberOfLines={1}>{med.name}</Text>
                        <Text style={styles.meta} numberOfLines={1}>
                            {med.quantityPerDose} {med.doseUnit}{meal ? ` · ${meal}` : ''}
                        </Text>
                    </View>
                    <Pill label={s.label} fg={s.fg} bg={s.bg} />
                </View>

                <View style={styles.bottom}>
                    <View style={styles.modeRow}>
                        {med.reminderMode === 'alarm' ? <BellRing size={13} color={colors.textSecondary} /> : <Clock size={13} color={colors.textSecondary} />}
                        <Text style={styles.modeText}>
                            {done ? `${state === 'taken' ? 'Taken' : 'Skipped'} at ${timeOf(view.log?.at)}` : med.reminderMode === 'alarm' ? 'Alarm' : 'Notification'}
                        </Text>
                    </View>
                    {actionable && !done && (
                        <View style={styles.actions}>
                            {state !== 'missed' && (
                                <Pressable onPress={onSnooze} style={styles.ghost} hitSlop={6} testID="snooze">
                                    <AlarmClock size={16} color={colors.textSecondary} />
                                </Pressable>
                            )}
                            <Pressable onPress={onSkip} style={styles.ghost} hitSlop={6} testID="skip">
                                <SkipForward size={16} color={colors.textSecondary} />
                            </Pressable>
                            <PressScale onPress={onTake} style={[styles.take, urgent && { backgroundColor: colors.accent }]} testID="take">
                                <Check size={16} color="#FFFFFF" strokeWidth={3} />
                                <Text style={styles.takeText}>Take</Text>
                            </PressScale>
                        </View>
                    )}
                    {actionable && done && (
                        <Pressable onPress={onUndo} style={styles.undo} hitSlop={6} testID="undo">
                            <Undo2 size={14} color={colors.primaryDark} />
                            <Text style={styles.undoText}>Undo</Text>
                        </Pressable>
                    )}
                </View>
            </View>
        </View>
    );
};

const styles = StyleSheet.create({
    row: { flexDirection: 'row', gap: 10, marginBottom: 12 },
    timeCol: { width: 52, alignItems: 'center', paddingTop: 14 },
    time: { fontSize: 13, fontWeight: '800', color: colors.text, textAlign: 'center', lineHeight: 16 },
    dot: { width: 8, height: 8, borderRadius: 4, marginTop: 8 },
    card: { flex: 1, backgroundColor: colors.surface, borderRadius: 18, padding: 14, borderWidth: 1, borderColor: colors.border },
    cardUrgent: { borderColor: '#FDA4AF', backgroundColor: '#FFF7F8' },
    cardDone: { opacity: 0.85 },
    top: { flexDirection: 'row', alignItems: 'center', gap: 12 },
    icon: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
    name: { fontSize: 16, fontWeight: '800', color: colors.text },
    meta: { fontSize: 13, color: colors.textSecondary, marginTop: 2 },
    bottom: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 12 },
    modeRow: { flexDirection: 'row', alignItems: 'center', gap: 5 },
    modeText: { fontSize: 12, color: colors.textSecondary, fontWeight: '600' },
    actions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
    ghost: { width: 36, height: 36, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' },
    take: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: colors.primary, paddingHorizontal: 16, height: 36, borderRadius: 12 },
    takeText: { color: '#FFFFFF', fontWeight: '800', fontSize: 14 },
    undo: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 10, backgroundColor: colors.primaryTint },
    undoText: { color: colors.primaryDark, fontWeight: '800', fontSize: 12 },
});
