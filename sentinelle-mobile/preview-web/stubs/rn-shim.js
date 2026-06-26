// Shim « react-native » → react-native-web, avec compléments pour les noms
// absents de RNW (utilisés par le code mais inutiles pour un aperçu visuel).
import * as RNW from 'react-native-web';

export const View = RNW.View;
export const Text = RNW.Text;
export const StyleSheet = RNW.StyleSheet;
export const TouchableOpacity = RNW.TouchableOpacity;
export const ActivityIndicator = RNW.ActivityIndicator;
export const FlatList = RNW.FlatList;
export const ScrollView = RNW.ScrollView;
export const Switch = RNW.Switch;
export const TextInput = RNW.TextInput;
export const KeyboardAvoidingView = RNW.KeyboardAvoidingView || RNW.View;
export const Platform = RNW.Platform || { OS: 'web', select: (o) => o.web ?? o.default };
export const Alert = RNW.Alert || { alert: (...a) => console.log('alert', ...a) };
export const StatusBar = RNW.StatusBar || (() => null);
export const SafeAreaView = RNW.SafeAreaView || RNW.View;
export const NativeModules = RNW.NativeModules || {};
export class NativeEventEmitter {
  addListener() {
    return { remove() {} };
  }
  removeAllListeners() {}
}
export const AppRegistry = RNW.AppRegistry || { registerComponent() {}, registerHeadlessTask() {} };

export default RNW;
