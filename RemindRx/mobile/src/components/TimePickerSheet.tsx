/**
 * TimePickerSheet — a themed analog clock time picker (Material-style) used in
 * place of the Android-only DateTimePickerAndroid clock, which is a no-op on iOS.
 * Tap/drag the clock face to set the hour, then the minute; AM/PM toggle on top.
 * Returns a 24-hour { hour, minute }.
 */
import React, { useRef, useState } from 'react';
import {
    GestureResponderEvent,
    PanResponder,
    StyleSheet,
    Text,
    TouchableOpacity,
    View,
} from 'react-native';
import Svg, { Circle, Line } from 'react-native-svg';
import { useTheme } from '../theme';
import BottomSheet from './BottomSheet';

interface Props {
    visible: boolean;
    hour: number;   // 24h (0..23)
    minute: number; // 0..59
    title?: string;
    onClose: () => void;
    onConfirm: (t: { hour: number; minute: number }) => void;
}

const CLOCK = 268;
const R = CLOCK / 2;
const NUM_R = R - 26;     // radius the numbers sit on
const KNOB = 19;          // selection knob radius

const pad2 = (n: number) => String(n).padStart(2, '0');
const HOURS = Array.from({ length: 12 }, (_, i) => i + 1);   // 1..12
const MIN_MARKS = Array.from({ length: 12 }, (_, i) => i * 5); // 0,5,...,55

const posFor = (deg: number, radius: number) => ({
    x: R + radius * Math.sin((deg * Math.PI) / 180),
    y: R - radius * Math.cos((deg * Math.PI) / 180),
});

type Mode = 'hour' | 'minute';
interface Sel { h12: number; min: number; period: 'AM' | 'PM'; mode: Mode }

