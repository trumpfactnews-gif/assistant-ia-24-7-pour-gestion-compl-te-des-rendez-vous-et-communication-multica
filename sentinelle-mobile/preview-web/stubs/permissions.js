export const PERMISSIONS = { ANDROID: { RECEIVE_SMS: 'a', READ_SMS: 'b' } };
export const RESULTS = { GRANTED: 'granted' };
export const requestMultiple = () => Promise.resolve({});
export const requestNotifications = () => Promise.resolve({ status: 'granted' });
export const check = () => Promise.resolve('granted');
export const request = () => Promise.resolve('granted');
export default { PERMISSIONS, RESULTS, requestMultiple, requestNotifications, check, request };
