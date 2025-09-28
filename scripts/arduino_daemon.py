#!/usr/bin/env python3
"""
Arduino Relay Daemon - Mantiene conexión persistente para evitar auto-reset.
"""

import json
import logging
import os
import signal
import socket
import threading
import time
from typing import Dict, Any, Optional

import serial

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ArduinoRelayDaemon:
    def __init__(self,
                 arduino_port: str = "/dev/arduino-relay",
                 socket_path: str = "/tmp/arduino-relay.sock",
                 pidfile: str = "/tmp/arduino-relay.pid"):

        self.arduino_port = arduino_port
        self.socket_path = socket_path
        self.pidfile = pidfile

        self.arduino: Optional[serial.Serial] = None
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        self.arduino_lock = threading.Lock()

    def start(self):
        """Inicia el daemon."""
        if self._is_already_running():
            logger.error("Daemon already running")
            return False

        # Conectar Arduino
        if not self._connect_arduino():
            return False

        # Crear socket Unix
        if not self._setup_socket():
            return False

        # Escribir PID
        with open(self.pidfile, 'w') as f:
            f.write(str(os.getpid()))

        # Signal handlers
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

        self.running = True
        logger.info(f"Arduino Relay Daemon started (PID: {os.getpid()})")

        # Main loop
        self._main_loop()

    def _connect_arduino(self) -> bool:
        try:
            self.arduino = serial.Serial(
                port=self.arduino_port,
                baudrate=115200,
                timeout=2.0
            )

            # Esperar reset inicial (solo una vez)
            time.sleep(3)
            self.arduino.reset_input_buffer()
            self.arduino.reset_output_buffer()

            # Verificar conexión
            self.arduino.write(b"ID\n")
            response = self.arduino.readline().decode('utf-8', errors='ignore')

            if "RELAY-CTRL" in response:
                logger.info(f"Arduino connected: {response.strip()}")
                return True
            else:
                logger.error(f"Invalid Arduino response: {response}")
                return False

        except Exception as e:
            logger.error(f"Failed to connect Arduino: {e}")
            return False

    def _setup_socket(self) -> bool:
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)

            self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server_socket.bind(self.socket_path)
            self.server_socket.listen(5)
            os.chmod(self.socket_path, 0o666)

            logger.info(f"Socket created: {self.socket_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to create socket: {e}")
            return False

    def _main_loop(self):
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                try:
                    client, _ = self.server_socket.accept()
                    threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
                except socket.timeout:
                    continue
            except Exception as e:
                if self.running:
                    logger.error(f"Main loop error: {e}")

    def _handle_client(self, client: socket.socket):
        try:
            with client:
                data = client.recv(1024)
                if data:
                    request = json.loads(data.decode('utf-8'))
                    response = self._execute_command(request.get("command", ""))
                    client.send(json.dumps(response).encode('utf-8'))
        except Exception as e:
            logger.error(f"Client error: {e}")

    def _execute_command(self, command: str) -> Dict[str, Any]:
        if not command:
            return {"success": False, "error": "No command"}

        try:
            with self.arduino_lock:
                self.arduino.write(f"{command}\n".encode('utf-8'))
                self.arduino.flush()

                # Leer respuesta
                lines = []
                for _ in range(10):
                    line = self.arduino.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        lines.append(line)
                        if any(term in line for term in ["STATUS", "ERR", "OK", "RELAY-CTRL"]):
                            break
                    else:
                        break

                response = '\n'.join(lines)
                success = response and "ERR" not in response

                return {"success": success, "response": response}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _shutdown(self, signum=None, frame=None):
        logger.info("Shutting down...")
        self.running = False

        if self.arduino and self.arduino.is_open:
            self.arduino.close()

        if self.server_socket:
            self.server_socket.close()

        for path in [self.socket_path, self.pidfile]:
            if os.path.exists(path):
                os.unlink(path)

    def _is_already_running(self) -> bool:
        if not os.path.exists(self.pidfile):
            return False
        try:
            with open(self.pidfile, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)  # Check if process exists
            return True
        except:
            os.unlink(self.pidfile)
            return False


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "status"])
    parser.add_argument("--port", default="/dev/arduino-relay")

    args = parser.parse_args()

    daemon = ArduinoRelayDaemon(arduino_port=args.port)

    if args.action == "start":
        daemon.start()
    elif args.action == "stop":
        try:
            with open("/tmp/arduino-relay.pid", 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            print("Stop signal sent")
        except Exception as e:
            print(f"Error: {e}")
    elif args.action == "status":
        if daemon._is_already_running():
            print("Daemon is running")
        else:
            print("Daemon is not running")


if __name__ == "__main__":
    main()
