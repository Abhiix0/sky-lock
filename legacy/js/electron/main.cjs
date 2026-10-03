const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');

// Offer GPU fallback: if env SKYLOCK_SOFTWARE_GL=1 call app.disableHardwareAcceleration()
if (process.env.SKYLOCK_SOFTWARE_GL === '1') {
  app.disableHardwareAcceleration();
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1600,
    height: 900,
    title: 'Sky Lock',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  win.setMenuBarVisibility(false);

  // Load dist/index.html via file://
  win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));

  return win;
}

// Handle native file persistence via IPC
ipcMain.handle('save-file', async (event, { name, data }) => {
  const focusedWin = BrowserWindow.getFocusedWindow();
  const { canceled, filePath } = await dialog.showSaveDialog(focusedWin, {
    title: 'Save Sky Lock File',
    defaultPath: name
  });

  if (!canceled && filePath) {
    await fs.promises.writeFile(filePath, Buffer.from(data));
    return { success: true, filePath };
  }
  return { canceled: true };
});

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
