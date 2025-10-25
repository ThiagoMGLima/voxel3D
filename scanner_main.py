#!/usr/bin/env python3
"""
PROGRAMA PRINCIPAL - Scanner 3D e Ferramentas de Sensor

Este é o ponto de entrada principal do projeto.
Ele importa as classes de 'sensor_distance.py' e 'data_logger.py'
e fornece um menu para acessar todas as funcionalidades.
"""

# Imports do Sistema
import time
import csv
import sys
import glob
import os
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt

# --- Imports do Projeto ---

# 1. Biblioteca do Sensor
try:
    from sensor_distance import GP2Y0A41SK0F
except ImportError:
    print("Erro: Não foi possível encontrar 'sensor_distance.py'.")
    print("Certifique-se que o arquivo está no mesmo diretório.")
    sys.exit(1)
except Exception as e:
    print(f"Erro ao importar 'sensor_distance.py': {e}")
    print("Verifique se as dependências (adafruit, numpy, scipy) estão instaladas.")
    sys.exit(1)

# 2. Biblioteca do Data Logger
try:
    from data_logger import SensorDataLogger
except ImportError:
    print("Erro: Não foi possível encontrar 'data_logger.py'.")
    print("Certifique-se que o arquivo está no mesmo diretório.")
    sys.exit(1)

# 3. Biblioteca do Motor de Passo
try:
    import pigpio
except ImportError:
    print("AVISO: Biblioteca 'pigpio' não encontrada.")
    print("A função 'Scanner 360' (opção 4) não funcionará.")
    print("Execute 'sudo apt-get install python3-pigpio'")
    pigpio = None # Permite o programa rodar sem o pigpio

# --- Configuração do Motor de Passo ---
STEP_PIN = 17 # GPIO 17
DIR_PIN = 27  # GPIO 27
EN_PIN = 22   # GPIO 22

# --- Parâmetros do Scanner ---
STEPS_POR_REVOLUCAO = 200
MICROSTEPPING = 16 # (Conforme pinos MS1/MS2 fisicamente ligados)
TOTAL_MICROSTEPS_360_GRAUS = STEPS_POR_REVOLUCAO * MICROSTEPPING # 3200
STEPS_POR_MEDICAO = 8  # 3200/8 = 400 medições. (360/400 = 0.9 graus/medição)
DELAY_APOS_MOVER = 0.1 # Atraso (s) para vibração do motor parar


# ###################################################################
# CLASSE DO MOTOR DE PASSO
# ###################################################################

class StepperMotor:
    """Classe de controle para o motor de passo usando pigpio"""

    def __init__(self, pi, step_pin, dir_pin, en_pin):
        if pigpio is None:
            raise ImportError("Biblioteca 'pigpio' não está disponível.")

        self.pi = pi
        self.step_pin = step_pin
        self.dir_pin = dir_pin
        self.en_pin = en_pin

        # Configura pinos
        self.pi.set_mode(self.step_pin, pigpio.OUTPUT)
        self.pi.set_mode(self.dir_pin, pigpio.OUTPUT)
        self.pi.set_mode(self.en_pin, pigpio.OUTPUT)

        # Define a direção (0 = CW, 1 = CCW)
        self.pi.write(self.dir_pin, 0)

        # Desativa o driver por padrão (HIGH = desativado)
        self.pi.write(self.en_pin, 1)
        self.enabled = False

    def enable(self):
        """Ativa o driver (Ativo Baixo)"""
        self.pi.write(self.en_pin, 0)
        self.enabled = True
        time.sleep(0.01) # Pequeno atraso para o driver estabilizar

    def disable(self):
        """Desativa o driver"""
        self.pi.write(self.en_pin, 1)
        self.enabled = False

    def move_steps(self, num_steps, delay_us=500):
        """
        Move um número de micro-passos.
        delay_us: Duração de cada pulso (metade do período).
                  500us = 1000us por ciclo = 1000 Hz (velocidade)
        """
        if not self.enabled:
            self.enable()

        for _ in range(num_steps):
            self.pi.write(self.step_pin, 1)
            time.sleep(delay_us / 1000000.0)
            self.pi.write(self.step_pin, 0)
            time.sleep(delay_us / 1000000.0)


# ###################################################################
# FUNÇÕES DE MENU (Movidas de sensor_distance.py)
# ###################################################################

