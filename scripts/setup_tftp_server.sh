#!/bin/bash
# Script para configurar e instalar un servidor TFTP para recovery con U-Boot.
#
# Este script:
# - Instala 'tftpd-hpa' (servidor TFTP de alta disponibilidad).
# - Crea el directorio raíz para los archivos TFTP (/srv/tftp).
# - Configura 'tftpd-hpa' para iniciar automáticamente al boot.
# - Proporciona comandos útiles para la administración del servicio.

set -e

TFTP_ROOT="/srv/tftp"
TFTP_USER="tftp"
SERVICE_NAME="tftpd-hpa"

echo "=== Configurando Servidor TFTP para Recovery con U-Boot ==="

# 1. Instalar tftpd-hpa
echo "1. Instalando paquete '$SERVICE_NAME'..."
sudo apt-get update
sudo apt-get install -y "$SERVICE_NAME"

# 2. Crear y configurar directorio raíz del TFTP
echo "2. Creando y configurando directorio raíz del TFTP: $TFTP_ROOT"
sudo mkdir -p "$TFTP_ROOT"
sudo chown -R "$TFTP_USER:$TFTP_USER" "$TFTP_ROOT"
sudo chmod -R 755 "$TFTP_ROOT"

# 3. Configurar tftpd-hpa
echo "3. Configurando archivo '/etc/default/$SERVICE_NAME'..."
sudo tee "/etc/default/$SERVICE_NAME" > /dev/null <<EOF
# /etc/default/tftpd-hpa
# Configuración para el servidor TFTP de alta disponibilidad.

TFTP_USERNAME="$TFTP_USER"
TFTP_DIRECTORY="$TFTP_ROOT"
TFTP_ADDRESS="0.0.0.0:69"
TFTP_OPTIONS="--secure --create"
EOF

# 4. Iniciar y habilitar el servicio
echo "4. Iniciando y habilitando el servicio '$SERVICE_NAME' para que inicie automáticamente al boot..."
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl enable "$SERVICE_NAME"

echo ""
echo "=== Servidor TFTP Configuraciń Finalizada ==="
echo "Directorio raíz para archivos TFTP: $TFTP_ROOT"
echo "Estado actual del servidor TFTP:"
sudo systemctl status "$SERVICE_NAME" --no-pager
echo ""

echo "--- Comandos Útiles para el Servidor TFTP ---"
echo ""
echo "• Para VERIFICAR el estado del servicio:"
echo "    sudo systemctl status $SERVICE_NAME"
echo ""
echo "• Para REINICIAR el servicio:"
echo "    sudo systemctl restart $SERVICE_NAME"
echo ""
echo "• Para DETENER el servicio (apagarlo):"
echo "    sudo systemctl stop $SERVICE_NAME"
echo ""
echo "• Para INICIAR el servicio (si está detenido):"
echo "    sudo systemctl start $SERVICE_NAME"
echo ""
echo "• Para DESHABILITAR el inicio automático al boot:"
echo "    sudo systemctl disable $SERVICE_NAME"
echo ""
echo "• Para HABILITAR el inicio automático al boot (ya habilitado por este script):"
echo "    sudo systemctl enable $SERVICE_NAME"
echo ""
echo "----------------------------------------------"
echo "Asegúrate de copiar los archivos de firmware (.itb) al directorio '$TFTP_ROOT'."
echo "----------------------------------------------"
