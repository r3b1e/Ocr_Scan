/** Small shared UI pieces in the RemindRx look. */
import React, { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet, Text, View, ViewStyle } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { colors, shadow } from '../theme';

export const Card: React.FC<{ style?: ViewStyle | ViewStyle[]; children: React.ReactNode }> = ({ style, children }) => (
    <View style={[styles.card, style as any]}>{children}</View>
);

export const SectionTitle: React.FC<{ children: React.ReactNode; right?: React.ReactNode }> = ({ children, right }) => (
    <View style={styles.sectionRow}>
        <Text style={styles.section}>{children}</Text>
        {right}
    </View>
);

/** Springy press feedback for any tappable surface. */
export const PressScale: React.FC<{ onPress?: () => void; onLongPress?: () => void; style?: any; children: React.ReactNode; disabled?: boolean; testID?: string }> = ({ onPress, onLongPress, style, children, disabled, testID }) => {
    const scale = useRef(new Animated.Value(1)).current;
    const to = (v: number) => Animated.spring(scale, { toValue: v, useNativeDriver: true, speed: 40, bounciness: 6 }).start();
    return (
        <Pressable testID={testID} disabled={disabled} onPress={onPress} onLongPress={onLongPress} onPressIn={() => to(0.96)} onPressOut={() => to(1)}>
            <Animated.View style={[style, { transform: [{ scale }] }]}>{children}</Animated.View>
        </Pressable>
    );
};

export const ProgressRing: React.FC<{ size: number; stroke: number; pct: number; color?: string; track?: string; children?: React.ReactNode }> = ({ size, stroke, pct, color = colors.primary, track = colors.primaryTint, children }) => {
    const r = (size - stroke) / 2;
    const c = 2 * Math.PI * r;
    const anim = useRef(new Animated.Value(0)).current;
    const [shown, setShown] = useState(0);
    useEffect(() => {
        const id = anim.addListener(({ value }) => setShown(value));
        Animated.timing(anim, { toValue: Math.max(0, Math.min(100, pct)), duration: 700, useNativeDriver: false }).start();
        return () => anim.removeListener(id);
    }, [pct, anim]);
    return (
        <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
            <Svg width={size} height={size} style={StyleSheet.absoluteFill}>
                <Circle cx={size / 2} cy={size / 2} r={r} stroke={track} strokeWidth={stroke} fill="none" />
                <Circle
                    cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={stroke} fill="none"
                    strokeDasharray={`${c} ${c}`} strokeDashoffset={c * (1 - shown / 100)} strokeLinecap="round"
                    transform={`rotate(-90 ${size / 2} ${size / 2})`}
                />
            </Svg>
            {children}
        </View>
    );
};

export const Pill: React.FC<{ label: string; fg: string; bg: string }> = ({ label, fg, bg }) => (
    <View style={[styles.pill, { backgroundColor: bg }]}>
        <Text style={[styles.pillText, { color: fg }]}>{label}</Text>
    </View>
);

/** Bottom toast with an optional action (Undo). */
export const useToast = () => {
    const [msg, setMsg] = useState<{ text: string; action?: { label: string; run: () => void } } | null>(null);
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const show = (text: string, action?: { label: string; run: () => void }) => {
        setMsg({ text, action });
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => setMsg(null), 3500);
    };
    const node = msg ? (
        <View style={styles.toast} pointerEvents="box-none">
            <Text style={styles.toastText} numberOfLines={2}>{msg.text}</Text>
            {msg.action && (
                <Pressable onPress={() => { msg.action!.run(); setMsg(null); }} hitSlop={10}>
                    <Text style={styles.toastAction}>{msg.action.label}</Text>
                </Pressable>
            )}
        </View>
    ) : null;
    return { show, node };
};

const styles = StyleSheet.create({
    card: { backgroundColor: colors.surface, borderRadius: 20, padding: 16, borderWidth: 1, borderColor: colors.border, ...shadow },
    sectionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 22, marginBottom: 10 },
    section: { fontSize: 13, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8, textTransform: 'uppercase' },
    pill: { paddingHorizontal: 9, paddingVertical: 3, borderRadius: 999 },
    pillText: { fontSize: 11, fontWeight: '800', letterSpacing: 0.3 },
    toast: {
        position: 'absolute', left: 16, right: 16, bottom: 18, flexDirection: 'row', alignItems: 'center', gap: 12,
        backgroundColor: colors.text, borderRadius: 14, paddingHorizontal: 16, paddingVertical: 13, elevation: 8,
    },
    toastText: { flex: 1, color: '#FFFFFF', fontSize: 14, fontWeight: '600' },
    toastAction: { color: '#7DD3FC', fontSize: 14, fontWeight: '800' },
});
