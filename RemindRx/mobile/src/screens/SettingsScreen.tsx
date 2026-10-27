/** Profile name, reminder health, test reminders, backup and data reset. */
import React, { useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { BellRing, Bell, Download, Lock, Trash2, Upload } from 'lucide-react-native';
import RNFS from 'react-native-fs';
import { errorCodes, isErrorWithCode, keepLocalCopy, pick, saveDocuments, types } from '@react-native-documents/picker';
import { backupFileName, makeBackup, parseBackup } from '@shared/index';
import { useStore } from '../state/Store';
import { colors } from '../theme';
import { Card, SectionTitle, useToast } from '../components/ui';
import { HealthCard } from '../components/HealthCard';
import ReminderService from '../reminders/ReminderService';

const Row: React.FC<{ icon: React.ReactNode; title: string; sub: string; onPress(): void; danger?: boolean; testID?: string }> = ({ icon, title, sub, onPress, danger, testID }) => (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.row, pressed && { backgroundColor: colors.secondary }]} testID={testID}>
        <View style={[styles.rowIcon, { backgroundColor: danger ? colors.accentTint : colors.primaryTint }]}>{icon}</View>
        <View style={{ flex: 1 }}>
            <Text style={[styles.rowTitle, danger && { color: colors.error }]}>{title}</Text>
            <Text style={styles.rowSub}>{sub}</Text>
        </View>
    </Pressable>
);

export const SettingsScreen: React.FC = () => {
    const insets = useSafeAreaInsets();
    const store = useStore();
    const toast = useToast();
    const [name, setName] = useState(store.settings.userName ?? '');

    const exportData = async () => {
        try {
            const fileName = backupFileName();
            const path = `${RNFS.CachesDirectoryPath}/${fileName}`;
            await RNFS.writeFile(path, JSON.stringify(makeBackup(store), null, 2), 'utf8');
            const [res] = await saveDocuments({ sourceUris: [`file://${path}`], mimeType: 'application/json', fileName });
            toast.show(res.error ? `Export failed: ${res.error}` : `Saved ${res.name ?? fileName}`);
        } catch (e) {
            if (isErrorWithCode(e) && e.code === errorCodes.OPERATION_CANCELED) return;
            toast.show('Could not export the backup.');
        }
    };

    const importData = async () => {
        try {
            const [file] = await pick({ type: [types.json, types.plainText, types.allFiles] });
            const [copy] = await keepLocalCopy({ files: [{ uri: file.uri, fileName: file.name ?? 'backup.json' }], destination: 'cachesDirectory' });
            if (copy.status !== 'success') { toast.show('Could not read that file.'); return; }
            const parsed = parseBackup(await RNFS.readFile(decodeURI(copy.localUri.replace('file://', '')), 'utf8'));
            if (!parsed.ok) { Alert.alert('Import failed', parsed.error); return; }
            const { meds, doses } = parsed.data;
            Alert.alert(
                'Import backup',
                `${meds.length} medicine${meds.length === 1 ? '' : 's'} and ${doses.length} dose record${doses.length === 1 ? '' : 's'}. Merge with what’s on this phone, or replace it?`,
                [
                    { text: 'Cancel', style: 'cancel' },
                    { text: 'Replace', style: 'destructive', onPress: async () => { await store.importData(parsed.data, 'replace'); toast.show('Backup restored: reminders re-armed'); } },
                    { text: 'Merge', onPress: async () => { await store.importData(parsed.data, 'merge'); toast.show('Backup merged: reminders re-armed'); } },
                ],
            );
        } catch (e) {
            if (isErrorWithCode(e) && e.code === errorCodes.OPERATION_CANCELED) return;
            toast.show('Could not import the backup.');
        }
    };

    const wipe = () =>
        Alert.alert('Erase all data?', 'Every medicine, reminder and dose record on this phone will be deleted. Export a backup first if you might need it.', [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Erase', style: 'destructive', onPress: async () => { await store.wipe(); setName(''); toast.show('All data erased'); } },
        ]);

    const test = async (mode: 'notification' | 'alarm') => {
        await ReminderService.testReminder(mode, 10);
        toast.show(`Test ${mode} in 10 s: lock the phone or close the app to try it`);
    };

    return (
        <View style={{ flex: 1, backgroundColor: colors.background, paddingTop: insets.top }}>
            <ScrollView contentContainerStyle={{ paddingTop: 12, paddingHorizontal: 18, paddingBottom: 120 }} keyboardShouldPersistTaps="handled">
                <Text style={styles.title}>Settings</Text>

                <SectionTitle>Profile</SectionTitle>
                <Card>
                    <Text style={styles.label}>Your name (for the greeting)</Text>
                    <TextInput
                        value={name}
                        onChangeText={setName}
                        onEndEditing={() => store.setSettings({ userName: name.trim() || undefined })}
                        placeholder="Optional"
                        placeholderTextColor={colors.textSecondary}
                        style={styles.input}
                        maxLength={40}
                        testID="user-name"
                    />
                </Card>

                <SectionTitle>Reminder health</SectionTitle>
                <HealthCard />
                <Card style={{ marginTop: 12, padding: 6 }}>
                    <Row icon={<Bell size={18} color={colors.primary} />} title="Send a test notification" sub="Arrives in 10 seconds" onPress={() => test('notification')} testID="test-notification" />
                    <Row icon={<BellRing size={18} color={colors.accent} />} title="Send a test alarm" sub="Full-screen ringer in 10 seconds" onPress={() => test('alarm')} testID="test-alarm" />
                </Card>

                <SectionTitle>Backup</SectionTitle>
                <Card style={{ padding: 6 }}>
                    <Row icon={<Download size={18} color={colors.primary} />} title="Export backup" sub="Save a .json file (works with the RemindRx website too)" onPress={exportData} testID="export" />
                    <Row icon={<Upload size={18} color={colors.primary} />} title="Import backup" sub="Restore or merge from a .json file" onPress={importData} testID="import" />
                    <Row icon={<Trash2 size={18} color={colors.error} />} title="Erase all data" sub="Delete everything on this phone" onPress={wipe} danger testID="wipe" />
                </Card>

                <View style={styles.privacy}>
                    <Lock size={16} color={colors.primaryDark} />
                    <Text style={styles.privacyText}>RemindRx works fully offline. Your medicines and history never leave this phone unless you export them.</Text>
                </View>
            </ScrollView>
            {toast.node}
        </View>
    );
};

const styles = StyleSheet.create({
    title: { fontSize: 26, fontWeight: '800', color: colors.text },
    label: { fontSize: 13, fontWeight: '700', color: colors.textSecondary, marginBottom: 8 },
    input: { backgroundColor: colors.secondary, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, color: colors.text },
    row: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 14 },
    rowIcon: { width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
    rowTitle: { fontSize: 15, fontWeight: '700', color: colors.text },
    rowSub: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
    privacy: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', backgroundColor: colors.primaryTint, borderRadius: 16, padding: 14, marginTop: 22 },
    privacyText: { flex: 1, fontSize: 13, color: colors.primaryDark, lineHeight: 19, fontWeight: '600' },
});
