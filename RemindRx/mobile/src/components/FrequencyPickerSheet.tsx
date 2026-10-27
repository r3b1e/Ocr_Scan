/**
 * "Set Frequency" sheet — pick one of the 7 modes; modes that need a parameter
 * reveal an inline control (X/day stepper, weekday toggles, interval stepper,
 * day-of-month grid). Confirm applies the chosen mode + its config to the form.
 */
import React, { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Check, Minus, Plus } from 'lucide-react-native';
import { useTheme } from '../theme';
import {
    FREQUENCY_MODES,
    MULTI_DAILY_MAX,
    MULTI_DAILY_MIN,
    WEEKDAY_LABELS,
} from '@shared/catalog';
import { FrequencyConfig, FrequencyType } from '@shared/types';
import BottomSheet from './BottomSheet';

interface Props {
    visible: boolean;
    type: FrequencyType;
    config: FrequencyConfig;
    onClose: () => void;
    onApply: (type: FrequencyType, config: FrequencyConfig) => void;
}

const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, n));

export const FrequencyPickerSheet: React.FC<Props> = ({ visible, type, config, onClose, onApply }) => {
    const { theme } = useTheme();
    const [mode, setMode] = useState<FrequencyType>(type);
    const [cfg, setCfg] = useState<FrequencyConfig>(config);

    // Reset local state each time the sheet opens.
    useEffect(() => {
        if (visible) {
            setMode(type);
            setCfg(config);
        }
    }, [visible, type, config]);

    const patch = (p: Partial<FrequencyConfig>) => setCfg(c => ({ ...c, ...p }));

    const toggleWeekday = (d: number) => {
        const current = cfg.weekdays ?? [];
        patch({
            weekdays: current.includes(d) ? current.filter(x => x !== d) : [...current, d].sort((a, b) => a - b),
        });
    };

    const onPickMode = (m: FrequencyType) => {
        setMode(m);
        // Seed sensible defaults for parameterised modes if missing.
        if (m === FrequencyType.MultiDaily && cfg.multiCount == null) patch({ multiCount: MULTI_DAILY_MIN });
        if (m === FrequencyType.SpecificDays && (cfg.weekdays == null || cfg.weekdays.length === 0)) {
            patch({ weekdays: [1, 3, 5] });
        }
        if (m === FrequencyType.EveryXDays && cfg.intervalDays == null) patch({ intervalDays: 2 });
        if (m === FrequencyType.DayOfMonth && cfg.dayOfMonth == null) patch({ dayOfMonth: 1 });
    };

    const Stepper = ({ value, min, max, onStep, suffix }: { value: number; min: number; max: number; onStep: (v: number) => void; suffix: string }) => (
        <View style={styles.stepperRow}>
            <TouchableOpacity
                onPress={() => onStep(clamp(value - 1, min, max))}
                disabled={value <= min}
                style={[styles.stepBtn, { borderColor: theme.colors.border, opacity: value <= min ? 0.4 : 1 }]}>
                <Minus size={18} color={theme.colors.text} />
            </TouchableOpacity>
            <Text style={[styles.stepValue, { color: theme.colors.text }]}>
                {value} <Text style={{ fontSize: 14, color: theme.colors.textSecondary, fontWeight: '500' }}>{suffix}</Text>
            </Text>
            <TouchableOpacity
                onPress={() => onStep(clamp(value + 1, min, max))}
                disabled={value >= max}
                style={[styles.stepBtn, { borderColor: theme.colors.border, opacity: value >= max ? 0.4 : 1 }]}>
                <Plus size={18} color={theme.colors.text} />
            </TouchableOpacity>
        </View>
    );

    const renderConfig = () => {
        switch (mode) {
            case FrequencyType.MultiDaily:
                return (
                    <View style={styles.configBox}>
                        <Text style={[styles.configLabel, { color: theme.colors.textSecondary }]}>How many times a day?</Text>
                        <Stepper
                            value={clamp(cfg.multiCount ?? MULTI_DAILY_MIN, MULTI_DAILY_MIN, MULTI_DAILY_MAX)}
                            min={MULTI_DAILY_MIN}
                            max={MULTI_DAILY_MAX}
                            onStep={v => patch({ multiCount: v })}
                            suffix="times / day"
                        />
                    </View>
                );
            case FrequencyType.SpecificDays:
                return (
                    <View style={styles.configBox}>
                        <Text style={[styles.configLabel, { color: theme.colors.textSecondary }]}>Repeat on</Text>
                        <View style={styles.weekRow}>
                            {WEEKDAY_LABELS.map((lbl, d) => {
                                const on = (cfg.weekdays ?? []).includes(d);
                                return (
                                    <TouchableOpacity
                                        key={d}
                                        onPress={() => toggleWeekday(d)}
                                        style={[
                                            styles.dayChip,
                                            {
                                                backgroundColor: on ? theme.colors.primary : theme.colors.background,
                                                borderColor: on ? theme.colors.primary : theme.colors.border,
                                            },
                                        ]}>
                                        <Text style={{ fontSize: 12, fontWeight: '700', color: on ? '#FFFFFF' : theme.colors.textSecondary }}>
                                            {lbl[0]}
                                        </Text>
                                    </TouchableOpacity>
                                );
                            })}
                        </View>
                    </View>
                );
            case FrequencyType.EveryXDays:
                return (
                    <View style={styles.configBox}>
                        <Text style={[styles.configLabel, { color: theme.colors.textSecondary }]}>Interval</Text>
                        <Stepper
                            value={clamp(cfg.intervalDays ?? 2, 1, 90)}
                            min={1}
                            max={90}
                            onStep={v => patch({ intervalDays: v })}
                            suffix={(cfg.intervalDays ?? 2) === 1 ? 'day' : 'days'}
                        />
                    </View>
                );
            case FrequencyType.DayOfMonth:
                return (
                    <View style={styles.configBox}>
                        <Text style={[styles.configLabel, { color: theme.colors.textSecondary }]}>Day of month</Text>
                        <View style={styles.monthGrid}>
                            {Array.from({ length: 31 }, (_, i) => i + 1).map(d => {
                                const on = cfg.dayOfMonth === d;
                                return (
                                    <TouchableOpacity
                                        key={d}
                                        onPress={() => patch({ dayOfMonth: d })}
                                        style={[
                                            styles.monthCell,
                                            {
                                                backgroundColor: on ? theme.colors.primary : theme.colors.background,
                                                borderColor: on ? theme.colors.primary : theme.colors.border,
                                            },
                                        ]}>
                                        <Text style={{ fontSize: 13, fontWeight: '600', color: on ? '#FFFFFF' : theme.colors.text }}>{d}</Text>
                                    </TouchableOpacity>
                                );
                            })}
                        </View>
                        {(cfg.dayOfMonth ?? 1) > 28 && (
                            <Text style={[styles.note, { color: theme.colors.warning }]}>
                                Short months will use their last day.
                            </Text>
                        )}
                    </View>
                );
            default:
                return null;
        }
    };

    return (
        <BottomSheet visible={visible} title="Set Frequency" onClose={onClose} maxHeightRatio={0.88}>
            <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 8 }}>
                {FREQUENCY_MODES.map(m => {
                    const active = m.type === mode;
                    return (
                        <View key={m.type}>
                            <TouchableOpacity
                                activeOpacity={0.7}
                                onPress={() => onPickMode(m.type)}
                                style={[
                                    styles.modeRow,
                                    {
                                        backgroundColor: active ? theme.colors.primary + '14' : theme.colors.background,
                                        borderColor: active ? theme.colors.primary : theme.colors.border,
                                    },
                                ]}>
                                <View style={{ flex: 1 }}>
                                    <Text style={[styles.modeLabel, { color: active ? theme.colors.primary : theme.colors.text }]}>{m.label}</Text>
                                    <Text style={[styles.modeHint, { color: theme.colors.textSecondary }]}>{m.hint}</Text>
                                </View>
                                <View
                                    style={[
                                        styles.radio,
                                        { borderColor: active ? theme.colors.primary : theme.colors.border, backgroundColor: active ? theme.colors.primary : 'transparent' },
                                    ]}>
                                    {active && <Check size={14} color="#FFFFFF" strokeWidth={3} />}
                                </View>
                            </TouchableOpacity>
                            {active && renderConfig()}
                        </View>
                    );
                })}
            </ScrollView>

            <TouchableOpacity
                activeOpacity={0.85}
                onPress={() => onApply(mode, cfg)}
                style={[styles.applyBtn, { backgroundColor: theme.colors.primary }]}>
                <Text style={styles.applyText}>Confirm</Text>
            </TouchableOpacity>
        </BottomSheet>
    );
};

