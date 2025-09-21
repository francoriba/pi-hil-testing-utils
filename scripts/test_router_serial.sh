#!/bin/bash
# Test de comunicación serial con router GL-MT300N-V2
# ==================================================

echo "=== Diagnóstico de comunicación serial ==="

ROUTER_PORT="/dev/glinet-mango"
ARDUINO_SCRIPT="/home/franco/pi/pi-hil-testing-utils/scripts/arduino_relay_control.py"
CHECK_CONN_SCRIPT="/home/franco/pi/pi-hil-testing-utils/scripts/check_router_serial_conn.py"
BAUDRATE=115200
WAIT_BEFORE_POWER=1     # Segundos antes de encender router
WAIT_AFTER_POWER=5      # Segundos para que arranque router
WAIT_AFTER_SERIAL=5     # Segundos antes de probar comunicación

if [ ! -e "$ROUTER_PORT" ]; then
    echo "❌ Error: $ROUTER_PORT no existe"
    exit 1
fi
echo "✅ Puerto $ROUTER_PORT existe"
echo "Permisos del puerto:"
ls -la "$ROUTER_PORT"
echo "Verificando si el puerto está en uso:"
lsof "$ROUTER_PORT" || echo "Puerto no está en uso por otro proceso"
echo
echo "=== Test de comunicación serial ==="
echo "Asegurando que el router está encendido..."
python3 "$ARDUINO_SCRIPT" on 1
python3 "$ARDUINO_SCRIPT" off 0
sleep $WAIT_AFTER_POWER
python3 "$ARDUINO_SCRIPT" off 1
sleep $WAIT_AFTER_SERIAL
echo "Probando comunicación serial con baudrate $BAUDRATE..."
python3 "$CHECK_CONN_SCRIPT" "$ROUTER_PORT" $BAUDRATE
echo
echo "Para validación manual, usar:"
echo "  screen $ROUTER_PORT $BAUDRATE"
echo "  (Ctrl+A, K para salir)"
