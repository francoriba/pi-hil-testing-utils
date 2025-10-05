#!/bin/bash
# Verification script for U-Boot recovery setup

set -e

echo "=== Verifying U-Boot Recovery Setup ==="
echo ""

# Check TFTP server
echo "1. Checking TFTP server..."
if systemctl is-active --quiet tftpd-hpa; then
    echo "   ✓ TFTP server is running"
    TFTP_ROOT=$(grep TFTP_DIRECTORY /etc/default/tftpd-hpa | cut -d'"' -f2)
    echo "   ✓ TFTP root: $TFTP_ROOT"
else
    echo "   ✗ TFTP server not running"
    echo "   Run: ./pi-hil-testing-utils/scripts/setup_tftp_server.sh"
    exit 1
fi

# Check network connectivity
echo ""
echo "2. Checking network configuration..."
PI_IP="192.168.20.234" # Cambiar a la IP de tu PC
if ip addr show | grep -q "$PI_IP"; then
    echo "   ✓ Pi has IP: $PI_IP"
else
    echo "   ⚠ Pi doesn't have expected IP: $PI_IP"
    echo "   Current IPs:"
    ip -4 -br addr show
    echo "   Please ensure your PC has the IP $PI_IP configured."
fi

# Check firmware image
echo ""
echo "3. Checking firmware availability..."
if [ -n "$1" ]; then
    if [ -f "$1" ]; then
        echo "   ✓ Firmware image found: $1"
        SIZE=$(du -h "$1" | cut -f1)
        echo "   ✓ Size: $SIZE"
    else
        echo "   ✗ Firmware image not found: $1"
        exit 1
    fi
else
    echo "   ℹ No firmware path provided (optional)"
fi

# Test TFTP access
echo ""
echo "4. Testing TFTP server access..."
TEST_FILE="$TFTP_ROOT/test.txt"
echo "TFTP test file" | sudo tee "$TEST_FILE" > /dev/null
sudo chown tftp:tftp "$TEST_FILE" # Asegurar que el archivo de test tiene el propietario correcto
sudo chmod 644 "$TEST_FILE"      # Asegurar que el archivo de test tiene permisos de lectura

# Corregir la sintaxis de tftp para descarga no interactiva usando pipe
if echo "get test.txt /tmp/tftp_test.txt" | tftp "$PI_IP" 2>/dev/null; then
    echo "   ✓ TFTP GET works"
    rm -f /tmp/tftp_test.txt
else
    echo "   ✗ TFTP GET failed from $PI_IP"
    exit 1
fi
sudo rm -f "$TEST_FILE"

echo ""
echo "=== U-Boot Recovery Setup Verified ==="
echo ""
