/** Looping alarm sound + vibration for the full-screen ringer (from HealthApp's SOSAlarmService). */
import { Platform, Vibration } from 'react-native';
import Sound from 'react-native-sound';

let sound: Sound | null = null;
let playing = false;

export const AlarmSound = {
    start() {
        if (playing) return;
        playing = true;
        Vibration.vibrate(Platform.OS === 'android' ? [0, 800, 400] : [800, 400], true);
        Sound.setCategory('Alarm', false);
        const s = new Sound('magic_ways.mp3', Platform.OS === 'ios' ? Sound.MAIN_BUNDLE : undefined, err => {
            if (err || !playing) return;
            s.setNumberOfLoops(-1);
            s.setVolume(1);
            s.play();
        });
        sound = s;
    },
    stop() {
        playing = false;
        Vibration.cancel();
        if (sound) {
            sound.stop();
            sound.release();
            sound = null;
        }
    },
};
