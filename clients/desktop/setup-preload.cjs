const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('connection',{connect:value=>ipcRenderer.invoke('connect',value)});
