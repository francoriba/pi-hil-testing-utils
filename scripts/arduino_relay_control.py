#!/usr/bin/env python3
"""
Arduino Relay Control Script
============================

Script for controlling a 6-relay module connected to an Arduino
via USB-Serial interface.

Author: FCEFyN-UNC
Project: pi-hil-testing-utils
Version: 1.0.0
License: MIT

Features:
- Control individual relays (0-5)
- Bulk operations (all on/off)
- Status monitoring
- Error handling and logging
- Command-line interface
- Robust serial communication
"""

import argparse
import logging
import serial
import sys
import time
from enum import IntEnum
from typing import Optional, Dict, Any

# Configure logging
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
    STATUS = "STATUS"
    ALL_OFF = "ALLOFF"


class ArduinoResponses:
    DEVICE_ID = "RELAY-CTRL"
    STATUS_OK = "STATUS"
    ERROR = "ERR"
    OK = "OK"


class ArduinoRelayController:
    """
    This class provides a robust interface for controlling a 6-channel relay module
    connected to an Arduino board via serial communication.

    Attributes:
        port (str): Serial port path
        baudrate (int): Serial communication speed
        timeout (float): Communication timeout in seconds
        connection (Optional[serial.Serial]): Active serial connection
    """

    def __init__(
            self,
            port: str = '/dev/arduino-relay',
            baudrate: int = 115200,
            timeout: float = 2.0
    ) -> None:
        """
        Initialize the Arduino relay controller.

        Args:
            port: Serial port path (default: /dev/arduino-relay)
            baudrate: Serial communication speed (default: 115200)
            timeout: Communication timeout in seconds (default: 2.0)
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.connection: Optional[serial.Serial] = None

        logger.info(f"Initialized ArduinoRelayController - Port: {port}, Baudrate: {baudrate}")

    def connect(self) -> bool:
        """
        Establish connection with the Arduino device.

        Returns:
            bool: True if connection is successful, False otherwise

        Raises:
            serial.SerialException: If serial port cannot be opened
        """
        try:
            logger.info(f"Attempting to connect to Arduino on port {self.port}")

            self.connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout
            )

            # Allow Arduino to initialize
            logger.debug("Waiting for Arduino initialization...")
            time.sleep(2)

            # Clear communication buffers
            self.connection.flushInput()
            self.connection.flushOutput()

            # Verify device responds correctly
            if self._send_command(ArduinoCommands.ID):
                response = self._read_response()
                if response and ArduinoResponses.DEVICE_ID in response:
                    logger.info(f"Arduino connected successfully: {response.strip()}")
                    return True
                else:
                    logger.error(f"Invalid device response: {response}")

            logger.error("Failed to verify Arduino device")
            self._cleanup_connection()
            return False

        except serial.SerialException as e:
            logger.error(f"Serial communication error: {e}")
            self._cleanup_connection()
            return False
        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}")
            self._cleanup_connection()
            return False

    def disconnect(self) -> None:
        """Close the connection with the Arduino device."""
        if self.connection and self.connection.is_open:
            logger.info("Disconnecting from Arduino")
            self.connection.close()
            self.connection = None
        else:
            logger.debug("No active connection to disconnect")

    def is_connected(self) -> bool:
        """
        Check if the controller is currently connected to the Arduino.

        Returns:
            bool: True if connected and ready for communication
        """
        return self.connection is not None and self.connection.is_open

    def relay_on(self, channel: int) -> bool:
        """
        Turn on a specific relay channel.

        Args:
            channel: Relay channel number (0-5)

        Returns:
            bool: True if operation was successful

        Raises:
            ValueError: If channel is not in valid range (0-5)
        """
        self._validate_channel(channel)

        logger.info(f"Turning ON relay channel {channel}")

        if self._send_command(f"{ArduinoCommands.ON} {channel}"):
            response = self._read_response()
            if self._is_success_response(response):
                logger.info(f"Relay {channel} turned ON successfully. Response: {response}")
                return True

        logger.error(f"Failed to turn ON relay {channel}")
        return False

    def relay_off(self, channel: int) -> bool:
        """
        Turn off a specific relay channel.

        Args:
            channel: Relay channel number (0-5)

        Returns:
            bool: True if operation was successful

        Raises:
            ValueError: If channel is not in valid range (0-5)
        """
        self._validate_channel(channel)
        logger.info(f"Turning OFF relay channel {channel}")
        if self._send_command(f"{ArduinoCommands.OFF} {channel}"):
            response = self._read_response()
            if self._is_success_response(response):
                logger.info(f"Relay {channel} turned OFF successfully. Response: {response}")
                return True
        logger.error(f"Failed to turn OFF relay {channel}")
        return False

    def all_relays_off(self) -> bool:
        """
        Turn off all relay channels simultaneously.

        Returns:
            bool: True if operation was successful
        """
        logger.info("Turning OFF all relays")
        if self._send_command(ArduinoCommands.ALL_OFF):
            response = self._read_response()
            if self._is_success_response(response):
                logger.info(f"All relays turned OFF successfully. Response: {response}")
                return True
        logger.error("Failed to turn OFF all relays")
        return False

    def get_status(self) -> Optional[Dict[str, Any]]:
        """
        Get the current status of all relay channels.

        Returns:
            Optional[Dict[str, Any]]: Status information or None if error occurred
        """
        logger.debug("Requesting relay status")
        if self._send_command(ArduinoCommands.STATUS):
            response = self._read_response()
            if response:
                logger.debug(f"Status response received: {response}")
                return self._parse_status_response(response)
        logger.error("Failed to get relay status")
        return None

    def _validate_channel(self, channel: int) -> None:
        """
        Validate relay channel number.

        Args:
            channel: Channel number to validate

        Raises:
            ValueError: If channel is not in valid range
        """
        if not 0 <= channel <= 5:
            raise ValueError(f"Invalid channel {channel}. Must be 0-5")

    def _send_command(self, command: str) -> bool:
        """
        Send a command to the Arduino device.

        Args:
            command: Command string to send

        Returns:
            bool: True if command was sent successfully
        """
        if not self.is_connected():
            logger.error("No active connection to Arduino")
            return False
        try:
            cmd_bytes = f"{command}\n".encode('utf-8')
            self.connection.write(cmd_bytes)
            self.connection.flush()
            logger.debug(f"Command sent: {command}")
            return True
        except Exception as e:
            logger.error(f"Error sending command '{command}': {e}")
            return False

    def _read_response(self, max_lines: int = 10) -> Optional[str]:
        """
        Read response from the Arduino device.

        Args:
            max_lines: Maximum number of lines to read

        Returns:
            Optional[str]: Response from Arduino or None if error occurred
        """
        if not self.is_connected():
            logger.error("No active connection to Arduino")
            return None
        try:
            response_lines = []
            for _ in range(max_lines):
                line = self.connection.readline().decode('utf-8').strip()
                if line:
                    response_lines.append(line)
                    # Check for terminal response indicators
                    if any(indicator in line for indicator in
                           [ArduinoResponses.STATUS_OK, ArduinoResponses.ERROR,
                            ArduinoResponses.OK, ArduinoResponses.DEVICE_ID]):
                        break
                else:
                    break
            response = '\n'.join(response_lines) if response_lines else None
            logger.debug(f"Response received: {response}")
            return response
        except Exception as e:
            logger.error(f"Error reading response: {e}")
            return None

    def _is_success_response(self, response: Optional[str]) -> bool:
        """
        Check if response indicates successful operation.

        Args:
            response: Response string from Arduino

        Returns:
            bool: True if response indicates success
        """
        if not response:
            return False
        return (ArduinoResponses.STATUS_OK in response or
                ArduinoResponses.OK in response) and ArduinoResponses.ERROR not in response

    def _parse_status_response(self, response: str) -> Dict[str, Any]:
        """
        Parse status response into structured data.

        Args:
            response: Raw status response from Arduino

        Returns:
            Dict[str, Any]: Parsed status information
        """
        # Basic parsing - can be extended based on actual Arduino response format
        return {
            'raw_response': response,
            'timestamp': time.time(),
            'connected': True
        }

    def _cleanup_connection(self) -> None:
        """Clean up connection resources."""
        if self.connection:
            try:
                self.connection.close()
            except Exception as e:
                logger.debug(f"Error during connection cleanup: {e}")
            finally:
                self.connection = None

    def __enter__(self):
        """Context manager entry."""
        if not self.connect():
            raise RuntimeError("Failed to connect to Arduino")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create and configure the command-line argument parser.

    Returns:
        argparse.ArgumentParser: Configured parser
    """
    parser = argparse.ArgumentParser(
        description="Professional Arduino Relay Controller for labgrid integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage Examples:
  %(prog)s on 0                    # Turn on relay channel 0
  %(prog)s off 1                   # Turn off relay channel 1  
  %(prog)s status                  # Show status of all relays
  %(prog)s all-off                 # Turn off all relays
  %(prog)s --port /dev/ttyUSB0 status  # Use custom port

Error Codes:
  0 - Success
  1 - Connection error
  2 - Command execution error
  3 - Invalid arguments
        """
    )

    # Global options
    parser.add_argument(
        '--port',
        default='/dev/arduino-relay',
        help='Serial port path (default: /dev/arduino-relay)'
    )
    parser.add_argument(
        '--baudrate',
        type=int,
        default=115200,
        help='Serial communication speed (default: 115200)'
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=2.0,
        help='Communication timeout in seconds (default: 2.0)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging output'
    )
    # Subcommands
    subparsers = parser.add_subparsers(dest='action', help='Available actions')
    # ON command
    on_parser = subparsers.add_parser('on', help='Turn on a relay channel')
    on_parser.add_argument(
        'channel',
        type=int,
        choices=range(6),
        help='Relay channel number (0-5)'
    )
    # OFF command
    off_parser = subparsers.add_parser('off', help='Turn off a relay channel')
    off_parser.add_argument(
        'channel',
        type=int,
        choices=range(6),
        help='Relay channel number (0-5)'
    )
    # STATUS command
    subparsers.add_parser('status', help='Show status of all relay channels')
    # ALL-OFF command
    subparsers.add_parser('all-off', help='Turn off all relay channels')

    return parser

def main() -> int:
    """
    Main entry point for command-line usage.

    Returns:
        int: Exit code (0 for success, non-zero for errors)
    """
    parser = create_argument_parser()
    args = parser.parse_args()
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    if not args.action:
        parser.print_help()
        return 3
    # Create and connect to controller
    controller = ArduinoRelayController(
        port=args.port,
        baudrate=args.baudrate,
        timeout=args.timeout
    )
    if not controller.connect():
        logger.error("Failed to connect to Arduino device")
        return 1

    try:
        # Execute requested action
        success = False
        if args.action == 'on':
            success = controller.relay_on(args.channel)
        elif args.action == 'off':
            success = controller.relay_off(args.channel)
        elif args.action == 'status':
            status = controller.get_status()
            success = status is not None
            if success and status:
                print(f"Relay Status: {status['raw_response']}")
        elif args.action == 'all-off':
            success = controller.all_relays_off()
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
