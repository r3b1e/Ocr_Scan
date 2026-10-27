/**
 * RemindRx: offline medication reminders. No backend, no account; data
 * lives in AsyncStorage and reminders are armed on-device with notifee.
 */
import React, { useEffect } from 'react';
import { AppState, StatusBar, StyleSheet, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { NavigationContainer, DefaultTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { CalendarCheck, ChartColumn, Pill, Settings } from 'lucide-react-native';
import notifee from '@notifee/react-native';
import { StoreProvider } from './src/state/Store';
import { RootStackParamList, navigationRef, openAlarm } from './src/navigation';
import { setShowOverLockScreen } from './src/reminders/permissions';
import ReminderService, { onAlarm, ringingAlarm } from './src/reminders/ReminderService';
import { TodayScreen } from './src/screens/TodayScreen';
import { MedicationsScreen } from './src/screens/MedicationsScreen';
import { HistoryScreen } from './src/screens/HistoryScreen';
import { SettingsScreen } from './src/screens/SettingsScreen';
import { AddMedicationScreen } from './src/screens/AddMedicationScreen';
import { AlarmScreen } from './src/screens/AlarmScreen';
import { colors } from './src/theme';

const Stack = createNativeStackNavigator<RootStackParamList>();
const Tab = createBottomTabNavigator();

const navTheme = { ...DefaultTheme, colors: { ...DefaultTheme.colors, background: colors.background, primary: colors.primary, card: colors.surface } };

const Tabs = () => (
    <Tab.Navigator
        screenOptions={({ route }) => ({
            headerShown: false,
            tabBarActiveTintColor: colors.primary,
            tabBarInactiveTintColor: '#94A3B8',
            tabBarStyle: styles.tabBar,
            tabBarLabelStyle: styles.tabLabel,
            tabBarIcon: ({ color, focused }) => {
                const Icon = { Today: CalendarCheck, Medications: Pill, History: ChartColumn, Settings }[route.name] ?? Pill;
                return (
                    <View style={[styles.tabIcon, focused && { backgroundColor: colors.primaryTint }]}>
                        <Icon size={21} color={color} strokeWidth={focused ? 2.5 : 2} />
                    </View>
                );
            },
        })}>
        <Tab.Screen name="Today" component={TodayScreen} />
        <Tab.Screen name="Medications" component={MedicationsScreen} />
        <Tab.Screen name="History" component={HistoryScreen} />
        <Tab.Screen name="Settings" component={SettingsScreen} />
    </Tab.Navigator>
);

/**
 * Open the ringer for an alarm that fired while the app was closed or in the
 * background. Checked again a moment later: the full-screen intent can bring
 * the app forward just before the notification is in the shade. If nothing is
 * ringing by then, drop back behind the lock screen (MainActivity may have
 * shown the app over it for an alarm that has since been dismissed).
 */
const showRingingAlarm = () => {
    const check = () => ringingAlarm().then(d => (d ? openAlarm(d) : false));
    check();
    setTimeout(async () => {
        if (!(await check()) && navigationRef.getCurrentRoute()?.name !== 'Alarm') setShowOverLockScreen(false);
    }, 1200);
};

export default function App() {
    useEffect(() => {
        (async () => {
            await ReminderService.createChannels().catch(() => {});
            await notifee.requestPermission().catch(() => {});
        })();
        const offFg = ReminderService.registerForegroundHandler();
        const offAlarm = onAlarm(data => openAlarm(data));
        const sub = AppState.addEventListener('change', s => { if (s === 'active') showRingingAlarm(); });
        return () => { offFg(); offAlarm(); sub.remove(); };
    }, []);

    return (
        <SafeAreaProvider>
            <StatusBar barStyle="dark-content" backgroundColor={colors.background} />
            <StoreProvider>
                <NavigationContainer ref={navigationRef} theme={navTheme} onReady={showRingingAlarm}>
                    <Stack.Navigator screenOptions={{ headerShown: false }}>
                        <Stack.Screen name="Tabs" component={Tabs} />
                        <Stack.Screen name="AddMedication" component={AddMedicationScreen} options={{ animation: 'slide_from_bottom' }} />
                        <Stack.Screen name="Alarm" component={AlarmScreen} options={{ presentation: 'fullScreenModal', animation: 'fade', gestureEnabled: false }} />
                    </Stack.Navigator>
                </NavigationContainer>
            </StoreProvider>
        </SafeAreaProvider>
    );
}

const styles = StyleSheet.create({
    tabBar: { height: 68, paddingTop: 6, paddingBottom: 8, borderTopColor: colors.border, backgroundColor: colors.surface },
    tabLabel: { fontSize: 11, fontWeight: '700' },
    tabIcon: { width: 44, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
});
