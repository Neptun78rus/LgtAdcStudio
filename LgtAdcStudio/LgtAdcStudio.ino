#define LED_PIN 13

void setup() {
  // Открываем порт на нашей стандартной скорости
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);

  // АЦП включен, делитель частоты 64 (500 кГц при тактовой частоте ядра 32 МГц)
  ADCSRA = (1 << ADEN) | (1 << ADPS2) | (1 << ADPS1);
  ADCSRB = 0;
  ADCSRD = 0; // Честный 12-битный режим без программных сдвигов

  // Стартовое состояние ADMUX: Опорное напряжение = AVCC (биты REFS1=0, REFS0=1)
  // По умолчанию выбран канал 0 (ADC0 / PC0)
  ADMUX = (1 << REFS0);

  digitalWrite(LED_PIN, HIGH);
  delay(200);
  digitalWrite(LED_PIN, LOW);
}

void loop() {
    if (Serial.available() > 0) {
        String input = Serial.readStringUntil('\n');
        input.trim();
        input.toUpperCase();

        // Команда 1: Настройка мультиплексора
        if (input.startsWith("CHMUX=")) {
            int channel_index = input.substring(6).toInt();
            if (channel_index >= 0 && channel_index <= 16) {
                byte current_admux = ADMUX & 0xE0;
                ADMUX = current_admux | (channel_index & 0x1F); // Записываем биты CHMUX

                // Сразу возвращаем подтверждение в Python
                Serial.print(F("ADMUX_READY:0x"));
                Serial.println(ADMUX, HEX);
            }
        }

        // Команда 2: Ручной пуск одиночного преобразования АЦП
        else if (input == "START_ADC") {
            // Аппаратный запуск одиночного замера
            bitSet(ADCSRA, ADSC);
            while (bit_is_set(ADCSRA, ADSC)); // Ждем окончания оцифровки
            uint16_t adc_raw = ADC; // Забираем 12 бит

            // Отправляем строго один пакет обратно в Python
            Serial.print(F("ADC:"));
            Serial.print(adc_raw);
            Serial.print(F(","));
            Serial.println(ADMUX);
        }
    }
}
