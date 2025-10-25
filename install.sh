#!/bin/bash

# Script de instalação para GP2Y0A41SK0F com ADS1115 e Scanner
# Raspberry Pi 4

echo "========================================"
echo "Instalador - Scanner 3D e Sensor"
echo "========================================"

# Atualiza sistema
echo "[1/5] Atualizando sistema..."
sudo apt-get update -y

# Instala dependências do sistema
echo "[2/5] Instalando dependências do sistema..."
sudo apt-get install -y python3-pip python3-dev i2c-tools python3-matplotlib python3-scipy

# Instala pigpio (ESSENCIAL para o motor)
echo "[3/5] Instalando PIGPIO para controle do motor..."
sudo apt-get install -y python3-pigpio
# Se o comando acima falhar (ex: em RPi OS Bookworm),
# será necessário compilar da fonte.
# Descomente as linhas abaixo se a instalação apt falhar:
# echo "Instalação 'apt' do pigpio falhou, tentando compilar da fonte..."
# sudo apt-get install -y build-essential
# wget https://github.com/joan2937/pigpio/archive/master.zip
# unzip master.zip
# cd pigpio-master
# make
# sudo make install
# cd ..
# sudo rm -rf pigpio-master master.zip

# Instala bibliotecas Python via PIP
echo "[4/5] Instalando bibliotecas Python (pip)..."
pip3 install --break-system-packages adafruit-circuitpython-ads1x15
pip3 install --break-system-packages numpy

# Habilita I2C e adiciona usuário ao grupo
echo "[5/5] Configurando I2C..."
if ! grep -q "^dtparam=i2c_arm=on$" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt > /dev/null
    echo "I2C habilitado em /boot/config.txt"
else
    echo "I2C já está habilitado."
fi
sudo usermod -a -G i2c $USER

echo ""
echo "✓ Instalação concluída!"
echo ""
echo "========================================"
echo "IMPORTANTE: REINICIE O RASPBERRY PI"
echo "========================================"
echo "1. Reinicie agora: sudo reboot"
echo "2. Após reiniciar, verifique o I2C: i2cdetect -y 1 (deve mostrar '48')"
echo "3. Teste o hardware: python3 test_connection.py"
echo "4. Inicie o daemon pigpio: sudo systemctl start pigpiod"
echo "5. Execute o programa: python3 scanner_main.py"
