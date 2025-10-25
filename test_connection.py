#!/usr/bin/env python3
"""
Teste de Conexão - GP2Y0A41SK0F com ADS1115
Verifica se o hardware está conectado corretamente
(Este arquivo é um utilitário standalone e não precisa de modificação)
"""

import time
import sys
import os

print("\n" + "="*50)
print("TESTE DE CONEXÃO - GP2Y0A41SK0F + ADS1115")
print("="*50)

# Teste 0: Verificar se I2C está habilitado
print("\n[1/5] Verificando se I2C está habilitado...")
if not os.path.exists('/dev/i2c-1'):
    print("✗ Interface I2C '/dev/i2c-1' não encontrada.")
    print("\nVerifique:")
    print("- I2C está habilitado? (Execute 'sudo raspi-config')")
    print("- Execute 'sudo apt-get install i2c-tools'")
    sys.exit(1)
print("✓ Interface I2C '/dev/i2c-1' encontrada.")

# Teste 1: Importar bibliotecas
print("\n[2/5] Importando bibliotecas (board, busio, adafruit_ads1x15)...")
try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    print("✓ Bibliotecas importadas com sucesso")
except ImportError as e:
    print(f"✗ Erro ao importar biblioteca: {e}")
    print("Execute o script 'install.sh' para instalar as dependências.")
    sys.exit(1)
except Exception as e:
    print(f"✗ Erro inesperado ao importar: {e}")
    sys.exit(1)

# Teste 2: Inicializar I2C
print("\n[3/5] Verificando interface I2C...")
try:
    i2c = busio.I2C(board.SCL, board.SDA)
    print("✓ I2C inicializado com sucesso")
except Exception as e:
    print(f"✗ Erro ao inicializar I2C: {e}")
    print("\nVerifique:")
    print("- Conexões SDA/SCL estão corretas? (GPIO 2 e 3)")
    print("- O usuário '$USER' está no grupo 'i2c'?")
    sys.exit(1)

# Teste 3: Detectar ADS1115
print("\n[4/5] Procurando ADS1115...")
try:
    ads = ADS.ADS1115(i2c)
    print("✓ ADS1115 detectado")
    print(f"  Endereço I2C: 0x48 (padrão)")
except Exception as e:
    print(f"✗ ADS1115 não encontrado: {e}")
    print("\nVerifique:")
    print("- ADS1115 está conectado corretamente?")
    print("- VDD e GND do ADS1115 estão conectados?")
    print("- ADDR do ADS1115 está conectado ao GND?")
    print("\nExecute 'i2cdetect -y 1' para verificar dispositivos I2C")
    sys.exit(1)

# Teste 4: Configurar e Ler Sensor
print("\n[5/5] Lendo sensor GP2Y0A41SK0F...")
try:
    ads.gain = 1
    ads.data_rate = 128
    channel = AnalogIn(ads, ADS.P0)
    print("✓ Canal A0 configurado")
    print("\n" + "-"*50)
    print("Lendo valores por 10 segundos... (Mova um objeto na frente do sensor)")
    print("-"*50)

    start_time = time.time()
    readings = []
    min_v = float('inf')
    max_v = 0

    while time.time() - start_time < 10:
        voltage = channel.voltage
        value = channel.value
        readings.append(voltage)
        min_v = min(min_v, voltage)
        max_v = max(max_v, voltage)

        if voltage > 0.3:
            distance = 12 / (voltage - 0.04) - 0.42
            distance = max(4, min(30, distance))
        else:
            distance = 30

        bar_len = int(voltage / 3.3 * 40)
        bar = "█" * bar_len + "░" * (40 - bar_len)

        print(f"\rTensão: {voltage:.3f}V [{bar}] ~{distance:.1f}cm | ADC: {value:5d}", end="")
        time.sleep(0.1)

    # Estatísticas
    print("\n\n" + "="*50)
    print("RESULTADOS DO TESTE:")
    print("="*50)
    avg_voltage = sum(readings) / len(readings)
    print(f"✓ Leituras realizadas: {len(readings)}")
    print(f"✓ Tensão média: {avg_voltage:.3f}V")
    print(f"✓ Tensão mínima: {min_v:.3f}V")
    print(f"✓ Tensão máxima: {max_v:.3f}V")
    print(f"✓ Variação: {max_v - min_v:.3f}V")

    # Diagnóstico
    print("\nDIAGNÓSTICO:")
    if max_v - min_v < 0.1:
        print("⚠ Pouca variação detectada. Verifique as conexões do sensor (Vcc, Gnd, Vo).")
    elif avg_voltage < 0.2:
        print("⚠ Tensão muito baixa. Verifique a alimentação 5V do sensor.")
    elif avg_voltage > 3.5:
        print("⚠ Tensão muito alta. Objeto muito próximo (<4cm) ou curto?")
    else:
        print("✓ Sensor funcionando normalmente!")

    print("\n✓ TESTE CONCLUÍDO COM SUCESSO!")

except KeyboardInterrupt:
    print("\n\nTeste interrompido")
except Exception as e:
    print(f"\n\n✗ Erro durante leitura: {e}")
    sys.exit(1)
