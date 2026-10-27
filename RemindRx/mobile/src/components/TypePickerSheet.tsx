/**
 * "Select Medication" sheet — a 3-column scrollable grid of medication-type
 * tiles. The selected tile is highlighted. Selecting a type only switches the
 * focus (and re-links the unit list); it does NOT close the sheet — the user
 * dismisses it themselves via the close button or backdrop.
 *
 * Uses a FlatList with numColumns for a reliable equal-width grid (a ScrollView
 * + flexWrap + percentage widths misbehaved inside the sheet's Modal).
 */
import React from 'react';
import { FlatList, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useTheme } from '../theme';
import { MEDICATION_TYPES, TypeEntry } from '@shared/catalog';
import { MedicationType } from '@shared/types';
import BottomSheet from './BottomSheet';
import { ICONS } from '../icons';

interface Props {
    visible: boolean;
    selected: MedicationType;
    onClose: () => void;
    onSelect: (type: MedicationType) => void;
}

const COLS = 3;

// Pad to a full last row so trailing tiles keep their column width (flex:1).
type GridItem = TypeEntry | { placeholder: true; key: string };
const GRID: GridItem[] = (() => {
    const items: GridItem[] = [...MEDICATION_TYPES];
    while (items.length % COLS !== 0) items.push({ placeholder: true, key: `pad-${items.length}` });
    return items;
})();

export const TypePickerSheet: React.FC<Props> = ({ visible, selected, onClose, onSelect }) => {
    const { theme } = useTheme();

    return (
        <BottomSheet visible={visible} title="Select Medication" onClose={onClose} maxHeightRatio={0.82}>
            <FlatList
                data={GRID}
                numColumns={COLS}
                extraData={selected}
                removeClippedSubviews={false}
                keyExtractor={item => ('placeholder' in item ? item.key : item.type)}
                keyboardShouldPersistTaps="always"
                showsVerticalScrollIndicator={false}
                columnWrapperStyle={styles.row}
                contentContainerStyle={{ paddingBottom: 8 }}
                renderItem={({ item }) => {
                    if ('placeholder' in item) return <View style={styles.tile} />;
                    const { type, label, icon } = item;
                    const Icon = ICONS[icon];
                    const active = type === selected;
                    return (
                        <TouchableOpacity
                            activeOpacity={0.8}
                            onPress={() => onSelect(type)}
                            style={[
                                styles.tile,
                                styles.tileFill,
                                {
                                    backgroundColor: active ? theme.colors.primary : theme.colors.background,
                                    borderColor: active ? theme.colors.primary : theme.colors.border,
                                },
                            ]}>
                            <View
                                style={[
                                    styles.iconWrap,
                                    { backgroundColor: active ? 'rgba(255,255,255,0.18)' : theme.colors.primary + '14' },
                                ]}>
                                <Icon size={26} color={active ? '#FFFFFF' : theme.colors.primary} strokeWidth={2} />
                            </View>
                            <Text numberOfLines={1} style={[styles.label, { color: active ? '#FFFFFF' : theme.colors.text }]}>
                                {label}
                            </Text>
                        </TouchableOpacity>
                    );
                }}
            />
        </BottomSheet>
    );
};

const styles = StyleSheet.create({
    row: { gap: 10, marginBottom: 12 },
    tile: { flex: 1, aspectRatio: 0.92 },
    tileFill: {
        borderRadius: 16,
        borderWidth: 1,
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        paddingHorizontal: 4,
    },
    iconWrap: {
        width: 48,
        height: 48,
        borderRadius: 14,
        alignItems: 'center',
        justifyContent: 'center',
    },
    label: { fontSize: 12, fontWeight: '600', textAlign: 'center' },
});

export default TypePickerSheet;
