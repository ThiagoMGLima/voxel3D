#!/usr/bin/env python3
"""
Sistema de Alta Precisão para Sensor GP2Y0A41SK0F
Sensor de distância IR Sharp (4-30cm) com ADS1115
"""

import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import numpy as np
from scipy import signal, interpolate
from collections import deque
import json
import matplotlib.pyplot as plt
from datetime import datetime
import threading

class GP2Y0A41SK0F:
    """Classe para sensor de distância Sharp GP2Y0A41SK0F com calibração avançada"""

    def __init__(self, ads_channel=0, gain=1, samples_rate=128):
        """
        Inicializa o sensor
        Args:
            ads_channel: Canal do ADS1115 (0-3)
            gain: Ganho do ADC (2/3, 1, 2, 4, 8, 16)
            samples_rate: Taxa de amostragem (8, 16, 32, 64, 128, 250, 475, 860)
        """
        # Configuração I2C e ADS1115
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.ads = ADS.ADS1115(self.i2c)
        self.ads.gain = gain
        self.ads.data_rate = samples_rate

        # Canal analógico
        channels = [ADS.Pin.A0, ADS.Pin.P1, ADS.Pin.P2, ADS.Pin.P3]
        self.channel = AnalogIn(self.ads, channels[ads_channel])

        # Parâmetros do sensor GP2Y0A41SK0F
        self.min_distance = 4.0   # cm
        self.max_distance = 30.0  # cm
        self.voltage_at_4cm = 3.1  # V típico
        self.voltage_at_30cm = 0.3 # V típico

        # Buffers para filtragem
        self.buffer_size = 10
        self.voltage_buffer = deque(maxlen=self.buffer_size)
        self.distance_buffer = deque(maxlen=self.buffer_size)

        # Calibração
        self.calibration_points = []
        self.interpolation_func = None
        self.load_calibration()

        # Filtro Kalman
        self.kalman_enabled = True
        self.kalman_q = 0.01  # Ruído do processo
        self.kalman_r = 0.1   # Ruído da medição
        self.kalman_p = 1.0   # Estimativa inicial do erro
        self.kalman_x = 15.0  # Estimativa inicial da distância

        # Estatísticas
        self.readings_count = 0
        self.last_reading_time = time.time()

    def read_voltage(self, samples=10):
        """Lê a tensão com média de múltiplas amostras"""
        voltages = []
        for _ in range(samples):
            voltages.append(self.channel.voltage)
            time.sleep(0.001)  # 1ms entre leituras

        # Remove outliers usando IQR
        q1, q3 = np.percentile(voltages, [25, 75])
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        filtered = [v for v in voltages if lower_bound <= v <= upper_bound]

        if not filtered:
            filtered = voltages

        voltage = np.mean(filtered)
        self.voltage_buffer.append(voltage)
        return voltage

    def voltage_to_distance_default(self, voltage):
        """Converte tensão em distância usando a curva característica do sensor"""
        # Curva característica do GP2Y0A41SK0F (aproximação)
        # Baseado no datasheet: V = k / (d + offset)

        if voltage < 0.25:
            return self.max_distance
        if voltage > 3.3:
            return self.min_distance

        # Fórmula empírica para GP2Y0A41SK0F
        # Ajustada para o range de 4-30cm
        try:
            # Modelo: distance = a / (voltage - b) - c
            # Valores típicos para este sensor
            a = 12.0
            b = 0.04
            c = 0.42

            distance = a / (voltage - b) - c

            # Limita ao range do sensor
            distance = np.clip(distance, self.min_distance, self.max_distance)

        except:
            distance = self.max_distance

        return distance

    def voltage_to_distance(self, voltage):
        """Converte tensão em distância usando calibração ou curva padrão"""
        if self.interpolation_func is not None:
            # Usa calibração personalizada
            distance = float(self.interpolation_func(voltage))
        else:
            # Usa curva característica padrão
            distance = self.voltage_to_distance_default(voltage)

        # Aplica limites físicos do sensor
        distance = np.clip(distance, self.min_distance, self.max_distance)

        return distance

    def kalman_filter(self, measurement):
        """Aplica filtro Kalman para suavizar leituras"""
        if not self.kalman_enabled:
            return measurement

        # Predição
        self.kalman_p = self.kalman_p + self.kalman_q

        # Atualização
        k = self.kalman_p / (self.kalman_p + self.kalman_r)
        self.kalman_x = self.kalman_x + k * (measurement - self.kalman_x)
        self.kalman_p = (1 - k) * self.kalman_p

        return self.kalman_x

    def read_distance(self, filtered=True):
        """Lê a distância com opção de filtragem"""
        voltage = self.read_voltage()
        distance = self.voltage_to_distance(voltage)

        if filtered:
            distance = self.kalman_filter(distance)
            self.distance_buffer.append(distance)

            # Média móvel ponderada
            if len(self.distance_buffer) > 3:
                weights = np.exp(np.linspace(-1, 0, len(self.distance_buffer)))
                weights /= weights.sum()
                distance = np.average(list(self.distance_buffer), weights=weights)

        self.readings_count += 1
        self.last_reading_time = time.time()

        return distance

    def calibrate_point(self, actual_distance):
        """Adiciona um ponto de calibração"""
        print(f"\nCalibrando para {actual_distance}cm...")
        print("Coletando 50 amostras...")

        voltages = []
        for i in range(50):
            v = self.read_voltage(samples=5)
            voltages.append(v)
            print(f"\rProgresso: {i+1}/50 - Tensão: {v:.3f}V", end="")
            time.sleep(0.1)

        avg_voltage = np.mean(voltages)
        std_voltage = np.std(voltages)

        self.calibration_points.append({
            'distance': actual_distance,
            'voltage': avg_voltage,
            'std': std_voltage
        })

        print(f"\n✓ Calibrado: {actual_distance}cm = {avg_voltage:.3f}V (±{std_voltage:.3f}V)")

        # Ordena pontos por distância
        self.calibration_points.sort(key=lambda x: x['distance'])

        # Atualiza interpolação se temos pontos suficientes
        if len(self.calibration_points) >= 3:
            self.update_interpolation()

        return avg_voltage, std_voltage

    def update_interpolation(self):
        """Atualiza função de interpolação com pontos calibrados"""
        if len(self.calibration_points) < 3:
            print("Necessário pelo menos 3 pontos para interpolação")
            return

        voltages = [p['voltage'] for p in self.calibration_points]
        distances = [p['distance'] for p in self.calibration_points]

        # Cria função de interpolação cúbica
        self.interpolation_func = interpolate.interp1d(
            voltages, distances,
            kind='cubic',
            bounds_error=False,
            fill_value=(self.max_distance, self.min_distance)
        )

        print(f"✓ Interpolação atualizada com {len(self.calibration_points)} pontos")

    def save_calibration(self, filename="sensor_calibration.json"):
        """Salva calibração em arquivo"""
        data = {
            'sensor': 'GP2Y0A41SK0F',
            'timestamp': datetime.now().isoformat(),
            'calibration_points': self.calibration_points,
            'kalman_params': {
                'q': self.kalman_q,
                'r': self.kalman_r
            }
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"✓ Calibração salva em {filename}")

    def load_calibration(self, filename="sensor_calibration.json"):
        """Carrega calibração de arquivo"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)

            self.calibration_points = data['calibration_points']

            if 'kalman_params' in data:
                self.kalman_q = data['kalman_params']['q']
                self.kalman_r = data['kalman_params']['r']

            if len(self.calibration_points) >= 3:
                self.update_interpolation()

            print(f"✓ Calibração carregada: {len(self.calibration_points)} pontos")
            return True
        except:
            print("⚠ Nenhuma calibração encontrada, usando curva padrão")
            return False

    def plot_calibration_curve(self):
        """Plota curva de calibração"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        # Gera pontos para plotagem
        voltages = np.linspace(0.2, 3.3, 100)

        # Curva padrão
        distances_default = [self.voltage_to_distance_default(v) for v in voltages]
        ax1.plot(voltages, distances_default, 'b-', label='Curva Padrão', alpha=0.5)

        # Curva calibrada
        if self.interpolation_func is not None:
            distances_calibrated = [self.voltage_to_distance(v) for v in voltages]
            ax1.plot(voltages, distances_calibrated, 'r-', label='Curva Calibrada', linewidth=2)

        # Pontos de calibração
        if self.calibration_points:
            cal_v = [p['voltage'] for p in self.calibration_points]
            cal_d = [p['distance'] for p in self.calibration_points]
            cal_std = [p['std'] for p in self.calibration_points]

            ax1.errorbar(cal_v, cal_d, xerr=cal_std, fmt='go',
                        markersize=8, label='Pontos Calibrados', capsize=5)

        ax1.set_xlabel('Tensão (V)')
        ax1.set_ylabel('Distância (cm)')
        ax1.set_title('Curva de Calibração GP2Y0A41SK0F')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim([0, 3.5])
        ax1.set_ylim([0, 35])

        # Gráfico de erro
        if self.interpolation_func is not None and self.calibration_points:
            errors = []
            distances = []

            for point in self.calibration_points:
                measured = point['distance']
                predicted = float(self.interpolation_func(point['voltage']))
                error = predicted - measured
                errors.append(error)
                distances.append(measured)

            ax2.scatter(distances, errors, c='red', s=50)
            ax2.axhline(y=0, color='k', linestyle='-', alpha=0.3)
            ax2.set_xlabel('Distância Real (cm)')
            ax2.set_ylabel('Erro (cm)')
            ax2.set_title('Análise de Erro da Calibração')
            ax2.grid(True, alpha=0.3)

            # Estatísticas
            mae = np.mean(np.abs(errors))
            rmse = np.sqrt(np.mean(np.square(errors)))
            ax2.text(0.05, 0.95, f'MAE: {mae:.2f}cm\nRMSE: {rmse:.2f}cm',
                    transform=ax2.transAxes, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout()
        plt.savefig('calibration_curve.png', dpi=100)
        plt.show()

    def get_statistics(self):
        """Retorna estatísticas das leituras"""
        if len(self.distance_buffer) == 0:
            return None

        distances = list(self.distance_buffer)
        voltages = list(self.voltage_buffer)

        stats = {
            'readings_count': self.readings_count,
            'distance': {
                'current': distances[-1] if distances else 0,
                'mean': np.mean(distances),
                'std': np.std(distances),
                'min': np.min(distances),
                'max': np.max(distances)
            },
            'voltage': {
                'current': voltages[-1] if voltages else 0,
                'mean': np.mean(voltages),
                'std': np.std(voltages)
            },
            'rate_hz': 1.0 / (time.time() - self.last_reading_time)
        }

        return stats

def calibration_wizard(sensor):
    """Assistente interativo de calibração"""
    print("\n" + "="*50)
    print("ASSISTENTE DE CALIBRAÇÃO - GP2Y0A41SK0F")
    print("="*50)
    print("\nRange do sensor: 4-30cm")
    print("Recomendado calibrar em: 5, 10, 15, 20, 25cm")
    print("\nInstruções:")
    print("1. Posicione um objeto plano perpendicular ao sensor")
    print("2. Use uma régua para medir a distância exata")
    print("3. Mantenha o objeto parado durante a calibração")

    while True:
        print("\n" + "-"*50)
        print("Opções:")
        print("1. Adicionar ponto de calibração")
        print("2. Limpar calibração")
        print("3. Mostrar pontos atuais")
        print("4. Salvar e sair")
        print("5. Sair sem salvar")

        choice = input("\nEscolha: ")

        if choice == '1':
            try:
                distance = float(input("Distância real em cm: "))
                if distance < 4 or distance > 30:
                    print("⚠ Aviso: Fora do range recomendado (4-30cm)")
                sensor.calibrate_point(distance)
            except ValueError:
                print("Valor inválido!")

        elif choice == '2':
            sensor.calibration_points = []
            sensor.interpolation_func = None
            print("✓ Calibração limpa")

        elif choice == '3':
            if sensor.calibration_points:
                print("\nPontos de calibração:")
                for p in sensor.calibration_points:
                    print(f"  {p['distance']:5.1f}cm = {p['voltage']:.3f}V (±{p['std']:.3f})")
            else:
                print("Nenhum ponto de calibração")

        elif choice == '4':
            if sensor.calibration_points:
                sensor.save_calibration()
                sensor.plot_calibration_curve()
            print("✓ Calibração concluída")
            break

        elif choice == '5':
            print("Saindo sem salvar...")
            break

def test_mode(sensor):
    """Modo de teste em tempo real"""
    print("\n" + "="*50)
    print("MODO DE TESTE - GP2Y0A41SK0F")
    print("="*50)
    print("Pressione Ctrl+C para sair\n")

    try:
        while True:
            # Leitura com filtragem
            distance = sensor.read_distance(filtered=True)

            # Leitura bruta para comparação
            voltage = sensor.channel.voltage
            distance_raw = sensor.voltage_to_distance(voltage)

            # Estatísticas
            stats = sensor.get_statistics()

            # Display
            print(f"\r", end="")
            print(f"Dist: {distance:5.1f}cm (Raw: {distance_raw:5.1f}cm) | ", end="")
            print(f"V: {voltage:.3f}V | ", end="")

            if stats:
                print(f"σ: {stats['distance']['std']:.2f}cm | ", end="")
                print(f"Rate: {stats['rate_hz']:.1f}Hz", end="")

            # Barra visual
            bar_len = int((distance - 4) / 26 * 30)
            bar = "█" * bar_len + "░" * (30 - bar_len)
            print(f" [{bar}]", end="")

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\nTeste finalizado")

        # Mostra estatísticas finais
        stats = sensor.get_statistics()
        if stats:
            print("\nEstatísticas finais:")
            print(f"  Leituras: {stats['readings_count']}")
            print(f"  Distância média: {stats['distance']['mean']:.2f}cm")
            print(f"  Desvio padrão: {stats['distance']['std']:.2f}cm")
            print(f"  Range: {stats['distance']['min']:.2f} - {stats['distance']['max']:.2f}cm")

def main():
    """Programa principal"""
    print("\n" + "="*50)
    print("SISTEMA DE TESTE GP2Y0A41SK0F")
    print("Sensor de Distância IR (4-30cm)")
    print("="*50)

    # Inicializa sensor
    print("\nInicializando sensor...")
    sensor = GP2Y0A41SK0F(ads_channel=0, gain=1, samples_rate=128)
    print("✓ Sensor inicializado")

    while True:
        print("\n" + "-"*50)
        print("MENU PRINCIPAL:")
        print("1. Modo de Teste (tempo real)")
        print("2. Calibração")
        print("3. Plotar curva de calibração")
        print("4. Configurar filtro Kalman")
        print("5. Teste de precisão")
        print("6. Sair")

        choice = input("\nEscolha: ")

        if choice == '1':
            test_mode(sensor)

        elif choice == '2':
            calibration_wizard(sensor)

        elif choice == '3':
            sensor.plot_calibration_curve()

        elif choice == '4':
            print(f"\nParâmetros atuais:")
            print(f"  Q (ruído processo): {sensor.kalman_q}")
            print(f"  R (ruído medição): {sensor.kalman_r}")
            print(f"  Habilitado: {sensor.kalman_enabled}")

            try:
                sensor.kalman_q = float(input("Novo Q (0.001-1.0): "))
                sensor.kalman_r = float(input("Novo R (0.01-10.0): "))
                sensor.kalman_enabled = input("Habilitar? (s/n): ").lower() == 's'
                print("✓ Filtro Kalman atualizado")
            except:
                print("Valores inválidos")

        elif choice == '5':
            print("\nTESTE DE PRECISÃO")
            print("Posicione um objeto a uma distância conhecida")
            actual = float(input("Distância real (cm): "))

            print("Coletando 100 amostras...")
            distances = []

            for i in range(100):
                d = sensor.read_distance(filtered=True)
                distances.append(d)
                print(f"\rProgresso: {i+1}/100", end="")
                time.sleep(0.05)

            mean_d = np.mean(distances)
            std_d = np.std(distances)
            error = mean_d - actual
            error_pct = (error / actual) * 100

            print(f"\n\nResultados:")
            print(f"  Distância real: {actual:.1f}cm")
            print(f"  Média medida: {mean_d:.2f}cm")
            print(f"  Desvio padrão: {std_d:.2f}cm")
            print(f"  Erro absoluto: {error:.2f}cm")
            print(f"  Erro percentual: {error_pct:.1f}%")
            print(f"  Range (95%): {mean_d-2*std_d:.2f} - {mean_d+2*std_d:.2f}cm")

        elif choice == '6':
            print("Encerrando...")
            break

if __name__ == "__main__":
    main()