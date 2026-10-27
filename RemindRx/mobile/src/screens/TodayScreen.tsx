/** Today: week strip, progress, reminder health and the dose timeline. */
import React, { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Plus, Pill as PillIcon, Sparkles } from 'lucide-react-native';
import { DoseView, addDaysISO, calendarOf, deviceTimeZone, dosesForDay, formatTime, todayISO } from '@shared/index';
import { useStore } from '../state/Store';
import { colors } from '../theme';
import { DoseCard } from '../components/DoseCard';
import { HealthCard } from '../components/HealthCard';
import { PressScale, ProgressRing, SectionTitle, useToast } from '../components/ui';

const DAY = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

const greeting = (h: number) => (h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening');
const partOfDay = (h: number) => (h < 12 ? 'Morning' : h < 17 ? 'Afternoon' : h < 21 ? 'Evening' : 'Night');

export const TodayScreen: React.FC = () => {
    const insets = useSafeAreaInsets();
    const nav = useNavigation<any>();
    const store = useStore();
    const { meds, doses, settings, now } = store;
    const toast = useToast();
    const tz = deviceTimeZone();
    const today = todayISO(now, tz);
    const [selected, setSelected] = useState(today);

    // Week strip: today in the middle-ish, 3 days back, 3 forward.
    const week = useMemo(() => Array.from({ length: 7 }, (_, i) => addDaysISO(today, i - 3)), [today]);
    const views = useMemo(() => dosesForDay(meds, doses, selected, now, tz), [meds, doses, selected, now, tz]);
    const todayViews = useMemo(() => (selected === today ? views : dosesForDay(meds, doses, today, now, tz)), [selected, today, views, meds, doses, now, tz]);

    const taken = todayViews.filter(v => v.state === 'taken').length;
    const total = todayViews.length;
    const next = todayViews.find(v => v.state === 'upcoming' || v.state === 'due');
    const missed = todayViews.filter(v => v.state === 'missed').length;

    const groups = useMemo(() => {
        const out: { title: string; items: DoseView[] }[] = [];
        for (const v of views) {
            const t = partOfDay(v.time.hour);
            const g = out.find(x => x.title === t);
            g ? g.items.push(v) : out.push({ title: t, items: [v] });
        }
        return out;
    }, [views]);

    const cal = calendarOf(selected);
    const [y, m] = selected.split('-').map(Number);
    const actionable = selected <= today;
    const activeCount = meds.filter(x => x.status === 'active').length;

    const take = async (v: DoseView) => {
        await store.logDose(v, 'taken');
        toast.show(`${v.med.name} marked as taken`, { label: 'UNDO', run: () => store.undoDose(v) });
    };
    const skip = async (v: DoseView) => {
        await store.logDose(v, 'skipped');
        toast.show(`${v.med.name} skipped`, { label: 'UNDO', run: () => store.undoDose(v) });
    };
    const snooze = async (v: DoseView) => {
        await store.snoozeDose(v);
        toast.show(`Snoozed: we’ll remind you in 10 min`);
    };

    return (
        <View style={{ flex: 1, backgroundColor: colors.background, paddingTop: insets.top }}>
            <ScrollView contentContainerStyle={{ paddingTop: 12, paddingHorizontal: 18, paddingBottom: 120 }} showsVerticalScrollIndicator={false}>
                <View style={styles.header}>
                    <View style={{ flex: 1 }}>
                        <Text style={styles.hello}>{greeting(now.getHours())}{settings.userName ? `, ${settings.userName}` : ''}</Text>
                        <Text style={styles.date}>{WEEKDAYS[calendarOf(today).weekday]}, {calendarOf(today).dayOfMonth} {MONTHS[Number(today.slice(5, 7)) - 1]}</Text>
                    </View>
                    <View style={styles.brand}>
                        <PillIcon size={16} color="#FFFFFF" />
                        <Text style={styles.brandText}>RemindRx</Text>
                    </View>
                </View>

                {/* Week strip */}
                <View style={styles.week}>
                    {week.map(d => {
                        const c = calendarOf(d);
                        const sel = d === selected;
                        const isToday = d === today;
                        return (
                            <Pressable key={d} onPress={() => setSelected(d)} style={[styles.day, sel && styles.daySel]} testID={`day-${d}`}>
                                <Text style={[styles.dayLetter, sel && { color: '#E0F2FE' }]}>{DAY[c.weekday]}</Text>
                                <Text style={[styles.dayNum, sel && { color: '#FFFFFF' }]}>{c.dayOfMonth}</Text>
                                <View style={[styles.todayDot, { backgroundColor: isToday ? (sel ? '#FFFFFF' : colors.primary) : 'transparent' }]} />
                            </Pressable>
                        );
                    })}
                </View>

                {/* Summary */}
                <View style={styles.hero}>
                    <ProgressRing size={96} stroke={10} pct={total ? (taken / total) * 100 : 0} color="#FFFFFF" track="rgba(255,255,255,0.25)">
                        <Text style={styles.ringNum}>{taken}/{total}</Text>
                        <Text style={styles.ringSub}>taken</Text>
                    </ProgressRing>
                    <View style={{ flex: 1 }}>
                        <Text style={styles.heroKicker}>TODAY</Text>
                        {total === 0 ? (
                            <Text style={styles.heroTitle}>No doses scheduled</Text>
                        ) : taken === total ? (
                            <Text style={styles.heroTitle}>All done for today 🎉</Text>
                        ) : next ? (
                            <>
                                <Text style={styles.heroTitle} numberOfLines={1}>Next: {next.med.name}</Text>
                                <Text style={styles.heroSub}>{formatTime(next.time)} · {next.med.quantityPerDose} {next.med.doseUnit}</Text>
                            </>
                        ) : (
                            <Text style={styles.heroTitle}>{total - taken} dose{total - taken > 1 ? 's' : ''} left to log</Text>
                        )}
                        {missed > 0 && (
                            <View style={styles.missedChip}>
                                <Text style={styles.missedText}>{missed} missed</Text>
                            </View>
                        )}
                    </View>
                </View>

                <HealthCard compact />

                {activeCount === 0 ? (
                    <View style={styles.empty}>
                        <View style={styles.emptyIcon}><Sparkles size={34} color={colors.primary} /></View>
                        <Text style={styles.emptyTitle}>Add your first medicine</Text>
                        <Text style={styles.emptySub}>RemindRx keeps everything on this phone and rings even when the app is closed.</Text>
                        <PressScale onPress={() => nav.navigate('AddMedication')} style={styles.emptyBtn} testID="empty-add">
                            <Plus size={18} color="#FFFFFF" strokeWidth={3} />
                            <Text style={styles.emptyBtnText}>Add medication</Text>
                        </PressScale>
                    </View>
                ) : views.length === 0 ? (
                    <Text style={styles.none}>Nothing scheduled on {cal.dayOfMonth} {MONTHS[m - 1]} {y}.</Text>
                ) : (
                    groups.map(g => (
                        <View key={g.title}>
                            <SectionTitle>{g.title}</SectionTitle>
                            {g.items.map(v => (
                                <DoseCard
                                    key={v.id}
                                    view={v}
                                    actionable={actionable}
                                    onTake={() => take(v)}
                                    onSkip={() => skip(v)}
                                    onSnooze={() => snooze(v)}
                                    onUndo={() => store.undoDose(v)}
                                />
                            ))}
                        </View>
                    ))
                )}
            </ScrollView>

            <PressScale onPress={() => nav.navigate('AddMedication')} style={[styles.fab, { bottom: 18 }]} testID="fab-add">
                <Plus size={28} color="#FFFFFF" strokeWidth={2.6} />
            </PressScale>
            {toast.node}
        </View>
    );
};

const styles = StyleSheet.create({
    header: { flexDirection: 'row', alignItems: 'center' },
    hello: { fontSize: 24, fontWeight: '800', color: colors.text },
    date: { fontSize: 14, color: colors.textSecondary, marginTop: 2, fontWeight: '600' },
    brand: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: colors.primary, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999 },
    brandText: { color: '#FFFFFF', fontWeight: '800', fontSize: 13 },
    week: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 18 },
    day: { width: 44, paddingVertical: 10, borderRadius: 16, alignItems: 'center', backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
    daySel: { backgroundColor: colors.primary, borderColor: colors.primary },
    dayLetter: { fontSize: 11, fontWeight: '700', color: colors.textSecondary },
    dayNum: { fontSize: 17, fontWeight: '800', color: colors.text, marginTop: 2 },
    todayDot: { width: 5, height: 5, borderRadius: 3, marginTop: 4 },
    hero: { flexDirection: 'row', alignItems: 'center', gap: 18, backgroundColor: colors.primary, borderRadius: 24, padding: 18, marginTop: 16 },
    ringNum: { color: '#FFFFFF', fontSize: 22, fontWeight: '900' },
    ringSub: { color: '#E0F2FE', fontSize: 11, fontWeight: '700' },
    heroKicker: { color: '#BAE6FD', fontSize: 11, fontWeight: '800', letterSpacing: 1.2 },
    heroTitle: { color: '#FFFFFF', fontSize: 18, fontWeight: '800', marginTop: 4 },
    heroSub: { color: '#E0F2FE', fontSize: 13, fontWeight: '600', marginTop: 3 },
    missedChip: { alignSelf: 'flex-start', backgroundColor: colors.accent, paddingHorizontal: 10, paddingVertical: 3, borderRadius: 999, marginTop: 8 },
    missedText: { color: '#FFFFFF', fontWeight: '800', fontSize: 12 },
    empty: { alignItems: 'center', marginTop: 40, paddingHorizontal: 20 },
    emptyIcon: { width: 76, height: 76, borderRadius: 24, backgroundColor: colors.primaryTint, alignItems: 'center', justifyContent: 'center' },
    emptyTitle: { fontSize: 19, fontWeight: '800', color: colors.text, marginTop: 16 },
    emptySub: { fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginTop: 6, lineHeight: 20 },
    emptyBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.primary, paddingHorizontal: 22, paddingVertical: 14, borderRadius: 16, marginTop: 18 },
    emptyBtnText: { color: '#FFFFFF', fontWeight: '800', fontSize: 15 },
    none: { textAlign: 'center', color: colors.textSecondary, marginTop: 40, fontSize: 14 },
    fab: {
        position: 'absolute', right: 20, width: 60, height: 60, borderRadius: 20, backgroundColor: colors.primary,
        alignItems: 'center', justifyContent: 'center', elevation: 8, shadowColor: colors.primaryDark, shadowOpacity: 0.35, shadowRadius: 12, shadowOffset: { width: 0, height: 6 },
    },
});
