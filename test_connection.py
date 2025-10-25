#!/usr/bin/env python3
"""
Teste de Conexão - GP2Y0A41SK0F com ADS1115
Verifica se o hardware está conectado corretamente
"""

import time
import sys

print("\n" + "="*50)
print("TESTE DE CONEXÃO - GP2Y0A41SK0F + ADS1115")
print("="*50)

# Teste 1: Verificar I2C
print("\n[1/4] Verificando interface I2C...")
try:
    import board
    import busio
    i2c = busio.I2C(board.SCL, board.SDA)
    print("✓ I2C inicializado com sucesso")
except Exception as e:
    print(f"✗ Erro ao inicializar I2C: {e}")
    print("\nVerifique:")
    print("- I2C está habilitado? (sudo raspi-config)")
    print("- Conexões SDA/SCL estão corretas?")
    sys.exit(1)

# Teste 2: Detectar ADS1115
print("\n[2/4] Procurando ADS1115...")
try:
    import adafruit_ads1x15.ads1115 as ADS
    ads = ADS.ADS1115(i2c)
    print("✓ ADS1115 detectado")
    print(f"  Endereço I2C: 0x48 (padrão)")
except Exception as e:
    print(f"✗ ADS1115 não encontrado: {e}")
    print("\nVerifique:")
    print("- ADS1115 está conectado corretamente?")
    print("- VDD conectado a 3.3V ou 5V?")
    print("- GND conectado?")
    print("- SDA conectado ao pino 2 (GPIO2)?")
    print("- SCL conectado ao pino 3 (GPIO3)?")
    print("\nExecute 'i2cdetect -y 1' para verificar dispositivos I2C")
    sys.exit(1)

# Teste 3: Configurar canal analógico
print("\n[3/4] Configurando canal analógico...")
try:
    from adafruit_ads1x15.analog_in import AnalogIn

    # Configura ganho e taxa de amostragem
    ads.gain = 1  # Ganho 1 = ±4.096V
    ads.data_rate = 128  # 128 amostras por segundo

    # Canal 0 (A0)
    channel = AnalogIn(ads, ADS.P0)
    print("✓ Canal A0 configurado")
    print(f"  Ganho: 1 (±4.096V)")
    print(f"  Taxa: 128 SPS")
except Exception as e:
    print(f"✗ Erro ao configurar canal: {e}")
    sys.exit(1)

# Teste 4: Ler sensor
print("\n[4/4] Lendo sensor GP2Y0A41SK0F...")
print("\nCONEXÕES DO SENSOR:")
print("- Sensor Vcc → 5V")
print("- Sensor GND → GND")
print("- Sensor Vo → ADS1115 A0")
print("- ADS1115 VDD → 3.3V ou 5V")
print("- ADS1115 GND → GND")
print("- ADS1115 SCL → RPi GPIO3 (Pino 5)")
print("- ADS1115 SDA → RPi GPIO2 (Pino 3)")
print("- ADS1115 ADDR → GND (endereço 0x48)")

print("\n" + "-"*50)
print("Lendo valores por 10 segundos...")
print("(Mova um objeto na frente do sensor)")
print("-"*50)

try:
    start_time = time.time()
    readings = []
    min_v = float('inf')
    max_v = 0

    while time.time() - start_time < 10:
        # Lê tensão
        voltage = channel.voltage
        value = channel.value

        readings.append(voltage)
        min_v = min(min_v, voltage)
        max_v = max(max_v, voltage)

        # Estimativa de distância (fórmula simplificada)
        if voltage > 0.3:
            distance = 12 / (voltage - 0.04) - 0.42
            distance = max(4, min(30, distance))
        else:
            distance = 30

        # Display
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
        print("⚠ Pouca variação detectada")
        print("  Possíveis causas:")
        print("  - Sensor não conectado corretamente")
        print("  - Sensor sem alimentação")
        print("  - Nenhum objeto no range (4-30cm)")
    elif avg_voltage < 0.2:
        print("⚠ Tensão muito baixa")
        print("  - Verifique alimentação do sensor (5V)")
    elif avg_voltage > 3.5:
        print("⚠ Tensão muito alta")
        print("  - Objeto muito próximo?")
        print("  - Verifique conexões")
    else:
        print("✓ Sensor funcionando normalmente!")
        print(f"  Range de tensão esperado: 0.3V - 3.1V")
        print(f"  Seu range: {min_v:.2f}V - {max_v:.2f}V")

    print("\n✓ TESTE CONCLUÍDO COM SUCESSO!")
    print("\nPróximo passo: python3 sensor_distance.py")

except KeyboardInterrupt:
    print("\n\nTeste interrompido pelo usuário")
except Exception as e:
    print(f"\n\n✗ Erro durante leitura: {e}")
    sys.exit(1)