#!/usr/bin/env python3
"""
Arduino Relay Control Script - Version with persistent connection cache
"""

import argparse
import fcntl
import logging
import serial
import sys
import time
from enum import IntEnum
from typing import Optional, Dict, Any, Iterable, List

import socket
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RelayChannel(IntEnum):
    CHANNEL_0 = 0
    CHANNEL_1 = 1
    CHANNEL_2 = 2
    CHANNEL_3 = 3
    CHANNEL_4 = 4
    CHANNEL_5 = 5


class ArduinoCommands:
    ID = "ID"
    ON = "ON"
    OFF = "OFF"
    TOGGLE = "TOGGLE"
    PULSE = "PULSE"
    STATUS = "STATUS"
    ALL_OFF = "ALLOFF"
    ALL_ON = "ALLON"


class ArduinoResponses:
    DEVICE_ID = "RELAY-CTRL"
    STATUS_OK = "STATUS"
    ERROR = "ERR"
    OK = "OK"


class PersistentArduinoController:
    """
    Controlador que mantiene la conexión abierta usando un lockfile
    para evitar el auto-reset del Arduino.
    """
    
    _instance = None
    _connection = None
    _lockfile = None
    
    def __new__(cls, port: str = '/dev/arduino-relay', baudrate: int = 115200):
        # Singleton por puerto
        if cls._instance is None or cls._instance.port != port:
            cls._instance = super().__new__(cls)
            cls._instance.port = port
            cls._instance.baudrate = baudrate
            cls._instance.timeout = 2.0
            cls._instance._lockfile_path = f"/tmp/arduino-relay-{port.replace('/', '_')}.lock"
        return cls._instance
    
    def get_connection(self) -> Optional[serial.Serial]:
        """Obtiene la conexión persistente, creándola si es necesario."""
        
        # Si ya tenemos conexión activa, usarla
        if self._connection and self._connection.is_open:
            return self._connection
            
        # Intentar obtener el lock
        try:
            self._lockfile = open(self._lockfile_path, 'w')
            fcntl.flock(self._lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Somos los únicos con el lock, crear conexión
            logging.info(f"Acquiring persistent connection to {self.port}")
            
            self._connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            
            # Solo esperar reset la primera vez
            time.sleep(2)
            self._connection.reset_input_buffer()
            self._connection.reset_output_buffer()
            
            # Verificar que funciona
            self._connection.write(b"ID\n")
            self._connection.flush()
            response = self._connection.readline().decode('utf-8', errors='ignore').strip()
            
            if "RELAY-CTRL" not in response:
                raise Exception(f"Invalid Arduino response: {response}")
                
            logging.info("Persistent Arduino connection established")
            return self._connection
            
        except (IOError, OSError):
            # Otro proceso tiene el lock, la conexión ya existe
            # Esperar un poco y reintentar
            logging.debug("Another process holds the Arduino connection")
            time.sleep(0.1)
            return None
            
        except Exception as e:
            logging.error(f"Failed to create persistent connection: {e}")
            self._cleanup()
            return None
    
    def send_command(self, command: str) -> Optional[str]:
        """Envía un comando usando la conexión persistente."""
        
        max_retries = 3
        for attempt in range(max_retries):
            conn = self.get_connection()
            if not conn:
                time.sleep(0.1)
                continue
                
            try:
                # Enviar comando
                cmd_bytes = f"{command}\n".encode('utf-8')
                conn.write(cmd_bytes)
                conn.flush()
                
                # Leer respuesta
                response_lines = []
                for _ in range(10):
                    line = conn.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        response_lines.append(line)
                        if any(term in line for term in ["STATUS", "ERR", "OK", "RELAY-CTRL"]):
                            break
                    else:
                        break
                        
                response = '\n'.join(response_lines)
                logging.debug(f"Command: {command} -> Response: {response}")
                return response
                
            except Exception as e:
                logging.error(f"Error sending command (attempt {attempt+1}): {e}")
                self._cleanup()
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    
        return None
    
    def _cleanup(self):
        """Limpia la conexión y el lockfile."""
        if self._connection:
            try:
                self._connection.close()
            except:
                pass
            self._connection = None
            
        if self._lockfile:
            try:
                fcntl.flock(self._lockfile.fileno(), fcntl.LOCK_UN)
                self._lockfile.close()
            except:
                pass
            self._lockfile = None
    
    def __del__(self):
        self._cleanup()


# Actualizar la clase principal para usar el controlador persistente
class ArduinoRelayController:
    """Interfaz compatible que usa conexión persistente internamente."""
    
    def __init__(self, port: str = '/dev/arduino-relay', baudrate: int = 115200, timeout: float = 2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._persistent = PersistentArduinoController(port, baudrate)
        logger.info(f"Initialized ArduinoRelayController - Port: {port}, Baudrate: {baudrate}")

    def connect(self) -> bool:
        """Conecta usando el controlador persistente."""
        return self._persistent.get_connection() is not None

    def disconnect(self) -> None:
        """No-op - la conexión se mantiene persistente."""
        pass

    def is_connected(self) -> bool:
        """Verifica si hay conexión disponible."""
        return self._persistent.get_connection() is not None

    # -------- Single-channel helpers (kept for compatibility) --------
    def relay_on(self, channel: int) -> bool:
        self._validate_channel(channel)
        logger.info(f"Turning ON relay channel {channel}")
        return self._exec_and_ok(f"{ArduinoCommands.ON} {channel}")

    def relay_off(self, channel: int) -> bool:
        self._validate_channel(channel)
        logger.info(f"Turning OFF relay channel {channel}")
        return self._exec_and_ok(f"{ArduinoCommands.OFF} {channel}")

    # -------- Multi-channel helpers --------
    def relays_on(self, channels: Iterable[int]) -> bool:
        ch = self._validate_channels(channels)
        logger.info(f"Turning ON relay channels {ch}")
        return self._exec_and_ok(f"{ArduinoCommands.ON} " + " ".join(map(str, ch)))

    def relays_off(self, channels: Iterable[int]) -> bool:
        ch = self._validate_channels(channels)
        logger.info(f"Turning OFF relay channels {ch}")
        return self._exec_and_ok(f"{ArduinoCommands.OFF} " + " ".join(map(str, ch)))

    def relays_toggle(self, channels: Iterable[int]) -> bool:
        ch = self._validate_channels(channels)
        logger.info(f"Toggling relay channels {ch}")
        return self._exec_and_ok(f"{ArduinoCommands.TOGGLE} " + " ".join(map(str, ch)))

    def pulse(self, channel: int, milliseconds: int) -> bool:
        self._validate_channel(channel)
        if not (1 <= milliseconds <= 60000):
            raise ValueError("Invalid milliseconds. Must be 1..60000")
        logger.info(f"Pulsing relay {channel} for {milliseconds} ms")
        return self._exec_and_ok(f"{ArduinoCommands.PULSE} {channel} {milliseconds}")

    # -------- Bulk helpers --------
    def all_relays_off(self) -> bool:
        logger.info("Turning OFF all relays")
        return self._exec_and_ok(ArduinoCommands.ALL_OFF)

    def all_relays_on(self) -> bool:
        logger.info("Turning ON all relays")
        return self._exec_and_ok(ArduinoCommands.ALL_ON)

    # -------- Status --------
    def get_status(self) -> Optional[Dict[str, Any]]:
        logger.debug("Requesting relay status")
        if self._send_command(ArduinoCommands.STATUS):
            response = self._read_response()
            if response:
                logger.debug(f"Status response received: {response}")
                return self._parse_status_response(response)
        logger.error("Failed to get relay status")
        return None

    # -------- Internals --------
    def _exec_and_ok(self, command: str) -> bool:
        if self._send_command(command):
            response = self._read_response()
            if self._is_success_response(response):
                logger.debug(f"OK: {response}")
                return True
            logger.error(f"Command failed. Resp: {response}")
        return False

    def _validate_channel(self, channel: int) -> None:
        if not 0 <= channel <= 5:
            raise ValueError(f"Invalid channel {channel}. Must be 0-5")

    def _validate_channels(self, channels: Iterable[int]) -> List[int]:
        ch_list = list(channels)
        if not ch_list:
            raise ValueError("No channels provided")
        for c in ch_list:
            self._validate_channel(int(c))
        return [int(c) for c in ch_list]

    def _send_command(self, command: str) -> bool:
        if not self.is_connected():
            logger.error("No active connection to Arduino")
            return False
        try:
            cmd_bytes = f"{command}\n".encode('utf-8')
            self._persistent.send_command(command) # Use persistent send_command
            logger.debug(f"Command sent: {command}")
            return True
        except Exception as e:
            logger.error(f"Error sending command '{command}': {e}")
            return False

    def _read_response(self, max_lines: int = 10) -> Optional[str]:
        if not self.is_connected():
            logger.error("No active connection to Arduino")
            return None
        try:
            response_lines = []
            for _ in range(max_lines):
                line = self._persistent.send_command("STATUS") # Use persistent send_command
                if line:
                    response_lines.append(line)
                    # Stop early on clear terminators
                    if any(ind in line for ind in (
                        ArduinoResponses.STATUS_OK,
                        ArduinoResponses.ERROR,
                        ArduinoResponses.OK,
                        ArduinoResponses.DEVICE_ID
                    )):
                        break
                else:
                    break
            response = '\n'.join(response_lines) if response_lines else None
            logger.debug(f"Response received:\n{response}")
            return response
        except Exception as e:
            logger.error(f"Error reading response: {e}")
            return None

    def _is_success_response(self, response: Optional[str]) -> bool:
        if not response:
            return False
        # STATUS lines after commands are considered OK if they don't include ERR
        return (ArduinoResponses.STATUS_OK in response or
                ArduinoResponses.OK in response or
                ArduinoResponses.DEVICE_ID in response) and \
               ArduinoResponses.ERROR not in response

    def _parse_status_response(self, response: str) -> Dict[str, Any]:
        """
        Expected STATUS format (from Arduino):
          STATUS 0:OFF 1:ON 2:OFF 3:OFF 4:ON 5:OFF
        """
        status_line = None
        for line in response.splitlines():
            if line.startswith(ArduinoResponses.STATUS_OK):
                status_line = line
                break
        channels: Dict[int, bool] = {}
        if status_line:
            parts = status_line.split()[1:]  # skip "STATUS"
            for tok in parts:
                if ':' in tok:
                    idx, val = tok.split(':', 1)
                    try:
                        ch = int(idx)
                        channels[ch] = (val.upper() == 'ON')
                    except ValueError:
                        continue
        return {
            'raw_response': response,
            'timestamp': time.time(),
            'connected': True,
            'channels': channels
        }

    def _cleanup_connection(self) -> None:
        # This method is no longer needed as connection is persistent
        pass

    def __enter__(self):
        if not self.connect():
            raise RuntimeError("Failed to connect to Arduino")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class DaemonClient:
    """Cliente simple para comunicarse con el daemon."""
    
    def __init__(self, socket_path: str = "/tmp/arduino-relay.sock"):
        self.socket_path = socket_path
    
    def is_daemon_running(self) -> bool:
        """Verifica si el daemon está corriendo."""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(1.0)
                sock.connect(self.socket_path)
                return True
        except:
            return False
    
    def send_command(self, command: str) -> dict:
        """Envía comando al daemon."""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(5.0)
                sock.connect(self.socket_path)
                
                request = {"command": command}
                sock.send(json.dumps(request).encode('utf-8'))
                
                response_data = sock.recv(4096)
                return json.loads(response_data.decode('utf-8'))
        except Exception as e:
            return {"success": False, "error": str(e)}


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Arduino Relay Controller for labgrid integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage Examples:
  %(prog)s on 0 1 3                # Turn ON channels 0,1,3
  %(prog)s off 2 5                 # Turn OFF channels 2 and 5
  %(prog)s toggle 0 4              # Toggle channels 0 and 4
  %(prog)s pulse 1 500             # Pulse channel 1 for 500 ms
  %(prog)s all-on                  # Turn ON all relays
  %(prog)s all-off                 # Turn OFF all relays
  %(prog)s status                  # Show status of all relays
  %(prog)s --port /dev/ttyUSB0 on 0 1  # Use custom port

Exit Codes:
  0 - Success
  1 - Connection error
  2 - Command execution error
  3 - Invalid arguments
        """
    )

    # Global options
    parser.add_argument('--port', default='/dev/arduino-relay',
                        help='Serial port path (default: /dev/arduino-relay)')
    parser.add_argument('--baudrate', type=int, default=115200,
                        help='Serial communication speed (default: 115200)')
    parser.add_argument('--timeout', type=float, default=2.0,
                        help='Communication timeout in seconds (default: 2.0)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging output')

    subparsers = parser.add_subparsers(dest='action', help='Available actions')

    # ON
    on_parser = subparsers.add_parser('on', help='Turn ON one or more channels')
    on_parser.add_argument('channels', nargs='+', type=int, choices=range(6),
                           help='Relay channels (0-5). Multiple allowed.')

    # OFF
    off_parser = subparsers.add_parser('off', help='Turn OFF one or more channels')
    off_parser.add_argument('channels', nargs='+', type=int, choices=range(6),
                            help='Relay channels (0-5). Multiple allowed.')

    # TOGGLE
    tog_parser = subparsers.add_parser('toggle', help='Toggle one or more channels')
    tog_parser.add_argument('channels', nargs='+', type=int, choices=range(6),
                            help='Relay channels (0-5). Multiple allowed.')

    # PULSE
    pulse_parser = subparsers.add_parser('pulse', help='Pulse a channel for ms')
    pulse_parser.add_argument('channel', type=int, choices=range(6),
                              help='Relay channel (0-5)')
    pulse_parser.add_argument('milliseconds', type=int,
                              help='Pulse width in milliseconds (1..60000)')

    # STATUS
    subparsers.add_parser('status', help='Show status of all relay channels')

    # ALL-ON / ALL-OFF
    subparsers.add_parser('all-on', help='Turn ON all relay channels')
    subparsers.add_parser('all-off', help='Turn OFF all relay channels')

    return parser


def main() -> int:
    parser = create_argument_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.action:
        parser.print_help()
        return 3

    # Detectar si el daemon está corriendo
    daemon_client = DaemonClient()
    use_daemon = daemon_client.is_daemon_running()
    
    if use_daemon:
        logger.info("Using Arduino daemon (no reset)")
        return _execute_via_daemon(args, daemon_client)
    else:
        logger.info("Using direct connection (may cause reset)")
        return _execute_direct(args)

def _execute_via_daemon(args, daemon_client: DaemonClient) -> int:
    """Ejecuta comandos vía daemon."""
    try:
        # Construir comando para el daemon
        if args.action == 'on':
            cmd = f"ON {' '.join(map(str, args.channels))}"
        elif args.action == 'off':
            cmd = f"OFF {' '.join(map(str, args.channels))}"
        elif args.action == 'toggle':
            cmd = f"TOGGLE {' '.join(map(str, args.channels))}"
        elif args.action == 'pulse':
            cmd = f"PULSE {args.channel} {args.milliseconds}"
        elif args.action == 'status':
            cmd = "STATUS"
        elif args.action == 'all-off':
            cmd = "ALLOFF"
        elif args.action == 'all-on':
            cmd = "ALLON"
        else:
            return 3
            
        # Enviar al daemon
        result = daemon_client.send_command(cmd)
        
        if result.get("success", False):
            if args.action == 'status':
                print(result.get("response", ""))
            return 0
        else:
            logger.error(f"Daemon command failed: {result.get('error', 'Unknown error')}")
            return 2
            
    except Exception as e:
        logger.error(f"Error communicating with daemon: {e}")
        return 2

def _execute_direct(args) -> int:
    """Ejecuta comandos directamente (método original)."""
    controller = ArduinoRelayController(
        port=args.port,
        baudrate=args.baudrate,
        timeout=args.timeout
    )
    if not controller.connect():
        logger.error("Failed to connect to Arduino device")
        return 1

    try:
        success = False
        if args.action == 'on':
            if len(args.channels) == 1:
                success = controller.relay_on(args.channels[0])
            else:
                success = controller.relays_on(args.channels)

        elif args.action == 'off':
            if len(args.channels) == 1:
                success = controller.relay_off(args.channels[0])
            else:
                success = controller.relays_off(args.channels)

        elif args.action == 'toggle':
            success = controller.relays_toggle(args.channels)

        elif args.action == 'pulse':
            success = controller.pulse(args.channel, args.milliseconds)

        elif args.action == 'status':
            status = controller.get_status()
            success = status is not None
            if success and status:
                ch_map = status.get('channels', {})
                pretty = ' '.join(f'{k}:{ "ON" if v else "OFF"}' for k, v in sorted(ch_map.items()))
                print(f"STATUS {pretty}" if pretty else status['raw_response'])

        elif args.action == 'all-off':
            success = controller.all_relays_off()

        elif args.action == 'all-on':
            success = controller.all_relays_on()

        return 0 if success else 2

    except ValueError as e:
        logger.error(f"Invalid argument: {e}")
        return 3
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 2
    finally:
        controller.disconnect()


if __name__ == '__main__':
    sys.exit(main())
