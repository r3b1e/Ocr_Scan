/**
 * Full-screen ringer for alarm-mode reminders (from HealthApp's
 * MedicationAlarmScreen). Rings until the user takes, skips or snoozes.
 * Back = snooze, so an alarm is never silently dismissed.
 */
import React, { useEffect, useRef } from 'react';
import { Animated, BackHandler, Easing, Pressable, StyleSheet, Text, View } from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import notifee from '@notifee/react-native';
import { AlarmClock, Check, Pill, X } from 'lucide-react-native';
import { SNOOZE_MIN } from '@shared/index';
import ReminderService, { MedData } from '../reminders/ReminderService';
import { AlarmSound } from '../reminders/AlarmSound';
import { setShowOverLockScreen } from '../reminders/permissions';
import { colors } from '../theme';

const MEAL: Record<string, string> = { before: 'Before food', after: 'After food', with: 'With food' };

export const AlarmScreen: React.FC = () => {
    const insets = useSafeAreaInsets();
    const nav = useNavigation<any>();
    const data = (useRoute<any>().params ?? {}) as MedData;
    const pulse = useRef(new Animated.Value(0)).current;
    const acted = useRef(false);

    const close = () => (nav.canGoBack() ? nav.goBack() : nav.reset({ index: 0, routes: [{ name: 'Tabs' }] }));

    const act = async (id: 'TAKEN' | 'SKIP' | 'SNOOZE') => {
        if (acted.current) return;
        acted.current = true;
        AlarmSound.stop();
        close();
        await ReminderService.handleAction(id, data).catch(() => {});
    };

    useEffect(() => {
        // The notification's own looping sound would play over ours: clear it
        // from the shade (the dose stays unlogged until the user acts here).
        notifee.getDisplayedNotifications().then(list => {
            list.filter(n => (n.notification.data as any)?.medId === data.medId && (n.notification.data as any)?.slotIndex === data.slotIndex)
                .forEach(n => n.id && notifee.cancelDisplayedNotification(n.id));
        }).catch(() => {});
        setShowOverLockScreen(true);
        AlarmSound.start();
        const loop = Animated.loop(Animated.timing(pulse, { toValue: 1, duration: 1600, easing: Easing.out(Easing.quad), useNativeDriver: true }));
        loop.start();
        const sub = BackHandler.addEventListener('hardwareBackPress', () => { act('SNOOZE'); return true; });
        return () => { AlarmSound.stop(); setShowOverLockScreen(false); loop.stop(); sub.remove(); };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const ring = (delay: number) => ({
        opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.5 - delay * 0.2, 0] }),
        transform: [{ scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.9 + delay * 0.4] }) }],
    });

    return (
        <View style={[styles.root, { paddingTop: insets.top + 36, paddingBottom: insets.bottom + 24 }]}>
            <View style={styles.center}>
                <View style={styles.iconBox}>
                    <Animated.View style={[styles.ring, ring(0)]} />
                    <Animated.View style={[styles.ring, ring(1)]} />
                    <View style={styles.icon}><Pill size={60} color={colors.accent} strokeWidth={2} /></View>
                </View>
                <Text style={styles.kicker}>TIME FOR YOUR MEDICINE</Text>
                <Text style={styles.name} numberOfLines={2}>{data.name ?? 'Medication'}</Text>
                {!!data.dose && <Text style={styles.dose}>Take {data.dose}</Text>}
                <View style={styles.chips}>
                    {!!data.time && <Text style={styles.chip}>{data.time}</Text>}
                    {!!MEAL[data.meal] && <Text style={styles.chip}>{MEAL[data.meal]}</Text>}
                </View>
            </View>

            <View style={{ gap: 12 }}>
                <Pressable onPress={() => act('TAKEN')} style={({ pressed }) => [styles.take, pressed && { opacity: 0.9 }]} testID="alarm-taken">
                    <Check size={24} color={colors.accent} strokeWidth={3} />
                    <Text style={styles.takeText}>I’ve taken it</Text>
                </Pressable>
                <View style={{ flexDirection: 'row', gap: 12 }}>
                    <Pressable onPress={() => act('SNOOZE')} style={styles.sec} testID="alarm-snooze">
                        <AlarmClock size={20} color="#FFFFFF" />
                        <Text style={styles.secText}>Snooze {SNOOZE_MIN}m</Text>
                    </Pressable>
                    <Pressable onPress={() => act('SKIP')} style={styles.sec} testID="alarm-skip">
                        <X size={20} color="#FFFFFF" />
                        <Text style={styles.secText}>Skip</Text>
                    </Pressable>
                </View>
            </View>
        </View>
    );
};

const styles = StyleSheet.create({
    root: { flex: 1, backgroundColor: colors.accent, paddingHorizontal: 24, justifyContent: 'space-between' },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
    iconBox: { width: 220, height: 220, alignItems: 'center', justifyContent: 'center', marginBottom: 6 },
    ring: { position: 'absolute', width: 128, height: 128, borderRadius: 64, backgroundColor: '#FFFFFF' },
    icon: { width: 128, height: 128, borderRadius: 64, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
    kicker: { color: 'rgba(255,255,255,0.9)', fontSize: 12, fontWeight: '800', letterSpacing: 1.6 },
    name: { color: '#FFFFFF', fontSize: 34, fontWeight: '900', textAlign: 'center' },
    dose: { color: '#FFFFFF', fontSize: 18, fontWeight: '700' },
    chips: { flexDirection: 'row', gap: 8, marginTop: 4 },
    chip: { color: '#FFFFFF', backgroundColor: 'rgba(255,255,255,0.2)', paddingHorizontal: 14, paddingVertical: 6, borderRadius: 999, fontWeight: '800', overflow: 'hidden' },
    take: { height: 64, borderRadius: 20, backgroundColor: '#FFFFFF', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10 },
    takeText: { color: colors.accent, fontSize: 18, fontWeight: '900' },
    sec: { flex: 1, height: 56, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.2)', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
    secText: { color: '#FFFFFF', fontSize: 16, fontWeight: '800' },
});
