#!/bin/bash

# Script de instalação para GP2Y0A41SK0F com ADS1115
# Raspberry Pi 4

echo "========================================"
echo "Instalador - Sensor GP2Y0A41SK0F"
echo "========================================"

# Atualiza sistema
echo "Atualizando sistema..."
sudo apt-get update

# Instala dependências do sistema
echo "Instalando dependências do sistema..."
sudo apt-get install -y python3-pip python3-dev i2c-tools python3-matplotlib

# Habilita I2C
echo "Habilitando I2C..."
sudo raspi-config nonint do_i2c 0

# Instala bibliotecas Python
echo "Instalando bibliotecas Python..."
pip3 install --break-system-packages adafruit-circuitpython-ads1x15
pip3 install --break-system-packages numpy scipy matplotlib

# Adiciona usuário ao grupo i2c
sudo usermod -a -G i2c $USER

echo ""
echo "✓ Instalação concluída!"
echo ""
echo "PRÓXIMOS PASSOS:"
echo "1. Reinicie o Raspberry Pi: sudo reboot"
echo "2. Verifique I2C: i2cdetect -y 1"
echo "   (ADS1115 deve aparecer no endereço 0x48)"
echo "3. Execute o teste: python3 test_connection.py"
echo "4. Execute o sistema: python3 sensor_distance.py"