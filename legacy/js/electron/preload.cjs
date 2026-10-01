const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('skylock', {
  saveFile: (name, dataUint8Array) => ipcRenderer.invoke('save-file', { name, data: dataUint8Array })
});