def test_mode(sensor: GP2Y0A41SK0F):
    """Modo de teste em tempo real"""
    print("\n" + "="*50)
    print("MODO DE TESTE - GP2Y0A41SK0F")
    print("="*50)
    print("Pressione Ctrl+C para sair\n")

    try:
        while True:
            distance = sensor.read_distance(filtered=True)
            voltage = sensor.voltage_buffer[-1] if sensor.voltage_buffer else 0
            distance_raw = sensor.voltage_to_distance(voltage)
            stats = sensor.get_statistics()

            print(f"\r", end="")
            print(f"Dist: {distance:5.1f}cm (Raw: {distance_raw:5.1f}cm) | ", end="")
            print(f"V: {voltage:.3f}V | ", end="")

            if stats:
                print(f"σ: {stats['distance']['std']:.2f}cm | ", end="")
                print(f"Rate: {stats['rate_hz']:.1f}Hz", end="")

            bar_len = int(np.clip((distance - 4) / 26 * 30, 0, 30))
            bar = "█" * bar_len + "░" * (30 - bar_len)
            print(f" [{bar}]", end="")

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\nTeste finalizado")
        stats = sensor.get_statistics()
        if stats:
            print("\nEstatísticas finais:")
            print(f"  Leituras: {stats['readings_count']}")
            print(f"  Distância média: {stats['distance']['mean']:.2f}cm")
            print(f"  Desvio padrão: {stats['distance']['std']:.2f}cm")
            print(f"  Range: {stats['distance']['min']:.2f} - {stats['distance']['max']:.2f}cm")


def calibration_wizard(sensor: GP2Y0A41SK0F):
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
        print("Opções de Calibração:")
        print("1. Adicionar ponto de calibração")
        print("2. Limpar calibração")
        print("3. Mostrar pontos atuais")
        print("4. Salvar e Sair")
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
            sensor.load_calibration() # Recarrega a calibração salva
            break


def precision_test(sensor: GP2Y0A41SK0F):
    """Executa um teste de precisão em um ponto conhecido"""
    print("\nTESTE DE PRECISÃO")
    try:
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

        print(f"\n\nResultados para Distância Real de {actual:.1f}cm:")
        print(f"  Média medida: {mean_d:.2f}cm")
        print(f"  Desvio padrão: {std_d:.2f}cm")
        print(f"  Erro absoluto: {error:.2f}cm")
        print(f"  Erro percentual: {error_pct:.1f}%")
        print(f"  Range (95%): {mean_d-2*std_d:.2f} - {mean_d+2*std_d:.2f}cm")
    except ValueError:
        print("Entrada inválida.")
    except Exception as e:
        print(f"Erro no teste: {e}")


# ###################################################################
# FUNÇÕES DO DATA LOGGER (Movidas de data_logger.py)
# ###################################################################

def start_data_logger(sensor: GP2Y0A41SK0F):
    """Menu de interface para o Data Logger"""

    print("\n" + "="*50)
    print("MÓDULO DATA LOGGER")
    print("="*50)

    # Cria logger (passando o sensor já inicializado)
    try:
        logger = SensorDataLogger(sensor)
    except Exception as e:
        print(f"Erro ao inicializar logger: {e}")
        return

    while True:
        print("\n" + "-"*50)
        print("Opções do Data Logger:")
        print("1. Iniciar logging (manual)")
        print("2. Logging com visualização em tempo real")
        print("3. Analisar arquivo de log existente")
        print("4. Voltar ao menu principal")

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
                logger.live_plot() # Isso bloqueia até a janela fechar
                logger.stop_logging()
            except KeyboardInterrupt:
                logger.stop_logging()
            except Exception as e:
                print(f"Erro: {e}")
                logger.stop_logging()

        elif choice == '3':
            logs = glob.glob("sensor_logs/*.csv")
            if not logs:
                print("Nenhum arquivo de log encontrado em 'sensor_logs/'.")
                continue

            print("\nArquivos de log disponíveis:")
            logs.sort(key=os.path.getmtime, reverse=True) # Mais recentes primeiro
            for i, log in enumerate(logs, 1):
                size = os.path.getsize(log) / 1024
                print(f"{i:2d}. {os.path.basename(log)} ({size:.1f} KB)")

            try:
                idx = int(input(f"\nNúmero do arquivo (1-{len(logs)}): "))
                if 1 <= idx <= len(logs):
                    logger.analyze_log(logs[idx-1])
            except ValueError:
                print("Seleção inválida")

        elif choice == '4':
            print("Voltando ao menu principal...")
            break


# ###################################################################
# FUNÇÕES DO SCANNER (Lógica original do scanner_main)
# ###################################################################

def run_scan(sensor: GP2Y0A41SK0F, motor: StepperMotor):
    """Executa a varredura de 360 graus"""

    num_medicoes = TOTAL_MICROSTEPS_360_GRAUS // STEPS_POR_MEDICAO
    graus_por_medicao = 360.0 / num_medicoes

    print("="*50)
    print("INICIANDO VARREDURA DE 360 GRAUS")
    print(f"  Total de medições: {num_medicoes}")
    print(f"  Passos por medição: {STEPS_POR_MEDICAO}")
    print(f"  Graus por medição: {graus_por_medicao:.3f}°")
    print(f"  Atraso por medição: {DELAY_APOS_MOVER}s")
    print("="*50)

    results = [] # Lista para salvar (angulo, distancia)

    # Ativa o motor
    motor.enable()
    print("Motor ativado. Aguardando 1s...")
    time.sleep(1.0)

    try:
        for i in range(num_medicoes):
            current_angle = i * graus_por_medicao
            distance = sensor.read_distance(filtered=True)
            results.append((current_angle, distance))

            print(f"\rProgresso: {i+1}/{num_medicoes} | "
                  f"Ângulo: {current_angle:6.2f}° | "
                  f"Distância: {distance:5.2f}cm", end="")

            motor.move_steps(STEPS_POR_MEDICAO)
            time.sleep(DELAY_APOS_MOVER)

    except KeyboardInterrupt:
        print("\n\nVarredura interrompida pelo usuário.")

    finally:
        motor.disable()
        print("\nMotor desativado.")

        if results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"scan_data_{timestamp}.csv"

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['angulo_graus', 'distancia_cm'])
                writer.writerows(results)

            print(f"\n✓ Dados da varredura salvos em: {filename}")


