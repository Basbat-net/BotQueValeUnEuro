"""A small MJPEG server over HTTP, written with plain sockets (no http.server: it needs inheritance).

MJPEG over HTTP is a never-ending answer of type multipart/x-mixed-replace: each part is one
JPEG picture. Browsers, VLC and OpenCV (with FFmpeg) open it from a URL like http://robot:8080/video.
Each client gets only the newest picture: if it is slow, the pictures in between are skipped
instead of queuing up, so the delay never grows.
"""

import selectors
import socket
import threading


class MjpegServer:
    """Serves the pictures given to publishFrame. Created once at startup."""

    boundary: bytes = b"frame"

    def __init__(self, port: int) -> None:
        self.port: int = port
        self.listener: socket.socket | None = None
        self.condition: threading.Condition = threading.Condition()
        self.latestJpeg: bytes = b""
        # +1 per published picture: a client sends a picture only when this is newer than its last one
        self.frameNumber: int = 0
        self.isRunning: bool = False
        self.clientCount: int = 0
        self.lastError: str = ""

    def start(self) -> bool:
        """Starts listening. False if the port is busy (see lastError)."""
        try:
            # Recovery only: a busy port is reported, not propagated
            self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.listener.bind(("0.0.0.0", self.port))
            self.listener.listen()
        except OSError as error:
            self.lastError = f"cannot listen on port {self.port}: {error}"
            return False
        self.isRunning = True
        threading.Thread(target=self._acceptLoop, daemon=True).start()
        return True

    def publishFrame(self, jpegBytes: bytes) -> None:
        """Makes this picture the newest one and wakes the clients."""
        with self.condition:
            self.latestJpeg = jpegBytes
            self.frameNumber += 1
            self.condition.notify_all()

    def stop(self) -> None:
        """Stops accepting and ends every client connection."""
        with self.condition:
            self.isRunning = False
            self.condition.notify_all()
        if self.listener is not None:
            self.listener.close()

    def _acceptLoop(self) -> None:
        """Body of the listening thread: one new thread per client."""
        selector: selectors.DefaultSelector = selectors.DefaultSelector()
        if self.listener is None:
            return
        selector.register(self.listener, selectors.EVENT_READ)
        while self.isRunning:
            # Waking up every half second lets stop() end this loop
            if not selector.select(timeout=0.5) or not self.isRunning:
                continue
            try:
                # Recovery only: the listener may be closed by stop() in the middle
                connection, _ = self.listener.accept()
            except OSError:
                break
            threading.Thread(target=self._serveClient, args=(connection,), daemon=True).start()
        selector.close()

    def _serveClient(self, connection: socket.socket) -> None:
        """Answers one client: the HTTP header, then pictures until it leaves or the server stops."""
        requestWaitSeconds: float = 2.0
        connection.settimeout(requestWaitSeconds)
        header: bytes = (b"HTTP/1.0 200 OK\r\nCache-Control: no-cache\r\nConnection: close\r\n"
                         b"Content-Type: multipart/x-mixed-replace; boundary=" + self.boundary + b"\r\n\r\n")
        sentFrameNumber: int = 0
        self.clientCount += 1
        try:
            # Recovery only: when a client leaves (or its network drops), sendall fails; that ends the
            # thread of that client and nothing else, the server goes on
            connection.recv(1024)
            connection.sendall(header)
            while True:
                jpegBytes, sentFrameNumber = self._waitForNewerFrame(sentFrameNumber)
                if not jpegBytes:
                    break
                partHeader: bytes = (b"--" + self.boundary + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                     + str(len(jpegBytes)).encode() + b"\r\n\r\n")
                connection.sendall(partHeader + jpegBytes + b"\r\n")
        except OSError:
            pass
        connection.close()
        self.clientCount -= 1

    def _waitForNewerFrame(self, sentFrameNumber: int) -> tuple[bytes, int]:
        """The newest picture once it is newer than the last one sent. Empty bytes when the server stops."""
        with self.condition:
            while self.isRunning and self.frameNumber == sentFrameNumber:
                self.condition.wait(timeout=1.0)
            if not self.isRunning:
                return b"", sentFrameNumber
            return self.latestJpeg, self.frameNumber