export const TimePickerSheet: React.FC<Props> = ({ visible, hour, minute, title = 'Set Time', onClose, onConfirm }) => {
    const { theme } = useTheme();
    const [sel, setSel] = useState<Sel>({ h12: 12, min: 0, period: 'AM', mode: 'hour' });

    // Derive selection from the incoming 24h value each time the sheet opens.
    const wasVisible = useRef(false);
    if (visible && !wasVisible.current) {
        wasVisible.current = true;
        const period: 'AM' | 'PM' = hour >= 12 ? 'PM' : 'AM';
        let h12 = hour % 12;
        if (h12 === 0) h12 = 12;
        if (sel.h12 !== h12 || sel.min !== minute || sel.period !== period || sel.mode !== 'hour') {
            setSel({ h12, min: minute, period, mode: 'hour' });
        }
    } else if (!visible && wasVisible.current) {
        wasVisible.current = false;
    }

    // PanResponder reads the live mode through a ref (it's created once).
    const modeRef = useRef<Mode>(sel.mode);
    modeRef.current = sel.mode;

    const applyTouch = (e: GestureResponderEvent) => {
        const { locationX, locationY } = e.nativeEvent;
        const dx = locationX - R;
        const dy = locationY - R;
        let deg = (Math.atan2(dx, -dy) * 180) / Math.PI;
        if (deg < 0) deg += 360;
        if (modeRef.current === 'hour') {
            const h = Math.round(deg / 30) % 12 || 12;
            setSel(s => ({ ...s, h12: h }));
        } else {
            const m = Math.round(deg / 6) % 60;
            setSel(s => ({ ...s, min: m }));
        }
    };

    const pan = useRef(
        PanResponder.create({
            onStartShouldSetPanResponder: () => true,
            onMoveShouldSetPanResponder: () => true,
            onPanResponderGrant: applyTouch,
            onPanResponderMove: applyTouch,
            onPanResponderRelease: () => {
                // After picking the hour, advance to minute selection (Material flow).
                if (modeRef.current === 'hour') {
                    setSel(s => ({ ...s, mode: 'minute' }));
                }
            },
        }),
    ).current;

    const confirm = () => {
        let h24 = sel.h12 % 12;
        if (sel.period === 'PM') h24 += 12;
        onConfirm({ hour: h24, minute: sel.min });
    };

    const knob = sel.mode === 'hour' ? posFor(sel.h12 * 30, NUM_R) : posFor(sel.min * 6, NUM_R);
    const numbers = sel.mode === 'hour' ? HOURS : MIN_MARKS;
    const isSelectedNum = (n: number) => (sel.mode === 'hour' ? sel.h12 === n : sel.min === n);

    const periodBtn = (p: 'AM' | 'PM') => {
        const on = sel.period === p;
        return (
            <TouchableOpacity
                onPress={() => setSel(s => ({ ...s, period: p }))}
                style={[
                    styles.periodBtn,
                    {
                        backgroundColor: on ? theme.colors.primary : theme.colors.background,
                        borderColor: on ? theme.colors.primary : theme.colors.border,
                    },
                ]}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: on ? '#FFFFFF' : theme.colors.textSecondary }}>{p}</Text>
            </TouchableOpacity>
        );
    };

    return (
        <BottomSheet visible={visible} title={title} onClose={onClose} maxHeightRatio={0.82}>
            {/* Digital readout — tap HH or MM to choose which the clock edits. */}
            <View style={styles.readout}>
                <TouchableOpacity onPress={() => setSel(s => ({ ...s, mode: 'hour' }))} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                    <Text style={[styles.bigNum, { color: sel.mode === 'hour' ? theme.colors.primary : theme.colors.text }]}>{pad2(sel.h12)}</Text>
                </TouchableOpacity>
                <Text style={[styles.bigNum, { color: theme.colors.text, marginHorizontal: 2 }]}>:</Text>
                <TouchableOpacity onPress={() => setSel(s => ({ ...s, mode: 'minute' }))} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                    <Text style={[styles.bigNum, { color: sel.mode === 'minute' ? theme.colors.primary : theme.colors.text }]}>{pad2(sel.min)}</Text>
                </TouchableOpacity>
                <View style={styles.periodCol}>
                    {periodBtn('AM')}
                    {periodBtn('PM')}
                </View>
            </View>

            {/* Clock face */}
            <View style={styles.clockWrap}>
                <View style={{ width: CLOCK, height: CLOCK }} {...pan.panHandlers}>
                    <Svg width={CLOCK} height={CLOCK} style={StyleSheet.absoluteFill} pointerEvents="none">
                        <Circle cx={R} cy={R} r={R} fill={theme.colors.background} />
                        <Line x1={R} y1={R} x2={knob.x} y2={knob.y} stroke={theme.colors.primary} strokeWidth={2} />
                        <Circle cx={knob.x} cy={knob.y} r={KNOB} fill={theme.colors.primary} />
                        <Circle cx={R} cy={R} r={4} fill={theme.colors.primary} />
                    </Svg>
                    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
                    {numbers.map(n => {
                        const deg = sel.mode === 'hour' ? n * 30 : n * 6;
                        const p = posFor(deg, NUM_R);
                        const on = isSelectedNum(n);
                        return (
                            <Text
                                key={n}
                                style={{
                                    position: 'absolute',
                                    width: 34,
                                    textAlign: 'center',
                                    left: p.x - 17,
                                    top: p.y - 11,
                                    fontSize: 16,
                                    fontWeight: on ? '800' : '600',
                                    color: on ? '#FFFFFF' : theme.colors.text,
                                }}>
                                {sel.mode === 'hour' ? n : pad2(n)}
                            </Text>
                        );
                    })}
                    </View>
                </View>
            </View>

            <TouchableOpacity activeOpacity={0.85} onPress={confirm} style={[styles.applyBtn, { backgroundColor: theme.colors.primary }]}>
                <Text style={styles.applyText}>Confirm</Text>
            </TouchableOpacity>
        </BottomSheet>
    );
};

const styles = StyleSheet.create({
    readout: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        marginTop: 2,
        marginBottom: 14,
    },
    bigNum: { fontSize: 46, fontWeight: '800', letterSpacing: -1 },
    periodCol: { marginLeft: 16, gap: 6 },
    periodBtn: {
        width: 50,
        height: 34,
        borderRadius: 10,
        borderWidth: 1,
        alignItems: 'center',
        justifyContent: 'center',
    },
    clockWrap: { alignItems: 'center', justifyContent: 'center', marginBottom: 14 },
    applyBtn: { borderRadius: 14, paddingVertical: 15, alignItems: 'center' },
    applyText: { color: '#FFFFFF', fontSize: 16, fontWeight: '700' },
});

export default TimePickerSheet;
