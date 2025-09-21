#!/usr/bin/env python3
"""
Script para verificar comunicación serial con router
"""

import serial
import time
import sys
import argparse

def test_communication(port, baudrate=115200, timeout=2):
    """
    Prueba la comunicación serial con el router.

    Args:
        port: Puerto serial (ej: /dev/glinet-mango)
        baudrate: Velocidad de comunicación
        timeout: Timeout para operaciones

    Returns:
        tuple: (success, response_text)
    """
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False
        )

        # Limpiar buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        # Esperar y enviar Enter varias veces
        time.sleep(1)
        for i in range(5):
            ser.write(b'\r\n')
            ser.flush()
            time.sleep(0.5)

        # Enviar comando de prueba
        ser.write(b'echo "ROUTER_TEST_OK"\r\n')
        ser.flush()
        time.sleep(1)

        # Leer respuesta
        response = ser.read(500).decode('utf-8', errors='ignore')
        ser.close()

        return True, response.strip()

    except Exception as e:
        return False, str(e)


def main():
    """Función principal para uso desde línea de comandos."""
    parser = argparse.ArgumentParser(description="Verificar comunicación serial con router")
    parser.add_argument('port', help='Puerto serial (ej: /dev/glinet-mango)')
    parser.add_argument('--baudrate', type=int, default=115200, help='Velocidad de comunicación')
    parser.add_argument('--timeout', type=float, default=2.0, help='Timeout para operaciones')
    parser.add_argument('--verbose', '-v', action='store_true', help='Mostrar respuesta completa')

    args = parser.parse_args()

    success, response = test_communication(args.port, args.baudrate, args.timeout)

    if success and response:
        print('✅ Router responde por serial')
        if args.verbose:
            print(f'   Respuesta completa: {repr(response)}')
        else:
            print(f'   Respuesta: {response[:100]}...' if len(response) > 100 else f'   Respuesta: {response}')
        return 0
    elif success:
        print('⚠️  Router conectado pero sin respuesta')
        return 1
    else:
        print(f'❌ Error en comunicación: {response}')
        return 1


if __name__ == "__main__":
    sys.exit(main())