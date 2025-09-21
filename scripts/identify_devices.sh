#!/bin/bash
# Script para identificar dispositivos seriales y generar regla udev

echo "=== Identificación de Dispositivos Seriales USB ==="
echo
echo "1. Buscando dispositivos seriales conectados..."
serial_devices=$(lsusb | grep -i "arduino\|ch340\|cp210\|ftdi\|pl2303\|usb-serial\|uart\|bridge")
if [ -z "$serial_devices" ]; then
    echo "No se encontraron dispositivos seriales USB conocidos."
    echo "Mostrando todos los dispositivos USB:"
    lsusb
    echo
    echo "Verifica que los dispositivos estén conectados y detectados por el sistema."
    exit 1
fi
echo "Dispositivos encontrados:"
echo "$serial_devices"
echo
echo "2. Puertos serie disponibles:"
ls -la /dev/tty* | grep -E "(USB|ACM)" || echo "No se encontraron puertos USB/ACM"
echo
echo "3. Información detallada de dispositivos:"
for device in /dev/ttyUSB* /dev/ttyACM*; do
    if [ -e "$device" ]; then
        echo "--- Dispositivo: $device ---"
        udevadm info -a -n "$device" | grep -E "(KERNEL|SUBSYSTEM|DRIVER|ATTRS\{idVendor\}|ATTRS\{idProduct\}|ATTRS\{serial\}|ATTRS\{product\}|ATTRS\{manufacturer\})" | head -10
        echo
    fi
done
echo "=== Creación de regla udev ==="
echo
echo "1. Identificar el dispositivo que a mapear en la lista anterior"
echo "2. Anotar los valores de idVendor, idProduct y serial (si está disponible)"
echo "3. Ejecutar el siguiente comando para crear la regla:"
echo
echo "sudo nano /etc/udev/rules.d/99-serial-devices.rules"
echo
echo "4. Agrega una línea similar a esta (reemplazar valores):"
echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="XXXX", ATTRS{idProduct}=="YYYY", SYMLINK+="nombre-descriptivo", MODE="0666", GROUP="dialout"'
echo
echo "5. Si el modelo tiene número de serie único disponible, es recomendable usarlo para mayor precisión:"
echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="XXXX", ATTRS{idProduct}=="YYYY", ATTRS{serial}=="ZZZZ", SYMLINK+="nombre-descriptivo", MODE="0666", GROUP="dialout"'
echo
echo "6. Recargar las reglas udev:"
echo "sudo udevadm control --reload-rules"
echo "sudo udevadm trigger"
echo
echo "7. Desconectar y reconectar el dispositivo, luego verificar:"
echo "ls -la /dev/nombre-descriptivo"
