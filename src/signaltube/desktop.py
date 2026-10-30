"""Linux desktop host. No automatic refresh; close to tray, explicit Quit."""
import os
import sys
import socket
import threading
from pathlib import Path
from urllib.parse import urlsplit


def is_local(url, port):
    try:
        u = urlsplit(url)
        return u.scheme == 'http' and u.hostname == '127.0.0.1' and u.port == port and not u.username and not u.password
    except ValueError:
        return False


def main():
    os.umask(0o077)
    # Set before importing modules whose state paths are bound at import time.
    os.environ.setdefault('SIGNALTUBE_DATA_DIR', str(Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share')))/'signaltube'))
    from PySide6.QtCore import QTimer, QUrl, QLockFile
    from PySide6.QtGui import QIcon, QDesktopServices
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu, QMessageBox, QInputDialog, QLineEdit
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlRequestInterceptor
    from PySide6.QtWebEngineWidgets import QWebEngineView
    import uvicorn
    from . import live, launcher
    from .webapp import create_app
    app = QApplication(sys.argv)
    app.setApplicationName('SignalTube')
    app.setDesktopFileName('signaltube')
    state = live.STATE
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if state.is_symlink() or state.stat().st_uid != os.getuid() or state.stat().st_mode & 0o077:
        QMessageBox.critical(None, 'SignalTube', 'The data folder must be owned by you and private (mode 700).')
        return 1
    endpoint = str(state/'desktop.sock')
    peer = QLocalSocket()
    peer.connectToServer(endpoint)
    if peer.waitForConnected(500):
        peer.write(b'open'); peer.waitForBytesWritten(500); peer.disconnectFromServer()
        return 0
    lock = QLockFile(str(state/'desktop.lock'))
    if not lock.tryLock(0):
        QMessageBox.information(None, 'SignalTube', 'SignalTube is already starting or running. Please try again shortly.')
        return 1
    QLocalServer.removeServer(endpoint)
    control = QLocalServer()
    control.setSocketOptions(QLocalServer.UserAccessOption)
    if not control.listen(endpoint):
        QMessageBox.critical(None, 'SignalTube', 'Could not create the private desktop control socket.')
        return 1
    sock = socket.socket(); sock.bind(('127.0.0.1', 0)); sock.listen(128)
    port = sock.getsockname()[1]
    token = launcher.session_token(state)
    server = uvicorn.Server(uvicorn.Config(create_app(state/'signaltube.sqlite3', token, port), host='127.0.0.1', port=port, access_log=False, log_level='error'))
    worker = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    worker.start()
    icon = QIcon(str(Path(__file__).with_name('desktop.svg')))
    app.setWindowIcon(icon)
    tray = QSystemTrayIcon(icon)
    tray.setToolTip('SignalTube — starting')
    menu = QMenu()
    status = menu.addAction('Starting…'); status.setEnabled(False)
    class Window(QMainWindow):
        def closeEvent(self, event):
            if tray.isSystemTrayAvailable():
                self.hide(); event.ignore()
            else:
                shutdown(); event.accept()
    window = Window(); window.setWindowTitle('SignalTube'); window.resize(1200, 800)
    class LocalOnly(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self, request):
            url = request.requestUrl().toString()
            if not is_local(url, port) and not url.startswith(('data:', 'about:')):
                request.block(True)
    # Off-the-record profile: no stored auth cookies, history, cache or passwords.
    profile = QWebEngineProfile(window)
    interceptor = LocalOnly(profile); profile.setUrlRequestInterceptor(interceptor)
    class Page(QWebEnginePage):
        def acceptNavigationRequest(self, url, kind, main_frame):
            if is_local(url.toString(), port) or url.toString() == 'about:blank':
                return True
            if main_frame and kind == QWebEnginePage.NavigationTypeLinkClicked and url.scheme() == 'https':
                QDesktopServices.openUrl(url)
            return False
    view = QWebEngineView(window); page = Page(profile, view); view.setPage(page)
    # target=_blank links use the system browser; never load remote sites in-app.
    page.newWindowRequested.connect(lambda request: QDesktopServices.openUrl(request.requestedUrl()) if request.isUserInitiated() and request.requestedUrl().scheme() == 'https' else None)
    profile.downloadRequested.connect(lambda download: download.cancel())
    window.setCentralWidget(view)
    def show():
        window.showNormal(); window.raise_(); window.activateWindow()
    def incoming():
        client = control.nextPendingConnection()
        if client:
            show(); client.disconnectFromServer(); client.deleteLater()
    control.newConnection.connect(incoming)
    menu.addAction('Open SignalTube', show)
    def api_key():
        key, accepted = QInputDialog.getText(window, 'YouTube API key', 'Your own Google API key. Saving does not refresh YouTube.', QLineEdit.Password)
        if accepted and key.strip():
            try:
                live.store_key(key.strip())
                QMessageBox.information(window, 'SignalTube', 'Key saved locally. Choose Refresh from YouTube when ready.')
                view.reload()
            except (ValueError, OSError) as error:
                QMessageBox.warning(window, 'Could not save key', str(error))
    menu.addAction('Google API setup and costs', lambda: (show(), view.setUrl(QUrl(f'http://127.0.0.1:{port}/setup'))))
    menu.addAction('Set YouTube API key…', api_key)
    quitting = False
    def shutdown():
        nonlocal quitting
        if quitting: return
        quitting = True
        server.should_exit = True
        tray.hide(); control.close()
        # Destroy the web page before its off-the-record profile.
        view.deleteLater()
        QTimer.singleShot(100, app.quit)
    menu.addSeparator(); menu.addAction('Quit SignalTube', shutdown)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: show() if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
    tray.show(); app.setQuitOnLastWindowClosed(False)
    ready = False
    attempts = 0
    def check():
        nonlocal ready, attempts
        attempts += 1
        if server.started and not ready:
            ready = True
            timer.setInterval(2000)
            view.setUrl(QUrl(f'http://127.0.0.1:{port}/?token={token}'))
            status.setText('Running — refreshes are manual')
            tray.setToolTip('SignalTube — running')
        if not worker.is_alive() or (not ready and attempts > 100):
            timer.stop()
            QMessageBox.critical(window, 'SignalTube stopped', 'The local server did not stay running. No other application was stopped.')
            shutdown()
    timer = QTimer(); timer.setInterval(100); timer.timeout.connect(check); timer.start()
    if '--background' not in sys.argv or not tray.isSystemTrayAvailable(): show()
    app.aboutToQuit.connect(lambda: setattr(server, 'should_exit', True))
    result = app.exec()
    server.should_exit = True; worker.join(timeout=10); sock.close(); lock.unlock()
    return result

if __name__ == '__main__':
    sys.exit(main())
