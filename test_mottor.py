import RPi.GPIO as GPIO
import time

# --- Configuração dos Pinos GPIO (use os números BCM) ---
STEP_PIN = 11  # GPIO 11
DIR_PIN = 13   # GPIO 13
ENABLE_PIN = 15 # GPIO 15

# --- Configuração da Rotação ---
# 200 passos * 16 microsteps = 3200 pulsos para 360 graus
PASSOS_PARA_360 = 3200

# Delay entre os pulsos (controla a velocidade)
# Um delay menor significa velocidade maior
# Comece com um valor seguro (0.001) e diminua para testar
PULSE_DELAY = 0.001

# Configurar GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(STEP_PIN, GPIO.OUT)
GPIO.setup(DIR_PIN, GPIO.OUT)
GPIO.setup(ENABLE_PIN, GPIO.OUT)

def girar_360():
    print("Iniciando rotação de 360 graus...")

    # Habilitar o driver (definir ENABLE como LOW)
    GPIO.output(ENABLE_PIN, GPIO.LOW)

    # Definir a direção (LOW para um lado, HIGH para o outro)
    GPIO.output(DIR_PIN, GPIO.HIGH)

    # Pausa para garantir que a direção foi setada
    time.sleep(0.1)

    # Enviar os pulsos
    for i in range(PASSOS_PARA_360):
        GPIO.output(STEP_PIN, GPIO.HIGH)
        time.sleep(PULSE_DELAY / 2) # Divide o delay para o pulso HIGH/LOW
        GPIO.output(STEP_PIN, GPIO.LOW)
        time.sleep(PULSE_DELAY / 2)

        # Opcional: imprimir progresso
        if (i % 400 == 0):
            print(f"Progresso: {i}/{PASSOS_PARA_360}")

    print("Rotação completa.")

    # Desabilitar o driver (opcional, economiza energia mas libera o motor)
    # GPIO.output(ENABLE_PIN, GPIO.HIGH)

try:
    girar_360()

except KeyboardInterrupt:
    print("Rotação interrompida.")

finally:
    GPIO.cleanup()
    print("GPIOs limpos.")