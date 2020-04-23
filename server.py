#!/usr/bin/python3
import bluetooth
import dbus
import logging
import logging.handlers
import os
import signal
import subprocess
import sys
import threading
import socket
import string
import random
import os

_closables = []


def _SignalHandler(signum, frame):  # pylint: disable=unused-argument
    print("\nCaught signal %d\n" % signum)
    for closable in _closables:
        closable.Close()


def _ExceptionHandler(exc_type, exc_value, exc_traceback):
    sys.__excepthook__(exc_type, exc_value, exc_traceback)
    os.kill(os.getpid(), signal.SIGINT)


class BluetoothServer(object):

    def __init__(self):
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._server_socket = None
        self._client_socket = None
        self._logger = logging.getLogger("logger")
        self._adapter = dbus.Interface(dbus.SystemBus().get_object(
            "org.bluez", "/org/bluez/hci0"), "org.freedesktop.DBus.Properties")
        self._adapter.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(1))
        self._closed = False
        self.set_host_name()

    def __del__(self):
        self.Close()

    def Close(self):
        """Closes the server and all assiciated resources."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._cond.notifyAll()

        if self._client_socket is not None:
            self._client_socket.close()

        if self._server_socket is not None:
            self._server_socket.close()

        self.set_discoverable(False)

    def run(self):
        if self._closed:
            return not self._closed

        subprocess.call("/usr/bin/sdptool add SP", shell=True)

        self._server_socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        self._server_socket.bind(("", bluetooth.PORT_ANY))
        self._server_socket.listen(1)
        self.hci_config_command("piscan")

        uuid = "00001101-0000-1000-8000-00805F9B34FB"
        bluetooth.advertise_service(
            self._server_socket,
            "rpi-bluetooth-server",
            service_id=uuid,
            service_classes=[uuid, bluetooth.SERIAL_PORT_CLASS],
            profiles=[bluetooth.SERIAL_PORT_PROFILE])

        while True:
            try:
                self._logger.info("Waiting for connections")
                self.set_discoverable(True)
                self._client_socket, client_info = self._server_socket.accept()
                self._logger.info(
                    "Connection from %s on channel %d",
                    client_info[0],
                    client_info[1])
            except bluetooth.BluetoothError as error:
                self._logger.info("Stop waiting for connections (%s)", error)
                break

            try:
                self.set_discoverable(False)
                self.handle_connection()
            except (IOError, bluetooth.BluetoothError):
                pass
            finally:
                self._client_socket.close()
                self._client_socket = None
                self._logger.info("Connection from %s on channel %d ended",
                                  client_info[0], client_info[1])
        self._logger.info("Server done")
        self.set_discoverable(False)
        return not self._closed

    def set_discoverable(self, discoverable):
        adapter = self._adapter
        if discoverable:
            adapter.Set(
                "org.bluez.Adapter1",
                "DiscoverableTimeout",
                dbus.UInt32(0))
            adapter.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(1))
            self.hci_config_command("leadv 3")
            self._logger.info("Discoverable enabled")
        else:
            adapter.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(0))
            self.hci_config_command("noleadv")
            self._logger.info("Discoverable disabled")

    def hci_config_command(self, command):
        subprocess.call("/bin/hciconfig hci0 %s" % command, shell=True)

    def handle_connection(self):
        while True:
            received_msg = self.get_msg()
            self._logger.info("Received request '%s'" % received_msg.rstrip())
            self.handle_request(received_msg)

    def handle_request(self, msg):
        try:
            self.send_msg("::start::")
            result = subprocess.check_output(msg, shell=True).decode('utf-8').strip()
            if not len(result):
                self.send_msg("the command '%s' returns nothing " % msg)
            for line in result.splitlines():
                self.send_msg(line + " ")
        except:
            self.send_msg("Error when trying to run the command '%s' " % msg)
        finally:
            self.send_msg("::end::")

    def send_msg(self, message):
        if self._client_socket is None:
            return
        self._logger.info("SendMessage: %s" % message)
        self._client_socket.send(message)

    def get_msg(self):
        data = self._client_socket.recv(1024).decode("utf-8")
        return str(data)

    def set_host_name(self):
        if not os.path.exists('/etc/bluetooth-id'):
            bt_device_number = ''.join(random.sample((string.digits), 4))
            f = open("/etc/bluetooth-id", "w")
            f.write(bt_device_number)
            f.close()
        else:
            f = open("/etc/bluetooth-id", "r")
            bt_device_number = f.read()
            f.close()

        bt_name = "%s-%s" % (socket.gethostname(), bt_device_number)
        self._device_name = bt_name
        self._logger.info("Setting device name: '%s'", bt_name)
        self._adapter.Set("org.bluez.Adapter1", "Alias", dbus.String(bt_name))


if __name__ == "__main__":
    sys.excepthook = _ExceptionHandler
    signal.signal(signal.SIGINT, _SignalHandler)
    signal.signal(signal.SIGTERM, _SignalHandler)
    logger = logging.getLogger("logger")
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s: %(message)s")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.info("Debug logs enabled")
    server = BluetoothServer()
    _closables.append(server)
    server.run()
