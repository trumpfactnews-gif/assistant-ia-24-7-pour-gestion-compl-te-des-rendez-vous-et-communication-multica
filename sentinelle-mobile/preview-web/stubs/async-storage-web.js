// AsyncStorage pour le web : adossé à localStorage (persiste entre rechargements).
const AsyncStorage = {
  getItem: (k) => Promise.resolve(localStorage.getItem(k)),
  setItem: (k, v) => {
    localStorage.setItem(k, v);
    return Promise.resolve();
  },
  removeItem: (k) => {
    localStorage.removeItem(k);
    return Promise.resolve();
  },
  clear: () => {
    localStorage.clear();
    return Promise.resolve();
  },
  getAllKeys: () => Promise.resolve(Object.keys(localStorage)),
};
export default AsyncStorage;