def start_scanner_mode(sensor: GP2Y0A41SK0F):
    """Inicializa pigpio e executa a varredura"""

    print("\n" + "="*50)
    print("MÓDULO SCANNER 360")
    print("="*50)

    # Verifica se pigpio foi importado corretamente
    if pigpio is None:
        print("Erro: Biblioteca 'pigpio' não está instalada.")
        print("Execute: sudo apt-get install python3-pigpio")
        return

    # 1. Inicializar pigpio
    try:
        pi = pigpio.pi()
        if not pi.connected:
            raise RuntimeError("Não foi possível conectar ao pigpio daemon.")
    except Exception as e:
        print(f"Erro: {e}")
        print("Execute 'sudo systemctl start pigpiod'")
        return

    print("✓ Conectado ao pigpio daemon")

    # 2. Inicializar Motor
    try:
        motor = StepperMotor(pi, STEP_PIN, DIR_PIN, EN_PIN)
        print("✓ Motor inicializado")
    except Exception as e:
        print(f"Erro ao inicializar motor: {e}")
        pi.stop()
        return

    # 3. Verifica calibração do sensor
    if sensor.interpolation_func is None:
        print("⚠ Aviso: Sensor está usando a curva padrão.")
        print("  A precisão da varredura será baixa.")
        print("  Recomenda-se usar a 'Opção 2. Calibração' primeiro.")
        if input("\nContinuar mesmo assim? (s/n): ").lower() != 's':
            pi.stop()
            return

    # 4. Executar a varredura
    run_scan(sensor, motor)

    # 5. Limpeza
    pi.stop()
    print("Conexão com pigpio daemon fechada.")
    print("Scanner finalizado.")


# ###################################################################
# PROGRAMA PRINCIPAL (MAIN)
# ###################################################################

def main():
    """Menu principal do aplicativo"""
    print("\n" + "="*50)
    print("SISTEMA DE SCANNER E ANÁLISE DE SENSOR")
    print("GP2Y0A41SK0F + NEMA 17")
    print("="*50)

    # Inicializa sensor (só uma vez)
    print("\nInicializando sensor...")
    try:
        sensor = GP2Y0A41SK0F(ads_channel=0, gain=1, samples_rate=128)
        print("✓ Sensor inicializado com sucesso.")
    except Exception as e:
        print(f"✗ ERRO FATAL AO INICIAR SENSOR: {e}")
        print("Verifique as conexões I2C (SDA, SCL) e o ADS1115.")
        print("Execute 'python3 test_connection.py' para diagnosticar.")
        sys.exit(1)

    while True:
        print("\n" + "-"*50)
        print("MENU PRINCIPAL:")
        print("--- Funções do Sensor ---")
        print("1. Modo de Teste (tempo real)")
        print("2. Calibração do Sensor")
        print("3. Teste de Precisão (ponto único)")
        print("4. Plotar curva de calibração")
        print("5. Configurar filtro Kalman")
        print("--- Funções do Scanner & Logger ---")
        print("6. Executar Data Logger (estabilidade, drift)")
        print("7. EXECUTAR VARREDURA 360")
        print("--- Sair ---")
        print("8. Sair")

        choice = input("\nEscolha: ")

        try:
            if choice == '1':
                test_mode(sensor)

            elif choice == '2':
                calibration_wizard(sensor)

            elif choice == '3':
                precision_test(sensor)

            elif choice == '4':
                sensor.plot_calibration_curve()

            elif choice == '5':
                print(f"\nParâmetros atuais:")
                print(f"  Q (ruído processo): {sensor.kalman_q}")
                print(f"  R (ruído medição): {sensor.kalman_r}")

                new_q = input(f"Novo Q [{sensor.kalman_q}]: ")
                new_r = input(f"Novo R [{sensor.kalman_r}]: ")

                if new_q: sensor.kalman_q = float(new_q)
                if new_r: sensor.kalman_r = float(new_r)
                print("✓ Filtro Kalman atualizado")

            elif choice == '6':
                start_data_logger(sensor)

            elif choice == '7':
                start_scanner_mode(sensor)

            elif choice == '8':
                print("Encerrando...")
                break

            else:
                print("Opção inválida, tente novamente.")

        except ValueError:
            print("Entrada inválida. Por favor, insira um número.")
        except Exception as e:
            print(f"\nOcorreu um erro inesperado: {e}")
            # Opcional: imprimir traceback para debug
            # import traceback
            # traceback.print_exc()

if __name__ == "__main__":
    main()
