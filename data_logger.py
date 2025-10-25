#!/usr/bin/env python3
"""
BIBLIOTECA DO DATA LOGGER

Este arquivo define a classe 'SensorDataLogger' para registrar dados do sensor.
Ele não é feito para ser executado diretamente.
Execute 'scanner_main.py' para usar esta classe.
"""

import time
import csv
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import threading
import queue
import os
import glob

# Tenta importar a classe do sensor
try:
    from sensor_distance import GP2Y0A41SK0F
except ImportError:
    print("AVISO: Não foi possível importar 'GP2Y0A41SK0F' de 'sensor_distance.py'")
    # Define uma classe 'dummy' para permitir que o logger seja importado
    # mas falhe na inicialização se for usado sem o sensor.
    class GP2Y0A41SK0F:
        def __init__(self, *args, **kwargs):
            raise ImportError("Classe GP2Y0A41SK0F não pôde ser carregada.")

class SensorDataLogger:
    """Logger de dados com visualização em tempo real"""

    def __init__(self, sensor: GP2Y0A41SK0F, log_dir="sensor_logs"):
        if not isinstance(sensor, GP2Y0A41SK0F):
            raise TypeError("O 'sensor' deve ser uma instância da classe GP2Y0A41SK0F.")

        self.sensor = sensor
        self.log_dir = log_dir
        self.running = False
        self.data_queue = queue.Queue()

        # Cria diretório de logs
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Nome do arquivo de log
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(log_dir, f"sensor_log_{timestamp}.csv")

        # Buffers para plotagem
        self.max_points = 500
        self.times = []
        self.distances = []
        self.voltages = []

        # Estatísticas
        self.total_readings = 0
        self.session_start = None

    def start_logging(self, interval=0.1):
        """Inicia o logging em thread separada"""
        self.running = True
        self.session_start = time.time()

        # Cria arquivo CSV com cabeçalho
        try:
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'elapsed_time', 'distance_cm', 'distance_raw_cm',
                    'voltage_v', 'voltage_std', 'kalman_p', 'temperature_c'
                ])
        except IOError as e:
            print(f"Erro ao criar arquivo de log: {e}")
            self.running = False
            return

        # Thread de logging
        self.log_thread = threading.Thread(
            target=self._logging_loop,
            args=(interval,),
            daemon=True # Garante que a thread morra se o programa principal sair
        )
        self.log_thread.start()

        print(f"✓ Logging iniciado: {self.log_file}")
        print(f"  Intervalo: {interval}s")

    def _logging_loop(self, interval):
        """Loop principal de logging"""
        while self.running:
            try:
                loop_start = time.time()

                # Coleta dados
                timestamp = datetime.now()
                elapsed = time.time() - self.session_start

                # Leituras do sensor
                voltage = self.sensor.read_voltage(samples=5)
                distance = self.sensor.read_distance(filtered=True)
                distance_raw = self.sensor.voltage_to_distance(voltage)

                # Estatísticas do buffer
                voltage_std = np.std(list(self.sensor.voltage_buffer)) if len(self.sensor.voltage_buffer) > 1 else 0

                # Temperatura (placeholder)
                temperature = 25.0

                # Dados para log
                log_data = {
                    'timestamp': timestamp.isoformat(),
                    'elapsed_time': elapsed,
                    'distance_cm': distance,
                    'distance_raw_cm': distance_raw,
                    'voltage_v': voltage,
                    'voltage_std': voltage_std,
                    'kalman_p': self.sensor.kalman_p,
                    'temperature_c': temperature
                }

                # Salva no arquivo
                with open(self.log_file, 'a', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=log_data.keys())
                    writer.writerow(log_data)

                # Adiciona à fila para plotagem
                self.data_queue.put(log_data)
                self.total_readings += 1

                # Aguarda intervalo (corrigido para ser mais preciso)
                loop_time = time.time() - loop_start
                sleep_time = interval - loop_time
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except Exception as e:
                print(f"Erro no logging: {e}")
                time.sleep(1)

    def stop_logging(self):
        """Para o logging"""
        if not self.running:
            return

        self.running = False
        if hasattr(self, 'log_thread') and self.log_thread.is_alive():
            self.log_thread.join(timeout=2.0)

        print(f"\n✓ Logging finalizado")
        print(f"  Total de leituras: {self.total_readings}")
        print(f"  Arquivo: {self.log_file}")

    def analyze_log(self, filename=None):
        """Analisa arquivo de log"""
        if filename is None:
            filename = self.log_file

        if not os.path.exists(filename):
            print(f"Erro: Arquivo não encontrado {filename}")
            return

        print(f"\nAnalisando: {filename}")

        # Carrega dados
        data = {
            'elapsed_time': [], 'distance_cm': [],
            'voltage_v': [], 'voltage_std': []
        }

        try:
            with open(filename, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data['elapsed_time'].append(float(row['elapsed_time']))
                    data['distance_cm'].append(float(row['distance_cm']))
                    data['voltage_v'].append(float(row['voltage_v']))
                    data['voltage_std'].append(float(row['voltage_std']))
        except Exception as e:
            print(f"Erro ao ler arquivo: {e}")
            return

        if not data['elapsed_time']:
            print("Arquivo vazio!")
            return

        # Converte para arrays numpy
        for key in data:
            data[key] = np.array(data[key])

        # Estatísticas
        print("\nESTATÍSTICAS GERAIS:")
        print(f"  Duração: {data['elapsed_time'][-1]:.1f}s")
        print(f"  Amostras: {len(data['elapsed_time'])}")
        print(f"  Taxa média: {len(data['elapsed_time'])/data['elapsed_time'][-1]:.1f} Hz")

        print("\nDISTÂNCIA:")
        print(f"  Média: {np.mean(data['distance_cm']):.2f} cm")
        print(f"  Desvio padrão: {np.std(data['distance_cm']):.2f} cm")
        print(f"  Mínimo: {np.min(data['distance_cm']):.2f} cm")
        print(f"  Máximo: {np.max(data['distance_cm']):.2f} cm")

        print("\nTENSÃO:")
        print(f"  Média: {np.mean(data['voltage_v']):.3f} V")
        print(f"  Desvio padrão: {np.std(data['voltage_v']):.3f} V")
        print(f"  Ruído médio: {np.mean(data['voltage_std']):.4f} V")

        # Plota análise
        self.plot_analysis(data, filename)

    def plot_analysis(self, data, source_filename):
        """Plota gráficos de análise"""
        fig, axes = plt.subplots(3, 2, figsize=(15, 10))
        fig.suptitle(f'Análise do Sensor - {os.path.basename(source_filename)}', fontsize=16)

        # 1. Distância vs Tempo
        ax = axes[0, 0]
        ax.plot(data['elapsed_time'], data['distance_cm'], 'b-', linewidth=0.5)
        ax.set_xlabel('Tempo (s)'); ax.set_ylabel('Distância (cm)')
        ax.set_title('Distância ao Longo do Tempo'); ax.grid(True, alpha=0.3)

        # 2. Histograma de Distância
        ax = axes[0, 1]
        ax.hist(data['distance_cm'], bins=50, color='blue', alpha=0.7, edgecolor='black')
        ax.set_xlabel('Distância (cm)'); ax.set_ylabel('Frequência')
        ax.set_title(f'Distribuição (μ={np.mean(data["distance_cm"]):.2f}, σ={np.std(data["distance_cm"]):.2f})')
        ax.grid(True, alpha=0.3)

        # 3. Tensão vs Tempo
        ax = axes[1, 0]
        ax.plot(data['elapsed_time'], data['voltage_v'], 'g-', linewidth=0.5)
        ax.set_xlabel('Tempo (s)'); ax.set_ylabel('Tensão (V)')
        ax.set_title('Tensão ao Longo do Tempo'); ax.grid(True, alpha=0.3)

        # 4. Correlação Tensão vs Distância
        ax = axes[1, 1]
        ax.scatter(data['voltage_v'], data['distance_cm'], alpha=0.5, s=1)
        ax.set_xlabel('Tensão (V)'); ax.set_ylabel('Distância (cm)')
        ax.set_title('Correlação Tensão-Distância'); ax.grid(True, alpha=0.3)

        # 5. Ruído da Tensão
        ax = axes[2, 0]
        ax.plot(data['elapsed_time'], data['voltage_std'], 'r-', linewidth=0.5)
        ax.set_xlabel('Tempo (s)'); ax.set_ylabel('Desvio Padrão (V)')
        ax.set_title('Ruído da Tensão (Std Dev)'); ax.grid(True, alpha=0.3)

        # 6. Análise de Drift (média móvel)
        ax = axes[2, 1]
        window = min(100, max(1, len(data['distance_cm'])//10))
        moving_avg = np.convolve(data['distance_cm'], np.ones(window)/window, mode='valid')
        time_avg_len = len(moving_avg)
        if time_avg_len > 0:
            time_avg = data['elapsed_time'][:time_avg_len] # Ajuste simples
            ax.plot(time_avg, moving_avg, 'b-', label=f'Média móvel ({window} amostras)')
        ax.plot(data['elapsed_time'], data['distance_cm'], 'gray', alpha=0.2, linewidth=0.5)
        ax.set_xlabel('Tempo (s)'); ax.set_ylabel('Distância (cm)')
        ax.set_title('Análise de Drift'); ax.legend(); ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plot_file = source_filename.replace('.csv', '_analysis.png')
        plt.savefig(plot_file, dpi=150)
        print(f"\n✓ Gráfico salvo: {plot_file}")
        plt.show()

    def live_plot(self):
        """Plotagem em tempo real"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
        fig.suptitle('Monitor em Tempo Real - GP2Y0A41SK0F')

        def update_plot(frame):
            while not self.data_queue.empty():
                try:
                    data = self.data_queue.get_nowait()
                    self.times.append(data['elapsed_time'])
                    self.distances.append(data['distance_cm'])
                    self.voltages.append(data['voltage_v'])

                    if len(self.times) > self.max_points:
                        self.times.pop(0)
                        self.distances.pop(0)
                        self.voltages.pop(0)
                except queue.Empty:
                    break

            if not self.times: return

            ax1.clear()
            ax2.clear()

            # Distância
            ax1.plot(self.times, self.distances, 'b-')
            ax1.set_ylabel('Distância (cm)')
            ax1.set_title(f'Última: {self.distances[-1]:.2f}cm | Média(100): {np.mean(self.distances[-100:]):.2f}cm | σ(100): {np.std(self.distances[-100:]):.2f}cm')
            ax1.grid(True, alpha=0.3)

            # Tensão
            ax2.plot(self.times, self.voltages, 'g-')
            ax2.set_ylabel('Tensão (V)')
            ax2.set_xlabel('Tempo (s)')
            ax2.set_title(f'Última: {self.voltages[-1]:.3f}V')
            ax2.grid(True, alpha=0.3)

            plt.tight_layout(rect=[0, 0.03, 1, 0.95])

        ani = FuncAnimation(fig, update_plot, interval=200, blit=False, cache_gen=False)
        print("\nPlotagem em tempo real iniciada. Feche a janela para parar.")
        plt.show()

# Este bloco só é executado se você tentar rodar este arquivo diretamente
if __name__ == "__main__":
    print("="*70)
    print("Este é um arquivo de biblioteca (data_logger.py).")
    print("Ele não deve ser executado diretamente.")
    print("Por favor, execute 'python3 scanner_main.py' para usar o programa.")
    print("="*70)
