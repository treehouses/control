#!/usr/bin/python3
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
import bluetooth
import dbus

def _ExceptionHandler(exc_type, exc_value, exc_traceback):
    sys.__excepthook__(exc_type, exc_value, exc_traceback)
    os.kill(os.getpid(), signal.SIGINT)

#This is what gets spawned by the server when it receives a connection.
# based on. Thanks. https://github.com/michaelgheith/actopy/blob/master/LICENSE.txt
class Worker(threading.Thread):
    def __init__(self, sock, address):
        threading.Thread.__init__(self)
        self.sock = sock
        self.address = address
        self._logger = logging.getLogger("logger")
        self.stopped = False

    def send_msg(self, message):
        self._logger.info("%s S - %s" % (self.address[0][12:], message))
        self.sock.send(message)

    def get_msg(self):
        data = str(self.sock.recv(1024).decode("utf-8"))
        if len(data) == 0:
            self.stopped = True
        self._logger.info("%s R %s" % (self.address[0][12:], data))
        return data

    def handle_request(self, msg):
        try:
            #self.send_msg("::start::")
            result = subprocess.check_output(msg, shell=True).decode('utf-8').strip()
            if not len(result):
                self.send_msg("the command '%s' returns nothing " % msg)
            for line in result.splitlines():
                self.send_msg(line + " ")
        except:
            self.send_msg("Error when trying to run the command '%s' " % msg)
        #finally:
            #self.send_msg("::end::")

    def run(self):
        try:
            while True:
                self.handle_request(self.get_msg())
                if self.stopped:
                    break
        except Exception as e:
            pass
        self.sock.close()
        self._logger.info("Disconnected from %s" % self.address[0])

class Server():
    def __init__(self):
        self.q_len = 3
        self.port = bluetooth.PORT_ANY
        self.server_sock = None
        self.name = "rpi-bluetooth-server"
        self.uuid = "00001101-0000-1000-8000-00805F9B34FB"
        self._logger = logging.getLogger("logger")
        self._adapter = dbus.Interface(dbus.SystemBus().get_object(
            "org.bluez", "/org/bluez/hci0"), "org.freedesktop.DBus.Properties")
        self._adapter.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(1))
        self.set_host_name()

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

    def hci_config_command(self, command):
        subprocess.call("/bin/hciconfig hci0 %s" % command, shell=True)

    def start_server(self):
        self.hci_config_command("piscan")
        self.server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        self.server_sock.bind(("", self.port))
        self.server_sock.listen(self.q_len)  #Queue up as many as 5 connect requests.
        self._logger.info("Listening on port %d" % self.port)

    def advertise_service(self):
        bluetooth.advertise_service(
            self.server_sock,
            self.name,
            service_id=self.uuid,
            service_classes=[self.uuid, bluetooth.SERIAL_PORT_CLASS],
            profiles=[bluetooth.SERIAL_PORT_PROFILE])

    def accept_connections(self):
        while True:
            self._logger.info("Main thread waiting for connections")
            client_sock, address = self.server_sock.accept()
            serverHash = sha(server.py)
            self._logger.info("test log")
            if !checkHash(serverHash):
                serverSync()

            self._logger.info("Accepted connection from %s" % address[0])
            Worker(client_sock, address).start()  #Spawns the worker thread.

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

    def run(self):
        self.set_discoverable(True)
        self.start_server()
        self.advertise_service()
        self.accept_connections()
        self.set_discoverable(False)

    def kill(self):
        self.server_sock.close()
        self.set_discoverable(False)
        sys.exit()

if __name__ == "__main__":
    sys.excepthook = _ExceptionHandler
    logger = logging.getLogger("logger")
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s: %(message)s")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.info("Debug logs enabled")
    try:
        multithreaded_server = Server()
        multithreaded_server.run()
    except KeyboardInterrupt:
        self._logger.info("shutting down the server")
        multithreaded_server.kill()
