/**
 * "Dose" unit picker — a scrollable list ordered by relevance to the current
 * type (preferred units first), with the selected unit highlighted. The full
 * catalog stays accessible below the preferred set.
 */
import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Check } from 'lucide-react-native';
import { useTheme } from '../theme';
import { splitUnitsForType } from '@shared/logic';
import { DoseUnit, MedicationType } from '@shared/types';
import BottomSheet from './BottomSheet';

interface Props {
    visible: boolean;
    type: MedicationType;
    selected: DoseUnit;
    onClose: () => void;
    onSelect: (unit: DoseUnit) => void;
}

export const UnitPickerSheet: React.FC<Props> = ({ visible, type, selected, onClose, onSelect }) => {
    const { theme } = useTheme();
    const { suggested, others } = splitUnitsForType(type);
    const units = [...suggested, ...others];
    const firstNonPreferredIndex = suggested.length;

    return (
        <BottomSheet visible={visible} title="Select Dose" onClose={onClose} maxHeightRatio={0.7}>
            <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 8 }}>
                {units.map((unit, i) => {
                    const active = unit === selected;
                    const showSuggestedHeader = i === 0 && suggested.length > 0;
                    const showDivider = i === firstNonPreferredIndex && firstNonPreferredIndex > 0;
                    return (
                        <React.Fragment key={unit}>
                            {showSuggestedHeader && (
                                <Text style={[styles.sectionLabel, styles.firstSectionLabel, { color: theme.colors.textSecondary }]}>
                                    Suggested for {type}
                                </Text>
                            )}
                            {showDivider && (
                                <Text style={[styles.sectionLabel, { color: theme.colors.textSecondary }]}>
                                    All units
                                </Text>
                            )}
                            <TouchableOpacity
                                activeOpacity={0.7}
                                onPress={() => onSelect(unit)}
                                style={[
                                    styles.row,
                                    {
                                        backgroundColor: active ? theme.colors.primary + '14' : 'transparent',
                                        borderColor: active ? theme.colors.primary + '33' : 'transparent',
                                    },
                                ]}>
                                <Text
                                    style={[
                                        styles.label,
                                        { color: active ? theme.colors.primary : theme.colors.text, fontWeight: active ? '700' : '500' },
                                    ]}>
                                    {unit}
                                </Text>
                                {active && (
                                    <View style={[styles.check, { backgroundColor: theme.colors.primary }]}>
                                        <Check size={14} color="#FFFFFF" strokeWidth={3} />
                                    </View>
                                )}
                            </TouchableOpacity>
                        </React.Fragment>
                    );
                })}
            </ScrollView>
        </BottomSheet>
    );
};

const styles = StyleSheet.create({
    sectionLabel: {
        fontSize: 12,
        fontWeight: '600',
        textTransform: 'uppercase',
        letterSpacing: 0.5,
        marginTop: 10,
        marginBottom: 4,
        paddingHorizontal: 4,
    },
    firstSectionLabel: { marginTop: 0 },
    row: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingVertical: 14,
        paddingHorizontal: 14,
        borderRadius: 12,
        borderWidth: 1,
        marginBottom: 4,
    },
    label: { fontSize: 16 },
    check: {
        width: 22,
        height: 22,
        borderRadius: 11,
        alignItems: 'center',
        justifyContent: 'center',
    },
});

export default UnitPickerSheet;
