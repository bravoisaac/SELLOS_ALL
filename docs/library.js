let database;
function open() {
  if (!database) database = new Promise((resolve, reject) => {
    const request = indexedDB.open('sello-pdf-web', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('stamps', { keyPath: 'id' });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error('No se puede acceder a Mis sellos. Puedes seguir usando la app sin guardarlos.'));
  });
  return database;
}
async function transaction(mode, action) {
  const db = await open();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('stamps', mode);
    const request = action(tx.objectStore('stamps'));
    tx.oncomplete = () => resolve(request.result);
    tx.onerror = tx.onabort = () => reject(new Error('No se pudo guardar el cambio. Revisa el espacio disponible del navegador.'));
  });
}
export const listStamps = () => transaction('readonly', store => store.getAll());
export const putStamp = stamp => transaction('readwrite', store => store.put(stamp));
export const removeStamp = id => transaction('readwrite', store => store.delete(id));
