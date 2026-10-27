/**
 * Add / Edit Medication form, ported from HealthApp's AddMedicationScreen.
 *
 * Saves to the on-device store (no backend). Every save re-arms reminders.
 * Unlike HealthApp, dates and frequency stay editable: past dose logs keep
 * their own scheduled time, so an edit only changes future doses.
 * Dates and times use the native Android Material pickers.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    Alert,
    Platform,
    Pressable,
    ScrollView,
    StyleSheet,
    Switch,
    Text,
    TextInput,
    TouchableOpacity,
    View,
} from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { DateTimePickerAndroid } from '@react-native-community/datetimepicker';
import DatePickerSheet from '../components/DatePickerSheet';
import {
    ChevronDown,
    ChevronLeft,
    Clock,
    AlarmClock,
    Bell,
    BellRing,
    CircleAlert,
    Lock,
    Minus,
    Plus,
    Trash2,
    Utensils,
} from 'lucide-react-native';
import { useTheme } from '../theme';
import { useStore } from '../state/Store';
import ReminderService from '../reminders/ReminderService';
import { getReminderHealth, fixHealth } from '../reminders/permissions';
import { iconForType } from '../icons';
import { LEAD_OPTIONS, MAX_COURSE_DAYS, MEAL_RELATIONS } from '@shared/catalog';
import {
    buildMedication,
    createEmptyDraft,
    addDays,
    currentMonthStart,
    daysBetween,
    draftFromMedication,
    formatDateShort,
    formatTime,
    frequencySummary,
    hasErrors,
    reconcileUnit,
    resizeTimes,
    startOfDay,
    timesPerDayFor,
    validateDraft,
} from '@shared/logic';
import {
    DoseUnit,
    FrequencyConfig,
    FrequencyType,
    Medication,
    MedicationDraft,
    MedicationStatus,
    MedicationType,
} from '@shared/types';
import TypePickerSheet from '../components/TypePickerSheet';
import UnitPickerSheet from '../components/UnitPickerSheet';
import FrequencyPickerSheet from '../components/FrequencyPickerSheet';
import ScheduleTimeSheet from '../components/ScheduleTimeSheet';
import TimePickerSheet from '../components/TimePickerSheet';

type SheetKey = 'type' | 'unit' | 'frequency' | 'time' | null;

export const AddMedicationScreen: React.FC = () => {
    const { theme } = useTheme();
    const insets = useSafeAreaInsets();
    const navigation = useNavigation<any>();
    const route = useRoute<any>();
    const store = useStore();
    const editing: Medication | undefined = route.params?.medication;
    const datesLocked = false;

    const [draft, setDraft] = useState<MedicationDraft>(() =>
        editing ? draftFromMedication(editing) : createEmptyDraft(),
    );
    const [sheet, setSheet] = useState<SheetKey>(null);
    const [submitted, setSubmitted] = useState(false);
    const [saving, setSaving] = useState(false);

    // Transient note (e.g. when a type change resets the dose unit).
    const [note, setNote] = useState<string | null>(null);
    const noteTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const flashNote = (msg: string) => {
        setNote(msg);
        if (noteTimer.current) clearTimeout(noteTimer.current);
        noteTimer.current = setTimeout(() => setNote(null), 2800);
    };

    const patch = (p: Partial<MedicationDraft>) => setDraft(d => ({ ...d, ...p }));

    const otherNames = useMemo(
        () => store.meds.filter(m => m.status === MedicationStatus.Active && m.id !== editing?.id).map(m => m.name),
        [store.meds, editing?.id],
    );
    const validation = useMemo(() => validateDraft(draft, { existingActiveNames: otherNames }), [draft, otherNames]);
    const errors = validation.errors;
    const warnings = validation.warnings;
    const showErr = (key: string) => (submitted ? errors[key] : undefined);
    const datesInvalid = daysBetween(draft.startDate, draft.endDate) < 0;

    // ── Field handlers ──────────────────────────────────────────────────────

    const onSelectType = (type: MedicationType) => {
        const { unit, changed } = reconcileUnit(type, draft.doseUnit);
        // Only switch focus — keep the picker open; the user dismisses it.
        patch({ type, doseUnit: unit });
        if (changed) flashNote(`Dose unit set to "${unit}" for ${type}.`);
    };

    const onNameChange = (name: string) => patch({ name });

    const onSelectUnit = (doseUnit: DoseUnit) => {
        patch({ doseUnit });
        setSheet(null);
    };

    const onApplyFrequency = (type: FrequencyType, config: FrequencyConfig) => {
        const required = timesPerDayFor(type, config);
        const scheduleTimes = resizeTimes(draft.scheduleTimes, required);
        patch({
            frequencyType: type,
            frequencyConfig: { ...config, timesPerDay: required },
            scheduleTimes,
        });
        setSheet(null);
    };

    const setQuantity = (n: number) => {
        const clamped = Math.max(1, Math.min(999, n));
        patch({ quantityPerDose: String(clamped) });
    };

    // ── Native date picker (Material) ───────────────────────────────────────

    const [datePicker, setDatePicker] = useState<'start' | 'end' | null>(null);

    const applyDate = (which: 'start' | 'end', date: Date) => {
        const day = startOfDay(date);
        if (which === 'start') patch({ startDate: day });
        else patch({ endDate: day });
    };

    const openDatePicker = (which: 'start' | 'end') => {
        if (Platform.OS !== 'android') {
            setDatePicker(which);
            return;
        }
        DateTimePickerAndroid.open({
            value: which === 'start' ? draft.startDate : draft.endDate,
            mode: 'date',
            minimumDate: currentMonthStart(),
            maximumDate: addDays(new Date(), MAX_COURSE_DAYS),
            onChange: (event, date) => {
                if (event.type === 'set' && date) {
                    applyDate(which, date);
                }
            },
        });
    };

    // ── Time picker ─────────────────────────────────────────────────────────
    // Android uses the native Material clock; iOS (where DateTimePickerAndroid is
    // a no-op) uses our themed TimePickerSheet so the time is actually pickable.
    const [timeSlot, setTimeSlot] = useState<number | null>(null);

    const applyTimeToSlot = (slot: number, hour: number, minute: number) => {
        setDraft(d => {
            const next = d.scheduleTimes.slice();
            next[slot] = { hour, minute };
            return { ...d, scheduleTimes: next };
        });
    };

    const openTimePicker = (slot: number) => {
        if (Platform.OS !== 'android') {
            setTimeSlot(slot);
            return;
        }
        const t = draft.scheduleTimes[slot] ?? { hour: 9, minute: 0 };
        const value = new Date();
        value.setHours(t.hour, t.minute, 0, 0);
        DateTimePickerAndroid.open({
            value,
            mode: 'time',
            is24Hour: false,
            onChange: (event, date) => {
                if (event.type === 'set' && date) {
                    applyTimeToSlot(slot, date.getHours(), date.getMinutes());
                }
            },
        });
    };

    const onScheduleTimePress = () => {
        const required = timesPerDayFor(draft.frequencyType, draft.frequencyConfig);
        // Keep the slot count in sync before editing.
        if (draft.scheduleTimes.length !== required) {
            patch({ scheduleTimes: resizeTimes(draft.scheduleTimes, required) });
        }
        if (required === 1) openTimePicker(0);
        else setSheet('time');
    };

    const onDone = async () => {
        setSubmitted(true);
        if (hasErrors(validation)) {
            const first = Object.values(errors)[0];
            if (first) flashNote(first);
            return;
        }
        // Never save a dead alarm: without exact-alarm permission the trigger
        // can't be armed, so fall back to a notification reminder.
        let draftToSave = draft;
        if (draft.remindersEnabled && draft.reminderMode === 'alarm') {
            const h = await getReminderHealth();
            if (!h.notifications || !h.exactAlarm) {
                draftToSave = { ...draft, reminderMode: 'notification' };
                flashNote('Alarm permission is off: saved as a notification reminder instead.');
            }
        }
        setSaving(true);
        try {
            await store.saveMed(buildMedication(draftToSave));
            navigation.goBack();
        } catch (e: any) {
            flashNote(e?.message || 'Could not save medication. Please try again.');
            setSaving(false);
        }
    };

    const onDelete = () => {
        if (!editing) return;
        Alert.alert(
            'Delete medication',
            `Remove "${editing.name}"? Its reminders stop. Past doses stay in your history.`,
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Delete',
                    style: 'destructive',
                    onPress: async () => {
                        await store.setStatus(editing.id, MedicationStatus.Deleted);
                        navigation.goBack();
                    },
                },
            ],
        );
    };

    /** Alarm mode needs notifications + exact alarms; ask before selecting it. */
    const ensureAlarmPermissions = async (): Promise<boolean> => {
        let h = await getReminderHealth();
        if (!h.notifications) { await fixHealth('notifications'); h = await getReminderHealth(); }
        if (!h.notifications) return false;
        if (!h.exactAlarm) { await fixHealth('exactAlarm'); return false; }
        if (!h.fullScreen) flashNote('Tip: allow full-screen alarms in Settings → Reminder health.');
        return true;
    };

    // ── Render helpers ──────────────────────────────────────────────────────

    const TypeIcon = iconForType(draft.type);
    const firstTime = draft.scheduleTimes[0];
    const requiredTimes = timesPerDayFor(draft.frequencyType, draft.frequencyConfig);
    const quantity = Math.max(1, Math.floor(Number(draft.quantityPerDose) || 1));

    const card = [styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }];

    const InvalidIcon = () =>
        datesInvalid ? <CircleAlert size={18} color={theme.colors.error} /> : null;

    return (
        <View style={{ flex: 1, backgroundColor: theme.colors.background, paddingTop: insets.top }}>
            {/* Header */}
            <View style={styles.header}>
                <TouchableOpacity onPress={() => navigation.goBack()} style={{ padding: 6 }} activeOpacity={0.7}>
                    <ChevronLeft size={26} color={theme.colors.text} />
                </TouchableOpacity>
                <Text style={[styles.headerTitle, { color: theme.colors.text }]}>
                    {editing ? 'Edit Medication' : 'Add Medication'}
                </Text>
                <View style={{ flex: 1 }} />
                {editing && (
                    <TouchableOpacity onPress={onDelete} style={[styles.trashBtn, { backgroundColor: theme.colors.error + '14' }]} activeOpacity={0.7}>
                        <Trash2 size={20} color={theme.colors.error} />
                    </TouchableOpacity>
                )}
            </View>

            <ScrollView
                showsVerticalScrollIndicator={false}
                keyboardShouldPersistTaps="handled"
                contentContainerStyle={{ paddingHorizontal: 18, paddingTop: 6, paddingBottom: 24 }}>

                {/* Pill's Name */}
                <View style={card}>
                    <Text style={[styles.cardLabel, { color: theme.colors.text }]}>Medicine name</Text>
                    <TextInput
                        value={draft.name}
                        onChangeText={onNameChange}
                        placeholder="e.g. Metformin 500"
                        testID="med-name"
                        placeholderTextColor={theme.colors.textSecondary}
                        maxLength={80}
                        style={[
                            styles.nameInput,
                            {
                                backgroundColor: theme.colors.secondary,
                                color: theme.colors.text,
                                borderColor: showErr('name') ? theme.colors.error : 'transparent',
                            },
                        ]}
                    />
                    {showErr('name') && <Text style={[styles.err, { color: theme.colors.error }]}>{showErr('name')}</Text>}
                    {!showErr('name') && warnings.name && (
                        <Text style={[styles.warn, { color: theme.colors.warning }]}>{warnings.name}</Text>
                    )}
                </View>

                {/* Type */}
                <TouchableOpacity activeOpacity={0.8} onPress={() => setSheet('type')} style={[...card, styles.rowCard]}>
                    <View style={styles.rowLeft}>
                        <View style={[styles.typeIcon, { backgroundColor: theme.colors.primary + '14' }]}>
                            <TypeIcon size={20} color={theme.colors.primary} strokeWidth={2} />
                        </View>
                        <Text style={[styles.rowValueStrong, { color: theme.colors.text }]}>{draft.type}</Text>
                    </View>
                    <ChevronDown size={20} color={theme.colors.textSecondary} />
                </TouchableOpacity>

                {/* Dates (locked in edit mode — a course's dates can't change) */}
                <View style={card}>
                    <TouchableOpacity activeOpacity={datesLocked ? 1 : 0.7} disabled={datesLocked} onPress={() => openDatePicker('start')} style={styles.dateRow}>
                        <Text style={[styles.rowLabel, { color: theme.colors.text }]}>Start Date</Text>
                        <View style={styles.rowLeft}>
                            {!datesLocked && <InvalidIcon />}
                            <Text style={[styles.rowValueAccent, { color: datesLocked ? theme.colors.textSecondary : datesInvalid ? theme.colors.error : theme.colors.primary }]}>
                                {formatDateShort(draft.startDate)}
                            </Text>
                            {datesLocked
                                ? <Lock size={15} color={theme.colors.textSecondary} />
                                : <ChevronDown size={18} color={theme.colors.textSecondary} />}
                        </View>
                    </TouchableOpacity>
                    <View style={[styles.hr, { backgroundColor: theme.colors.border }]} />
                    <TouchableOpacity activeOpacity={datesLocked ? 1 : 0.7} disabled={datesLocked} onPress={() => openDatePicker('end')} style={styles.dateRow}>
                        <Text style={[styles.rowLabel, { color: theme.colors.text }]}>End Date</Text>
                        <View style={styles.rowLeft}>
                            {!datesLocked && <InvalidIcon />}
                            <Text style={[styles.rowValueAccent, { color: datesLocked ? theme.colors.textSecondary : datesInvalid ? theme.colors.error : theme.colors.primary }]}>
                                {formatDateShort(draft.endDate)}
                            </Text>
                            {datesLocked
                                ? <Lock size={15} color={theme.colors.textSecondary} />
                                : <ChevronDown size={18} color={theme.colors.textSecondary} />}
                        </View>
                    </TouchableOpacity>
                </View>
                {datesLocked && (
                    <Text style={[styles.helper, { color: theme.colors.textSecondary }]}>Dates can’t be changed after creating</Text>
                )}
                {!datesLocked && datesInvalid && (
                    <Text style={[styles.errStandalone, { color: theme.colors.error }]}>
                        Start date must be on or before the end date
                    </Text>
                )}

                {/* Pills + Dose */}
                <View style={styles.twoCol}>
                    {/* Pills stepper */}
                    <View style={[...card, styles.colCard]}>
                        <Text style={[styles.rowLabel, { color: theme.colors.text }]}>Pills</Text>
                        <View style={styles.stepperRow}>
                            <Pressable
                                onPress={() => setQuantity(quantity - 1)}
                                disabled={quantity <= 1}
                                style={({ pressed }) => [
                                    styles.stepBtn,
                                    {
                                        borderColor: theme.colors.border,
                                        backgroundColor: pressed ? theme.colors.primary + '0A' : 'transparent',
                                        opacity: quantity <= 1 ? 0.35 : 1,
                                    },
                                ]}>
                                <Minus size={18} color={theme.colors.text} />
                            </Pressable>
                            <Text style={[styles.qtyValue, { color: theme.colors.text }]}>{quantity}</Text>
                            <Pressable
                                onPress={() => setQuantity(quantity + 1)}
                                style={({ pressed }) => [
                                    styles.stepBtn,
                                    {
                                        borderColor: theme.colors.border,
                                        backgroundColor: pressed ? theme.colors.primary + '0A' : 'transparent',
                                    },
                                ]}>
                                <Plus size={18} color={theme.colors.text} />
                            </Pressable>
                        </View>
                    </View>

                    {/* Dose unit */}
                    <TouchableOpacity activeOpacity={0.8} onPress={() => setSheet('unit')} style={[...card, styles.colCard]}>
                        <Text style={[styles.rowLabel, { color: theme.colors.text }]}>Dose</Text>
                        <View style={styles.doseRow}>
                            <Text style={[styles.doseValue, { color: theme.colors.textSecondary }]} numberOfLines={1}>{draft.doseUnit}</Text>
                            <ChevronDown size={18} color={theme.colors.textSecondary} />
                        </View>
                    </TouchableOpacity>
                </View>
                {showErr('quantity') && <Text style={[styles.errStandalone, { color: theme.colors.error }]}>{showErr('quantity')}</Text>}

                {/* Set Frequency (locked in edit mode — changing it would reshape the schedule) */}
                <TouchableOpacity activeOpacity={datesLocked ? 1 : 0.8} disabled={datesLocked} onPress={() => setSheet('frequency')} style={[...card, styles.rowCard]}>
                    <Text style={[styles.rowLabel, { color: theme.colors.text }]}>Set Frequency</Text>
                    <View style={styles.rowLeft}>
                        <Text style={[styles.rowValueAccent, { color: datesLocked ? theme.colors.textSecondary : theme.colors.primary }]} numberOfLines={1}>
                            {frequencySummary(draft.frequencyType, draft.frequencyConfig)}
                        </Text>
                        {datesLocked
                            ? <Lock size={15} color={theme.colors.textSecondary} />
                            : <ChevronDown size={18} color={theme.colors.textSecondary} />}
                    </View>
                </TouchableOpacity>
                {showErr('frequency') && <Text style={[styles.errStandalone, { color: theme.colors.error }]}>{showErr('frequency')}</Text>}

                {/* Schedule Time */}
                <TouchableOpacity activeOpacity={0.8} onPress={onScheduleTimePress} style={[...card, styles.rowCard]}>
                    <Text style={[styles.rowLabel, { color: theme.colors.text }]}>Schedule Time</Text>
                    <View style={styles.rowLeft}>
                        <AlarmClock size={18} color={theme.colors.primary} />
                        <Text style={[styles.rowValueAccent, { color: theme.colors.primary }]}>
                            {firstTime ? formatTime(firstTime) : '--'}
                        </Text>
                        {requiredTimes > 1 && (
                            <View style={[styles.countPill, { backgroundColor: theme.colors.primary + '1F' }]}>
                                <Text style={{ fontSize: 11, fontWeight: '700', color: theme.colors.primary }}>+{requiredTimes - 1}</Text>
                            </View>
                        )}
                        <ChevronDown size={18} color={theme.colors.textSecondary} />
                    </View>
                </TouchableOpacity>
                {requiredTimes > 1 && (
                    <Text style={[styles.helper, { color: theme.colors.textSecondary }]}>
                        {requiredTimes} doses/day · {draft.scheduleTimes.map(formatTime).join(' · ')}
                    </Text>
                )}
                {showErr('times') && <Text style={[styles.errStandalone, { color: theme.colors.error }]}>{showErr('times')}</Text>}
                {!showErr('times') && warnings.times && (
                    <Text style={[styles.warnStandalone, { color: theme.colors.warning }]}>{warnings.times}</Text>
                )}

                {/* Reminders */}
                <View style={card}>
                    <View style={styles.rowCard}>
                        <Text style={[styles.rowLabel, { color: theme.colors.text }]}>Reminders</Text>
                        <Switch
                            value={draft.remindersEnabled}
                            onValueChange={v => patch({ remindersEnabled: v })}
                            trackColor={{ true: theme.colors.primary, false: theme.colors.border }}
                            thumbColor="#FFFFFF"
                        />
                    </View>
                    {draft.remindersEnabled && (
                        <>
                            <View style={[styles.hr, { backgroundColor: theme.colors.border }]} />
                            <Text style={[styles.subLabel, { color: theme.colors.textSecondary }]}>Alert type</Text>
                            <View style={styles.modeRow}>
                                {([
                                    { key: 'notification', label: 'Notification', Icon: Bell, hint: 'A tap-able reminder' },
                                    { key: 'alarm', label: 'Alarm', Icon: BellRing, hint: 'Rings full-screen' },
                                ] as const).map(opt => {
                                    const active = draft.reminderMode === opt.key;
                                    return (
                                        <TouchableOpacity
                                            key={opt.key}
                                            activeOpacity={0.85}
                                            onPress={async () => {
                                                // Alarm mode needs exact-alarm (+ full-screen) OS permission,
                                                // else the on-device alarm silently never fires. Block the
                                                // selection until granted; Notification mode has no wall.
                                                if (opt.key === 'alarm') {
                                                    const ok = await ensureAlarmPermissions();
                                                    if (!ok) {
                                                        flashNote("Alarm reminders need the 'Alarms & reminders' permission. Allow it, then choose Alarm again.");
                                                        return;
                                                    }
                                                }
                                                patch({ reminderMode: opt.key });
                                            }}
                                            style={[
                                                styles.modeOpt,
                                                {
                                                    backgroundColor: active ? theme.colors.primary + '14' : theme.colors.background,
                                                    borderColor: active ? theme.colors.primary : theme.colors.border,
                                                    borderWidth: active ? 2 : 1,
                                                },
                                            ]}>
                                            <opt.Icon size={22} color={active ? theme.colors.primary : theme.colors.textSecondary} strokeWidth={2.2} />
                                            <Text style={[styles.modeLabel, { color: active ? theme.colors.primary : theme.colors.text }]}>{opt.label}</Text>
                                            <Text style={[styles.modeHint, { color: theme.colors.textSecondary }]}>{opt.hint}</Text>
                                        </TouchableOpacity>
                                    );
                                })}
                            </View>
                            <Text style={[styles.subLabel, { color: theme.colors.textSecondary, marginTop: 16 }]}>Remind me early</Text>
                            <View style={styles.chipRow}>
                                {LEAD_OPTIONS.map(min => {
                                    const active = draft.reminderLeadMinutes === min;
                                    return (
                                        <TouchableOpacity key={min} activeOpacity={0.85} onPress={() => patch({ reminderLeadMinutes: min })}
                                            style={[styles.chip, { backgroundColor: active ? theme.colors.primary : theme.colors.background, borderColor: active ? theme.colors.primary : theme.colors.border }]}>
                                            <Text style={[styles.chipText, { color: active ? '#FFFFFF' : theme.colors.text }]}>{min === 0 ? 'On time' : `${min} min`}</Text>
                                        </TouchableOpacity>
                                    );
                                })}
                            </View>
                        </>
                    )}
                </View>

                {/* With food */}
                <View style={card}>
                    <View style={[styles.rowLeft, { marginBottom: 12 }]}>
                        <Utensils size={18} color={theme.colors.primary} />
                        <Text style={[styles.rowLabel, { color: theme.colors.text }]}>Food</Text>
                    </View>
                    <View style={styles.chipRow}>
                        {MEAL_RELATIONS.map(opt => {
                            const active = (draft.mealRelation ?? 'any') === opt.value;
                            return (
                                <TouchableOpacity key={opt.value} activeOpacity={0.85} onPress={() => patch({ mealRelation: opt.value })}
                                    style={[styles.chip, { backgroundColor: active ? theme.colors.primary : theme.colors.background, borderColor: active ? theme.colors.primary : theme.colors.border }]}>
                                    <Text style={[styles.chipText, { color: active ? '#FFFFFF' : theme.colors.text }]}>{opt.label}</Text>
                                </TouchableOpacity>
                            );
                        })}
                    </View>
                </View>
            </ScrollView>

            {/* Transient note banner */}
            {note && (
                <View style={[styles.note, { backgroundColor: theme.colors.text, bottom: insets.bottom + 92 }]}>
                    <Clock size={14} color="#FFFFFF" />
                    <Text style={styles.noteText} numberOfLines={2}>{note}</Text>
                </View>
            )}

            {/* Done */}
            <View style={[styles.footer, { paddingBottom: insets.bottom + 12, backgroundColor: theme.colors.background, borderTopColor: theme.colors.border }]}>
                <TouchableOpacity
                    activeOpacity={0.9}
                    onPress={onDone}
                    disabled={saving}
                    testID="save-med"
                    style={[styles.doneBtn, { backgroundColor: theme.colors.primary }, saving && { opacity: 0.8 }]}>
                    <Text style={styles.doneText}>{saving ? 'Saving…' : editing ? 'Save Changes' : 'Save Medication'}</Text>
                </TouchableOpacity>
            </View>

            {/* Sheets — only the active one is mounted at a time. */}
            {sheet === 'type' && (
                <TypePickerSheet visible selected={draft.type} onClose={() => setSheet(null)} onSelect={onSelectType} />
            )}
            {sheet === 'unit' && (
                <UnitPickerSheet visible type={draft.type} selected={draft.doseUnit} onClose={() => setSheet(null)} onSelect={onSelectUnit} />
            )}
            {sheet === 'frequency' && (
                <FrequencyPickerSheet visible type={draft.frequencyType} config={draft.frequencyConfig} onClose={() => setSheet(null)} onApply={onApplyFrequency} />
            )}
            {sheet === 'time' && (
                <ScheduleTimeSheet
                    visible
                    times={draft.scheduleTimes}
                    onClose={() => setSheet(null)}
                    onEditSlot={openTimePicker}
                />
            )}

            {/* iOS / cross-platform themed clock picker (Android uses the native clock). */}
            {timeSlot !== null && (
                <TimePickerSheet
                    visible
                    hour={draft.scheduleTimes[timeSlot]?.hour ?? 9}
                    minute={draft.scheduleTimes[timeSlot]?.minute ?? 0}
                    onClose={() => setTimeSlot(null)}
                    onConfirm={t => {
                        applyTimeToSlot(timeSlot, t.hour, t.minute);
                        setTimeSlot(null);
                    }}
                />
            )}

            {/* iOS / cross-platform themed date picker (Android uses the native dialog). */}
            {datePicker !== null && (
                <DatePickerSheet
                    visible
                    value={datePicker === 'start' ? draft.startDate : draft.endDate}
                    minDate={currentMonthStart()}
                    maxDate={addDays(new Date(), MAX_COURSE_DAYS)}
                    title={datePicker === 'start' ? 'Start Date' : 'End Date'}
                    onClose={() => setDatePicker(null)}
                    onConfirm={d => {
                        applyDate(datePicker, d);
                        setDatePicker(null);
                    }}
                />
            )}
        </View>
    );
};

