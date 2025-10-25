# Sistema de Alta Precisão para Sensor GP2Y0A41SK0F

Sistema completo para teste e calibração do sensor de distância infravermelho Sharp GP2Y0A41SK0F usando ADS1115 e Raspberry Pi 4.

## 📋 Especificações do Sensor

- **Modelo**: GP2Y0A41SK0F (Sharp)
- **Range**: 4 a 30 cm
- **Tensão de saída**: 0.3V (30cm) a 3.1V (4cm)
- **Alimentação**: 4.5V a 5.5V
- **Corrente**: ~30mA típico

## 🔌 Diagrama de Conexão

```
RASPBERRY PI 4          ADS1115           GP2Y0A41SK0F
─────────────          ────────          ─────────────

3.3V/5V (Pino 1) ────> VDD
GND (Pino 6) ────────> GND <──────────── GND (Pino 1)
GPIO2/SDA (Pino 3) ──> SDA
GPIO3/SCL (Pino 5) ──> SCL
                       A0 <────────────── Vo (Pino 3)
                       ADDR ───┐
                              ─┴─ GND
5V (Pino 2) ─────────────────────────> Vcc (Pino 2)

```

### Pinagem GP2Y0A41SK0F:
1. GND (Preto)
2. Vcc 5V (Vermelho)
3. Vo - Saída analógica (Amarelo)

### Pinagem ADS1115:
- VDD: Alimentação (3.3V ou 5V)
- GND: Terra
- SCL: Clock I2C
- SDA: Dados I2C
- ADDR: Endereço I2C (GND = 0x48)
- A0-A3: Entradas analógicas

## 🛠️ Instalação

### 1. Instale as dependências:
```bash
chmod +x install.sh
./install.sh
```

### 2. Reinicie o Raspberry Pi:
```bash
sudo reboot
```

### 3. Verifique a conexão I2C:
```bash
i2cdetect -y 1
```
Você deve ver `48` no grid (endereço do ADS1115)

### 4. Teste a conexão:
```bash
python3 test_connection.py
```

### 5. Execute o sistema principal:
```bash
python3 sensor_distance.py
```

## 🎯 Recursos do Sistema

### 1. **Leitura de Alta Precisão**
- Múltiplas amostragens com remoção de outliers
- Filtro Kalman adaptativo
- Média móvel ponderada
- Buffer circular para análise estatística

### 2. **Calibração Avançada**
- Calibração multi-ponto
- Interpolação cúbica entre pontos
- Persistência em arquivo JSON
- Análise de erro e desvio padrão

### 3. **Modos de Operação**
- **Modo Teste**: Visualização em tempo real
- **Modo Calibração**: Assistente interativo
- **Teste de Precisão**: Análise estatística detalhada
- **Configuração Kalman**: Ajuste fino do filtro

### 4. **Visualização**
- Gráfico da curva de calibração
- Comparação com curva padrão
- Análise de erro por distância
- Estatísticas em tempo real

## 📊 Como Calibrar para Máxima Precisão

### Preparação:
1. Use uma superfície plana e perpendicular ao sensor (ex: livro, caixa)
2. Tenha uma régua ou fita métrica precisa
3. Ambiente com iluminação estável
4. Evite superfícies muito reflexivas ou absorventes de IR

### Processo de Calibração:

1. **Execute o programa principal**:
```bash
python3 sensor_distance.py
```

2. **Selecione "2. Calibração"**

3. **Calibre em múltiplos pontos** (recomendado):
   - 5 cm
   - 10 cm
   - 15 cm
   - 20 cm
   - 25 cm

4. **Para cada ponto**:
   - Posicione o objeto na distância exata
   - Mantenha estável por 5 segundos
   - O sistema coleta 50 amostras automaticamente

5. **Salve a calibração** ao finalizar

### Dicas para Melhor Precisão:

1. **Calibração**:
   - Calibre com o mesmo tipo de superfície que será medida
   - Faça calibração em ambiente similar ao de uso
   - Recalibre se mudar as condições de uso

2. **Posicionamento**:
   - Monte o sensor firmemente (evite vibrações)
   - Mantenha perpendicular à superfície medida
   - Evite ângulos maiores que 20°

3. **Ambiente**:
   - Evite luz solar direta no sensor
   - Cuidado com superfícies pretas (absorvem IR)
   - Superfícies espelhadas podem causar leituras erráticas

4. **Filtragem**:
   - Ajuste o filtro Kalman (Menu opção 4)
   - Q menor = resposta mais lenta, mais estável
   - R maior = menos confiança na medição, mais suavização

## 📈 Interpretando os Resultados

### Estatísticas Importantes:

- **Desvio Padrão (σ)**: Menor que 0.5cm é excelente
- **Erro Absoluto**: Menor que 1cm é bom para este sensor
- **Taxa de Leitura**: 10-20 Hz típico com filtragem

### Limitações do Sensor:

- **Zona morta**: < 4cm (leituras não confiáveis)
- **Alcance máximo**: > 30cm (satura em valor mínimo)
- **Superfícies problemáticas**:
  - Vidro e acrílico (transparente ao IR)
  - Superfícies muito escuras
  - Materiais com alta absorção IR

## 🔧 Solução de Problemas

### Leituras instáveis:
- Verifique alimentação estável de 5V
- Adicione capacitor de 10µF entre Vcc e GND do sensor
- Aumente o número de amostras no código
- Ajuste os parâmetros do filtro Kalman

### Leituras sempre máximas/mínimas:
- Verifique conexão do pino Vo
- Confirme alimentação de 5V no sensor
- Teste com `test_connection.py`

### Erro de I2C:
- Habilite I2C: `sudo raspi-config`
- Verifique conexões SDA/SCL
- Confirme endereço: `i2cdetect -y 1`

## 📁 Arquivos do Sistema

- `sensor_distance.py`: Sistema principal
- `test_connection.py`: Teste de hardware
- `install.sh`: Script de instalação
- `sensor_calibration.json`: Arquivo de calibração (gerado)
- `calibration_curve.png`: Gráfico de calibração (gerado)

## 🎓 Teoria de Operação

O GP2Y0A41SK0F usa triangulação IR:
1. LED IR emite luz modulada
2. Luz reflete no objeto
3. PSD (Position Sensitive Detector) detecta posição do reflexo
4. Circuito interno converte posição em tensão analógica

A relação tensão-distância segue aproximadamente:
```
V = k / (d + offset)
```

Onde:
- V = tensão de saída
- d = distância
- k, offset = constantes do sensor

## 📚 Referências

- [Datasheet GP2Y0A41SK0F](https://global.sharp/products/device/lineup/data/pdf/datasheet/gp2y0a41sk_e.pdf)
- [ADS1115 Documentation](https://www.ti.com/product/ADS1115)
- [Filtro Kalman](https://en.wikipedia.org/wiki/Kalman_filter)

## 💡 Melhorias Futuras

Para precisão ainda maior, considere:

1. **Compensação de temperatura**: Adicione sensor de temperatura
2. **Múltiplos sensores**: Use 2-3 sensores para redundância
3. **Calibração por tipo de material**: Perfis diferentes para cada superfície
4. **Machine Learning**: Treine modelo para corrigir não-linearidades

---

Desenvolvido para máxima precisão com o sensor GP2Y0A41SK0F