/**
 * Point d'entrée React Native.
 */
import { AppRegistry } from 'react-native';

import App from './App';
import { name as appName } from './app.json';
import { sentinelleSmsHeadlessTask } from './src/services/smsHeadlessTask';

AppRegistry.registerComponent(appName, () => App);

// Tâche Headless JS : analyse des SMS même quand l'app est « tuée » (Android).
AppRegistry.registerHeadlessTask('SentinelleSmsTask', () => sentinelleSmsHeadlessTask);
