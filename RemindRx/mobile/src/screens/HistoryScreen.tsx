/** Adherence over the last 7 days, streak, and the log for a chosen day. */
import React, { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { CheckCircle2, Flame, SkipForward, XCircle } from 'lucide-react-native';
import { adherence, calendarOf, dosesForDay, formatTime, todayISO } from '@shared/index';
import { useStore } from '../state/Store';
import { colors } from '../theme';
import { iconForType } from '../icons';
import { Card, ProgressRing, SectionTitle } from '../components/ui';

const DAY = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export const HistoryScreen: React.FC = () => {
    const insets = useSafeAreaInsets();
    const { meds, doses, now } = useStore();
    const a = useMemo(() => adherence(meds, doses, 7, now), [meds, doses, now]);
    const [sel, setSel] = useState(todayISO(now));
    const dayViews = useMemo(() => dosesForDay(meds, doses, sel, now).filter(v => v.state !== 'upcoming' && v.state !== 'due'), [meds, doses, sel, now]);
    const pctColor = a.pct == null ? colors.primary : a.pct >= 80 ? colors.success : a.pct >= 50 ? colors.accentOrange : colors.accent;

    return (
        <View style={{ flex: 1, backgroundColor: colors.background, paddingTop: insets.top }}>
            <ScrollView contentContainerStyle={{ paddingTop: 12, paddingHorizontal: 18, paddingBottom: 120 }}>
                <Text style={styles.title}>History</Text>

                <View style={styles.statsRow}>
                    <Card style={styles.big}>
                        <ProgressRing size={110} stroke={11} pct={a.pct ?? 0} color={pctColor}>
                            <Text style={[styles.pct, { color: pctColor }]}>{a.pct == null ? '—' : `${a.pct}%`}</Text>
                        </ProgressRing>
                        <Text style={styles.bigLabel}>7-day adherence</Text>
                        <Text style={styles.bigSub}>{a.taken} of {a.scheduled} doses taken</Text>
                    </Card>
                    <Card style={styles.streak}>
                        <View style={styles.flame}><Flame size={26} color={colors.accentOrange} /></View>
                        <Text style={styles.streakNum}>{a.streak}</Text>
                        <Text style={styles.streakLabel}>day streak</Text>
                    </Card>
                </View>

                <SectionTitle>Last 7 days</SectionTitle>
                <Card style={styles.bars}>
                    {a.days.map(d => {
                        const p = d.counted ? d.taken / d.counted : 0;
                        const active = d.dateISO === sel;
                        const color = !d.counted ? colors.border : p === 1 ? colors.success : p >= 0.5 ? colors.accentOrange : colors.accent;
                        return (
                            <Pressable key={d.dateISO} style={styles.barCol} onPress={() => setSel(d.dateISO)} testID={`bar-${d.dateISO}`}>
                                <Text style={styles.barVal}>{d.counted ? `${Math.round(p * 100)}` : '–'}</Text>
                                <View style={styles.barTrack}>
                                    <View style={[styles.barFill, { height: `${Math.max(d.counted ? p * 100 : 0, 6)}%`, backgroundColor: color }]} />
                                </View>
                                <Text style={[styles.barDay, active && styles.barDayActive]}>{DAY[calendarOf(d.dateISO).weekday]}</Text>
                            </Pressable>
                        );
                    })}
                </Card>

                <SectionTitle>{sel === todayISO(now) ? 'Today’s log' : `Log · ${DAY[calendarOf(sel).weekday]} ${calendarOf(sel).dayOfMonth}`}</SectionTitle>
                {dayViews.length === 0 ? (
                    <Text style={styles.empty}>Nothing logged yet for this day.</Text>
                ) : (
                    dayViews.map(v => {
                        const Icon = iconForType(v.med.type);
                        const S = v.state === 'taken' ? CheckCircle2 : v.state === 'skipped' ? SkipForward : XCircle;
                        const c = v.state === 'taken' ? colors.success : v.state === 'skipped' ? colors.textSecondary : colors.accent;
                        return (
                            <Card key={v.id} style={styles.logRow}>
                                <View style={styles.logIcon}><Icon size={18} color={colors.primary} /></View>
                                <View style={{ flex: 1 }}>
                                    <Text style={styles.logName}>{v.med.name}</Text>
                                    <Text style={styles.logMeta}>{formatTime(v.time)} · {v.med.quantityPerDose} {v.med.doseUnit}</Text>
                                </View>
                                <S size={18} color={c} />
                                <Text style={[styles.logState, { color: c }]}>{v.state}</Text>
                            </Card>
                        );
                    })
                )}
            </ScrollView>
        </View>
    );
};

const styles = StyleSheet.create({
    title: { fontSize: 26, fontWeight: '800', color: colors.text },
    statsRow: { flexDirection: 'row', gap: 12, marginTop: 16 },
    big: { flex: 1.4, alignItems: 'center', paddingVertical: 20 },
    pct: { fontSize: 26, fontWeight: '900' },
    bigLabel: { fontSize: 14, fontWeight: '800', color: colors.text, marginTop: 12 },
    bigSub: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
    streak: { flex: 1, alignItems: 'center', justifyContent: 'center' },
    flame: { width: 54, height: 54, borderRadius: 18, backgroundColor: '#FFEDD5', alignItems: 'center', justifyContent: 'center' },
    streakNum: { fontSize: 34, fontWeight: '900', color: colors.text, marginTop: 8 },
    streakLabel: { fontSize: 12, color: colors.textSecondary, fontWeight: '700' },
    bars: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 14 },
    barCol: { alignItems: 'center', flex: 1 },
    barVal: { fontSize: 10, color: colors.textSecondary, fontWeight: '700', marginBottom: 4 },
    barTrack: { width: 18, height: 96, borderRadius: 9, backgroundColor: colors.secondary, justifyContent: 'flex-end', overflow: 'hidden' },
    barFill: { width: '100%', borderRadius: 9 },
    barDay: { fontSize: 11, color: colors.textSecondary, fontWeight: '700', marginTop: 6, paddingHorizontal: 4, borderRadius: 6 },
    barDayActive: { color: '#FFFFFF', backgroundColor: colors.primary, overflow: 'hidden' },
    empty: { color: colors.textSecondary, textAlign: 'center', marginTop: 12 },
    logRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 10, paddingVertical: 12 },
    logIcon: { width: 36, height: 36, borderRadius: 12, backgroundColor: colors.primaryTint, alignItems: 'center', justifyContent: 'center' },
    logName: { fontSize: 15, fontWeight: '800', color: colors.text },
    logMeta: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
    logState: { fontSize: 12, fontWeight: '800', textTransform: 'capitalize', width: 56 },
});
