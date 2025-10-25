#!/usr/bin/env python3
"""
BIBLIOTECA DO SENSOR GP2Y0A41SK0F

Este arquivo define a classe 'GP2Y0A41SK0F' para interagir com o sensor.
Ele não é feito para ser executado diretamente.
Execute 'scanner_main.py' para usar esta classe.
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
        # --- CORREÇÃO AQUI ---
        # A sintaxe correta é `ADS.P0` (usando a referência do módulo importado)
        channels = [ADS.P0, ADS.P1, ADS.P2, ADS.P3]
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
        if voltage < 0.25:
            return self.max_distance
        if voltage > 3.3:
            return self.min_distance

        try:
            # Modelo: distance = a / (voltage - b) - c
            a = 12.0
            b = 0.04
            c = 0.42
            distance = a / (voltage - b) - c
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
        except FileNotFoundError:
            print("⚠ Nenhuma calibração encontrada, usando curva padrão")
            return False
        except Exception as e:
            print(f"⚠ Erro ao carregar calibração: {e}. Usando curva padrão.")
            return False

    def plot_calibration_curve(self):
        """Plota curva de calibração"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
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
        if len(self.distance_buffer) == 0: return None
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
            'rate_hz': 1.0 / (time.time() - self.last_reading_time) if (time.time() - self.last_reading_time) > 0 else 0
        }
        return stats

# Este bloco só é executado se você tentar rodar este arquivo diretamente
if __name__ == "__main__":
    print("="*70)
    print("Este é um arquivo de biblioteca (sensor_distance.py).")
    print("Ele não deve ser executado diretamente.")
    print("Por favor, execute 'python3 scanner_main.py' para usar o programa.")
    print("="*70)