const styles = StyleSheet.create({
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: 12,
        paddingVertical: 8,
        gap: 4,
    },
    headerTitle: { fontSize: 24, fontWeight: '800' },
    trashBtn: { width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginRight: 6 },

    card: {
        borderRadius: 18,
        borderWidth: 1,
        padding: 18,
        marginTop: 14,
    },
    cardLabel: { fontSize: 18, fontWeight: '700', marginBottom: 12 },
    nameInput: {
        borderRadius: 12,
        borderWidth: 1.5,
        paddingHorizontal: 16,
        paddingVertical: 14,
        fontSize: 17,
    },

    rowCard: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    rowLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
    rowLabel: { fontSize: 17, fontWeight: '700' },
    rowValueStrong: { fontSize: 17, fontWeight: '700' },
    rowValueAccent: { fontSize: 16, fontWeight: '700' },
    typeIcon: { width: 34, height: 34, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },

    dateRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 4 },
    hr: { height: StyleSheet.hairlineWidth, marginVertical: 14 },

    twoCol: { flexDirection: 'row', gap: 12 },
    colCard: { flex: 1, marginTop: 14, minHeight: 104, justifyContent: 'space-between' },
    stepperRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 12 },
    stepBtn: {
        width: 38,
        height: 38,
        borderRadius: 11,
        borderWidth: 1,
        alignItems: 'center',
        justifyContent: 'center',
    },
    qtyValue: { fontSize: 22, fontWeight: '800', minWidth: 28, textAlign: 'center' },
    doseRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 16 },
    doseValue: { fontSize: 16, fontWeight: '600', flexShrink: 1 },

    countPill: { paddingHorizontal: 7, paddingVertical: 2, borderRadius: 10 },
    helper: { fontSize: 12, fontWeight: '500', marginTop: 8, marginHorizontal: 4 },
    subLabel: { fontSize: 13, fontWeight: '600', marginBottom: 10 },
    modeRow: { flexDirection: 'row', gap: 12 },
    modeOpt: { flex: 1, borderRadius: 14, alignItems: 'center', paddingVertical: 14, paddingHorizontal: 8, gap: 5 },
    modeLabel: { fontSize: 14, fontWeight: '700' },
    modeHint: { fontSize: 11, fontWeight: '500', textAlign: 'center' },
    chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
    chip: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 8 },
    chipText: { fontSize: 13, fontWeight: '700' },

    err: { fontSize: 12, fontWeight: '600', marginTop: 8 },
    warn: { fontSize: 12, fontWeight: '600', marginTop: 8 },
    errStandalone: { fontSize: 12, fontWeight: '600', marginTop: 6, marginHorizontal: 4 },
    warnStandalone: { fontSize: 12, fontWeight: '600', marginTop: 6, marginHorizontal: 4 },

    note: {
        position: 'absolute',
        left: 18,
        right: 18,
        flexDirection: 'row',
        alignItems: 'center',
        gap: 8,
        paddingHorizontal: 14,
        paddingVertical: 12,
        borderRadius: 12,
        elevation: 6,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.2,
        shadowRadius: 10,
    },
    noteText: { color: '#FFFFFF', fontSize: 13, fontWeight: '600', flex: 1 },

    footer: {
        paddingHorizontal: 18,
        paddingTop: 12,
        borderTopWidth: StyleSheet.hairlineWidth,
    },
    doneBtn: { borderRadius: 16, paddingVertical: 17, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
    doneText: { color: '#FFFFFF', fontSize: 17, fontWeight: '700' },
});

export default AddMedicationScreen;
