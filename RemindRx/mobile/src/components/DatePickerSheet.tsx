/**
 * Date picker for iOS (Android uses the native Material dialog directly).
 * HealthApp's version wraps its own calendar; this uses the platform inline
 * picker so there is no extra dependency.
 */
import React, { useState } from 'react';
import { StyleSheet, Text, TouchableOpacity } from 'react-native';
import DateTimePicker from '@react-native-community/datetimepicker';
import { useTheme } from '../theme';
import BottomSheet from './BottomSheet';

interface Props {
    visible: boolean;
    value: Date;
    minDate: Date;
    maxDate: Date;
    title: string;
    onClose: () => void;
    onConfirm: (d: Date) => void;
}

export const DatePickerSheet: React.FC<Props> = ({ visible, value, minDate, maxDate, title, onClose, onConfirm }) => {
    const { theme } = useTheme();
    const [d, setD] = useState(value);
    return (
        <BottomSheet visible={visible} title={title} onClose={onClose}>
            <DateTimePicker value={d} mode="date" display="inline" minimumDate={minDate} maximumDate={maxDate} accentColor={theme.colors.primary} onChange={(_, next) => next && setD(next)} />
            <TouchableOpacity style={[styles.btn, { backgroundColor: theme.colors.primary }]} onPress={() => onConfirm(d)}>
                <Text style={styles.btnText}>Done</Text>
            </TouchableOpacity>
        </BottomSheet>
    );
};

const styles = StyleSheet.create({
    btn: { borderRadius: 14, paddingVertical: 14, alignItems: 'center', marginTop: 12 },
    btnText: { color: '#FFFFFF', fontWeight: '800', fontSize: 16 },
});

export default DatePickerSheet;
