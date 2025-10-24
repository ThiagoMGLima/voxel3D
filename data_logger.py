#!/usr/bin/env python3
"""
Data Logger para GP2Y0A41SK0F
Registra dados para análise de estabilidade e drift
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

class SensorDataLogger:
    """Logger de dados com visualização em tempo real"""
    
    def __init__(self, sensor, log_dir="sensor_logs"):
        self.sensor = sensor
        self.log_dir = log_dir
        self.running = False
        self.data_queue = queue.Queue()
        
        # Cria diretório de logs
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Nome do arquivo de log
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = f"{log_dir}/sensor_log_{timestamp}.csv"
        
        # Buffers para plotagem
        self.max_points = 500
        self.times = []
        self.distances = []
        self.voltages = []
        self.temperatures = []  # Para futura expansão
        
        # Estatísticas
        self.total_readings = 0
        self.session_start = None
        
    def start_logging(self, interval=0.1):
        """Inicia o logging em thread separada"""
        self.running = True
        self.session_start = time.time()
        
        # Cria arquivo CSV com cabeçalho
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'elapsed_time', 'distance_cm', 'distance_raw_cm',
                'voltage_v', 'voltage_std', 'kalman_p', 'temperature_c'
            ])
        
        # Thread de logging
        self.log_thread = threading.Thread(
            target=self._logging_loop,
            args=(interval,)
        )
        self.log_thread.start()
        
        print(f"✓ Logging iniciado: {self.log_file}")
        print(f"  Intervalo: {interval}s")
    
    def _logging_loop(self, interval):
        """Loop principal de logging"""
        while self.running:
            try:
                # Coleta dados
                timestamp = datetime.now()
                elapsed = time.time() - self.session_start
                
                # Leituras do sensor
                voltage = self.sensor.read_voltage(samples=5)
                distance = self.sensor.read_distance(filtered=True)
                distance_raw = self.sensor.voltage_to_distance(voltage)
                
                # Estatísticas do buffer
                voltage_std = np.std(list(self.sensor.voltage_buffer)) if len(self.sensor.voltage_buffer) > 1 else 0
                
                # Temperatura (placeholder para sensor futuro)
                temperature = 25.0  # Valor fixo por enquanto
                
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
                
                # Aguarda intervalo
                time.sleep(interval)
                
            except Exception as e:
                print(f"Erro no logging: {e}")
                time.sleep(1)
    
    def stop_logging(self):
        """Para o logging"""
        self.running = False
        if hasattr(self, 'log_thread'):
            self.log_thread.join()
        print(f"\n✓ Logging finalizado")
        print(f"  Total de leituras: {self.total_readings}")
        print(f"  Arquivo: {self.log_file}")
    
    def analyze_log(self, filename=None):
        """Analisa arquivo de log"""
        if filename is None:
            filename = self.log_file
        
        print(f"\nAnalisando: {filename}")
        
        # Carrega dados
        data = {
            'elapsed_time': [],
            'distance_cm': [],
            'voltage_v': [],
            'voltage_std': []
        }
        
        with open(filename, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data['elapsed_time'].append(float(row['elapsed_time']))
                data['distance_cm'].append(float(row['distance_cm']))
                data['voltage_v'].append(float(row['voltage_v']))
                data['voltage_std'].append(float(row['voltage_std']))
        
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
        
        # Análise de drift
        if len(data['elapsed_time']) > 100:
            # Divide em quartis
            n = len(data['distance_cm'])
            q1_mean = np.mean(data['distance_cm'][:n//4])
            q4_mean = np.mean(data['distance_cm'][3*n//4:])
            drift = q4_mean - q1_mean
            drift_rate = drift / (data['elapsed_time'][-1] / 60)  # cm/min
            
            print("\nANÁLISE DE DRIFT:")
            print(f"  Média inicial (25%): {q1_mean:.2f} cm")
            print(f"  Média final (25%): {q4_mean:.2f} cm")
            print(f"  Drift total: {drift:.3f} cm")
            print(f"  Taxa de drift: {drift_rate:.4f} cm/min")
        
        # Análise de estabilidade
        if len(data['distance_cm']) > 10:
            # Calcula desvio padrão em janelas
            window_size = min(50, len(data['distance_cm'])//10)
            stds = []
            
            for i in range(0, len(data['distance_cm']) - window_size, window_size//2):
                window = data['distance_cm'][i:i+window_size]
                stds.append(np.std(window))
            
            print("\nESTABILIDADE:")
            print(f"  Desvio padrão mínimo: {np.min(stds):.3f} cm")
            print(f"  Desvio padrão máximo: {np.max(stds):.3f} cm")
            print(f"  Variação da estabilidade: {np.std(stds):.4f}")
        
        # Plota análise
        self.plot_analysis(data)
    
    def plot_analysis(self, data):
        """Plota gráficos de análise"""
        fig, axes = plt.subplots(3, 2, figsize=(15, 10))
        fig.suptitle('Análise de Dados do Sensor GP2Y0A41SK0F', fontsize=16)
        
        # 1. Distância vs Tempo
        ax = axes[0, 0]
        ax.plot(data['elapsed_time'], data['distance_cm'], 'b-', linewidth=0.5)
        ax.set_xlabel('Tempo (s)')
        ax.set_ylabel('Distância (cm)')
        ax.set_title('Distância ao Longo do Tempo')
        ax.grid(True, alpha=0.3)
        
        # 2. Histograma de Distância
        ax = axes[0, 1]
        ax.hist(data['distance_cm'], bins=50, color='blue', alpha=0.7, edgecolor='black')
        ax.set_xlabel('Distância (cm)')
        ax.set_ylabel('Frequência')
        ax.set_title(f'Distribuição de Distâncias (μ={np.mean(data["distance_cm"]):.2f}, σ={np.std(data["distance_cm"]):.2f})')
        ax.grid(True, alpha=0.3)
        
        # 3. Tensão vs Tempo
        ax = axes[1, 0]
        ax.plot(data['elapsed_time'], data['voltage_v'], 'g-', linewidth=0.5)
        ax.set_xlabel('Tempo (s)')
        ax.set_ylabel('Tensão (V)')
        ax.set_title('Tensão ao Longo do Tempo')
        ax.grid(True, alpha=0.3)
        
        # 4. Correlação Tensão vs Distância
        ax = axes[1, 1]
        ax.scatter(data['voltage_v'], data['distance_cm'], alpha=0.5, s=1)
        ax.set_xlabel('Tensão (V)')
        ax.set_ylabel('Distância (cm)')
        ax.set_title('Correlação Tensão-Distância')
        ax.grid(True, alpha=0.3)
        
        # 5. Ruído da Tensão
        ax = axes[2, 0]
        ax.plot(data['elapsed_time'], data['voltage_std'], 'r-', linewidth=0.5)
        ax.set_xlabel('Tempo (s)')
        ax.set_ylabel('Desvio Padrão (V)')
        ax.set_title('Ruído da Tensão')
        ax.grid(True, alpha=0.3)
        
        # 6. Análise de Drift (média móvel)
        ax = axes[2, 1]
        window = min(100, len(data['distance_cm'])//10)
        if window > 1:
            moving_avg = np.convolve(data['distance_cm'], np.ones(window)/window, mode='valid')
            time_avg = data['elapsed_time'][window//2:-window//2+1]
            ax.plot(time_avg, moving_avg, 'b-', label=f'Média móvel ({window} amostras)')
            ax.plot(data['elapsed_time'], data['distance_cm'], 'gray', alpha=0.2, linewidth=0.5)
        else:
            ax.plot(data['elapsed_time'], data['distance_cm'], 'b-', linewidth=0.5)
        
        ax.set_xlabel('Tempo (s)')
        ax.set_ylabel('Distância (cm)')
        ax.set_title('Análise de Drift')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Salva figura
        plot_file = self.log_file.replace('.csv', '_analysis.png')
        plt.savefig(plot_file, dpi=150)
        print(f"\n✓ Gráfico salvo: {plot_file}")
        
        plt.show()
    
    def live_plot(self):
        """Plotagem em tempo real"""
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 8))
        fig.suptitle('Monitor em Tempo Real - GP2Y0A41SK0F')
        
        def update_plot(frame):
            # Processa dados da fila
            while not self.data_queue.empty():
                try:
                    data = self.data_queue.get_nowait()
                    
                    self.times.append(data['elapsed_time'])
                    self.distances.append(data['distance_cm'])
                    self.voltages.append(data['voltage_v'])
                    
                    # Limita número de pontos
                    if len(self.times) > self.max_points:
                        self.times.pop(0)
                        self.distances.pop(0)
                        self.voltages.pop(0)
                except:
                    break
            
            if not self.times:
                return
            
            # Limpa e plota
            ax1.clear()
            ax2.clear()
            ax3.clear()
            
            # Distância
            ax1.plot(self.times, self.distances, 'b-')
            ax1.set_ylabel('Distância (cm)')
            ax1.set_title(f'Última: {self.distances[-1]:.2f}cm' if self.distances else 'Aguardando...')
            ax1.grid(True, alpha=0.3)
            
            # Tensão
            ax2.plot(self.times, self.voltages, 'g-')
            ax2.set_ylabel('Tensão (V)')
            ax2.set_title(f'Última: {self.voltages[-1]:.3f}V' if self.voltages else 'Aguardando...')
            ax2.grid(True, alpha=0.3)
            
            # Histograma
            if len(self.distances) > 10:
                ax3.hist(self.distances[-min(100, len(self.distances)):], bins=20, alpha=0.7)
                ax3.set_xlabel('Distância (cm)')
                ax3.set_ylabel('Frequência')
                mean_d = np.mean(self.distances[-100:])
                std_d = np.std(self.distances[-100:])
                ax3.set_title(f'Últimas 100: μ={mean_d:.2f}cm, σ={std_d:.2f}cm')
            
            ax3.set_xlabel('Tempo (s)')
            
            plt.tight_layout()
        
        # Animação
        ani = FuncAnimation(fig, update_plot, interval=100, blit=False)
        
        print("\nPlotagem em tempo real iniciada")
        print("Feche a janela para parar")
        
        plt.show()
        
        return ani

def main():
    """Programa principal de logging"""
    from sensor_distance import GP2Y0A41SK0F
    
    print("\n" + "="*50)
    print("DATA LOGGER - GP2Y0A41SK0F")
    print("="*50)
    
    # Inicializa sensor
    print("\nInicializando sensor...")
    sensor = GP2Y0A41SK0F(ads_channel=0, gain=1, samples_rate=128)
    print("✓ Sensor inicializado")
    
    # Cria logger
    logger = SensorDataLogger(sensor)
    
    while True:
        print("\n" + "-"*50)
        print("OPÇÕES:")
        print("1. Iniciar logging")
        print("2. Logging com visualização em tempo real")
        print("3. Analisar arquivo de log")
        print("4. Teste de estabilidade (1 hora)")
        print("5. Sair")
        
        choice = input("\nEscolha: ")
        
        if choice == '1':
            try:
                interval = float(input("Intervalo entre leituras (s) [0.1]: ") or "0.1")
                duration = float(input("Duração em minutos (0 = manual): ") or "0")
                
                logger.start_logging(interval)
                
                if duration > 0:
                    print(f"\nLogging por {duration} minutos...")
                    print("Pressione Ctrl+C para interromper")
                    time.sleep(duration * 60)
                else:
                    print("\nLogging iniciado. Pressione Enter para parar...")
                    input()
                
                logger.stop_logging()
                
                # Análise automática
                if input("\nAnalisar dados agora? (s/n): ").lower() == 's':
                    logger.analyze_log()
                    
            except KeyboardInterrupt:
                logger.stop_logging()
            except Exception as e:
                print(f"Erro: {e}")
                logger.stop_logging()
        
        elif choice == '2':
            try:
                interval = float(input("Intervalo entre leituras (s) [0.1]: ") or "0.1")
                
                logger.start_logging(interval)
                
                # Inicia plotagem em tempo real
                ani = logger.live_plot()
                
                logger.stop_logging()
                
            except KeyboardInterrupt:
                logger.stop_logging()
            except Exception as e:
                print(f"Erro: {e}")
                logger.stop_logging()
        
        elif choice == '3':
            # Lista arquivos de log
            import glob
            logs = glob.glob("sensor_logs/*.csv")
            
            if not logs:
                print("Nenhum arquivo de log encontrado")
                continue
            
            print("\nArquivos disponíveis:")
            for i, log in enumerate(logs, 1):
                size = os.path.getsize(log) / 1024
                print(f"{i}. {os.path.basename(log)} ({size:.1f} KB)")
            
            try:
                idx = int(input("\nNúmero do arquivo (0 = cancelar): "))
                if idx > 0 and idx <= len(logs):
                    logger.analyze_log(logs[idx-1])
            except:
                print("Seleção inválida")
        
        elif choice == '4':
            print("\nTESTE DE ESTABILIDADE (1 hora)")
            print("Este teste verificará drift e estabilidade do sensor")
            
            if input("Confirmar teste de 1 hora? (s/n): ").lower() == 's':
                try:
                    logger.start_logging(interval=1.0)  # 1 leitura por segundo
                    
                    start = time.time()
                    duration = 3600  # 1 hora
                    
                    while time.time() - start < duration:
                        elapsed = time.time() - start
                        remaining = duration - elapsed
                        
                        stats = sensor.get_statistics()
                        if stats:
                            print(f"\rTempo: {elapsed:.0f}s / {duration}s | ", end="")
                            print(f"Dist: {stats['distance']['current']:.2f}cm | ", end="")
                            print(f"σ: {stats['distance']['std']:.3f}cm | ", end="")
                            print(f"Restante: {remaining/60:.1f}min", end="")
                        
                        time.sleep(1)
                    
                    logger.stop_logging()
                    
                    print("\n\n✓ Teste concluído!")
                    logger.analyze_log()
                    
                except KeyboardInterrupt:
                    logger.stop_logging()
                    print("\n\nTeste interrompido")
                    if input("Analisar dados parciais? (s/n): ").lower() == 's':
                        logger.analyze_log()
        
        elif choice == '5':
            print("Encerrando...")
            break

if __name__ == "__main__":
    main()