const styles = StyleSheet.create({
    modeRow: {
        flexDirection: 'row',
        alignItems: 'center',
        borderRadius: 14,
        borderWidth: 1,
        paddingVertical: 13,
        paddingHorizontal: 14,
        marginBottom: 8,
        gap: 10,
    },
    modeLabel: { fontSize: 15, fontWeight: '700' },
    modeHint: { fontSize: 12, marginTop: 2 },
    radio: {
        width: 22,
        height: 22,
        borderRadius: 11,
        borderWidth: 2,
        alignItems: 'center',
        justifyContent: 'center',
    },
    configBox: {
        marginTop: -2,
        marginBottom: 12,
        paddingHorizontal: 4,
    },
    configLabel: { fontSize: 13, fontWeight: '600', marginBottom: 10 },
    stepperRow: { flexDirection: 'row', alignItems: 'center', gap: 18 },
    stepBtn: {
        width: 40,
        height: 40,
        borderRadius: 12,
        borderWidth: 1,
        alignItems: 'center',
        justifyContent: 'center',
    },
    stepValue: { fontSize: 20, fontWeight: '700', minWidth: 110, textAlign: 'center' },
    weekRow: { flexDirection: 'row', justifyContent: 'space-between' },
    dayChip: {
        width: 40,
        height: 40,
        borderRadius: 20,
        borderWidth: 1,
        alignItems: 'center',
        justifyContent: 'center',
    },
    monthGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
    monthCell: {
        width: 40,
        height: 40,
        borderRadius: 10,
        borderWidth: 1,
        alignItems: 'center',
        justifyContent: 'center',
    },
    note: { fontSize: 12, marginTop: 10, fontWeight: '500' },
    applyBtn: {
        marginTop: 8,
        borderRadius: 14,
        paddingVertical: 15,
        alignItems: 'center',
    },
    applyText: { color: '#FFFFFF', fontSize: 16, fontWeight: '700' },
});

export default FrequencyPickerSheet;
