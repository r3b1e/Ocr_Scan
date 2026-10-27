/**
 * @format
 */

import { AppRegistry } from 'react-native';
import App from './App';
import { name as appName } from './app.json';
import { registerBackgroundHandler } from './src/reminders/ReminderService';

// Notification actions (Taken / Skip / Snooze) while the app is closed.
registerBackgroundHandler();

AppRegistry.registerComponent(appName, () => App);
