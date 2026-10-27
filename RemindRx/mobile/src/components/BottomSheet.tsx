/**
 * Reusable bottom sheet: dimmed backdrop + slide-up panel with a grab handle
 * and optional title row. Tap the backdrop or the close button to dismiss.
 * Content scrolls within a capped max height.
 */
import React, { useEffect, useRef } from 'react';
import {
    Animated,
    Dimensions,
    Modal,
    Pressable,
    StyleSheet,
    Text,
    TouchableOpacity,
    View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { X } from 'lucide-react-native';
import { useTheme } from '../theme';

interface Props {
    visible: boolean;
    title?: string;
    onClose: () => void;
    children: React.ReactNode;
    /** Fraction of screen height the panel may grow to (default 0.8). */
    maxHeightRatio?: number;
}

const SCREEN_H = Dimensions.get('window').height;

export const BottomSheet: React.FC<Props> = ({
    visible,
    title,
    onClose,
    children,
    maxHeightRatio = 0.8,
}) => {
    const { theme } = useTheme();
    const insets = useSafeAreaInsets();
    const translateY = useRef(new Animated.Value(SCREEN_H)).current;
    const backdrop = useRef(new Animated.Value(0)).current;

    useEffect(() => {
        if (visible) {
            Animated.parallel([
                Animated.spring(translateY, { toValue: 0, useNativeDriver: true, speed: 18, bounciness: 4 }),
                Animated.timing(backdrop, { toValue: 1, duration: 180, useNativeDriver: true }),
            ]).start();
        } else {
            translateY.setValue(SCREEN_H);
            backdrop.setValue(0);
        }
    }, [visible, translateY, backdrop]);

    return (
        <Modal visible={visible} transparent animationType="none" statusBarTranslucent onRequestClose={onClose}>
            <View style={StyleSheet.absoluteFill}>
                <Pressable style={StyleSheet.absoluteFill} onPress={onClose}>
                    <Animated.View
                        style={[
                            StyleSheet.absoluteFill,
                            { backgroundColor: '#000', opacity: backdrop.interpolate({ inputRange: [0, 1], outputRange: [0, 0.45] }) },
                        ]}
                    />
                </Pressable>

                <Animated.View
                    style={[
                        styles.panel,
                        {
                            backgroundColor: theme.colors.surface,
                            paddingBottom: insets.bottom + 12,
                            maxHeight: SCREEN_H * maxHeightRatio,
                            transform: [{ translateY }],
                        },
                    ]}>
                    <View style={[styles.handle, { backgroundColor: theme.colors.border }]} />
                    {title != null && (
                        <View style={styles.titleRow}>
                            <Text style={[styles.title, { color: theme.colors.text }]}>{title}</Text>
                            <TouchableOpacity onPress={onClose} hitSlop={10} style={[styles.closeBtn, { backgroundColor: theme.colors.background }]}>
                                <X size={18} color={theme.colors.textSecondary} />
                            </TouchableOpacity>
                        </View>
                    )}
                    {children}
                </Animated.View>
            </View>
        </Modal>
    );
};

const styles = StyleSheet.create({
    panel: {
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 0,
        borderTopLeftRadius: 24,
        borderTopRightRadius: 24,
        paddingTop: 10,
        paddingHorizontal: 16,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: -4 },
        shadowOpacity: 0.18,
        shadowRadius: 20,
        elevation: 24,
    },
    handle: {
        alignSelf: 'center',
        width: 40,
        height: 5,
        borderRadius: 3,
        marginBottom: 10,
    },
    titleRow: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 12,
        paddingHorizontal: 2,
    },
    title: { fontSize: 18, fontWeight: '700' },
    closeBtn: {
        width: 30,
        height: 30,
        borderRadius: 15,
        alignItems: 'center',
        justifyContent: 'center',
    },
});

export default BottomSheet;
