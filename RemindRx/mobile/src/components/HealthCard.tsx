/** Shows what could stop reminders from firing, with a Fix button per item. */
import React, { useCallback, useEffect, useState } from 'react';
import { AppState, Pressable, StyleSheet, Text, View } from 'react-native';
import { CheckCircle2, ShieldAlert, ShieldCheck } from 'lucide-react-native';
import { colors } from '../theme';
import { Card } from './ui';
import { HEALTH_COPY, HealthKey, ReminderHealth, fixHealth, getReminderHealth, issues } from '../reminders/permissions';

export const useReminderHealth = () => {
    const [health, setHealth] = useState<ReminderHealth | null>(null);
    const refresh = useCallback(() => { getReminderHealth().then(setHealth).catch(() => {}); }, []);
    useEffect(() => {
        refresh();
        const sub = AppState.addEventListener('change', s => { if (s === 'active') refresh(); });
        return () => sub.remove();
    }, [refresh]);
    return { health, refresh };
};

export const HealthCard: React.FC<{ compact?: boolean }> = ({ compact }) => {
    const { health, refresh } = useReminderHealth();
    if (!health) return null;
    const bad = issues(health);
    if (compact && bad.length === 0) return null;
    const keys: HealthKey[] = compact ? bad : (Object.keys(HEALTH_COPY) as HealthKey[]);
    const fix = async (k: HealthKey) => { await fixHealth(k).catch(() => {}); setTimeout(refresh, 600); };

    return (
        <Card style={[styles.card, bad.length ? styles.cardBad : null] as any}>
            <View style={styles.head}>
                {bad.length ? <ShieldAlert size={22} color={colors.accent} /> : <ShieldCheck size={22} color={colors.success} />}
                <Text style={styles.title}>{bad.length ? 'Reminders may not ring' : 'Reminders are ready'}</Text>
            </View>
            {keys.map(k => {
                const ok = k === 'batteryOptimized' ? !health[k] : health[k];
                return (
                    <View key={k} style={styles.row}>
                        <View style={{ flex: 1 }}>
                            <Text style={styles.rowTitle}>{HEALTH_COPY[k].title}</Text>
                            <Text style={[styles.rowSub, !ok && { color: colors.accent }]}>{ok ? HEALTH_COPY[k].ok : HEALTH_COPY[k].bad}</Text>
                        </View>
                        {ok ? (
                            <CheckCircle2 size={20} color={colors.success} />
                        ) : (
                            <Pressable onPress={() => fix(k)} style={styles.fix} testID={`fix-${k}`}>
                                <Text style={styles.fixText}>Fix</Text>
                            </Pressable>
                        )}
                    </View>
                );
            })}
        </Card>
    );
};

const styles = StyleSheet.create({
    card: { marginTop: 14 },
    cardBad: { borderColor: '#FECDD3', backgroundColor: '#FFF7F8' },
    head: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 6 },
    title: { fontSize: 16, fontWeight: '800', color: colors.text },
    row: { flexDirection: 'row', alignItems: 'center', paddingVertical: 9, gap: 12 },
    rowTitle: { fontSize: 14, fontWeight: '700', color: colors.text },
    rowSub: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
    fix: { backgroundColor: colors.accent, paddingHorizontal: 16, paddingVertical: 7, borderRadius: 999 },
    fixText: { color: '#FFFFFF', fontWeight: '800', fontSize: 13 },
});
