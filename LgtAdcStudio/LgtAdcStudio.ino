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
  // Если в буфере UART появились данные от Python
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    input.toUpperCase();

    // Проверяем, что пришла именно команда переключения мультиплексора
    if (input.startsWith("CHMUX=")) {
      // Вытаскиваем числовое значение канала после знака "="
      int channel_index = input.substring(6).toInt();

      // Защита: индекс канала должен быть строго в пределах таблицы (0..16)
      if (channel_index >= 0 && channel_index <= 16) {

        digitalWrite(LED_PIN, HIGH); // Мигнем светодиодом в знак приема данных

        // --- МАГИЯ ПЕРЕКЛЮЧЕНИЯ БИТОВ CHMUX ---
        // 1. Сначала полностью очищаем младшие 5 бит (биты 4, 3, 2, 1, 0) в регистре ADMUX,
        // чтобы не испортить старшие биты REFS0, REFS1 и ADLAR.
        // Маска 0xE0 (1110 0000 в двоичной) сохраняет старшие биты и зануляет CHMUX.
        byte current_admux = ADMUX & 0xE0;

        // 2. Накладываем наше число (индекс канала) на очищенное место.
        // Так как биты CHMUX[4:0] занимают позиции с 0 по 4, сдвигать число не нужно!
        // Маска 0x1F (0001 1111) гарантирует, что мы не вылезем за пределы 5 бит.
        ADMUX = current_admux | (channel_index & 0x1F);

        // 3. Делаем один пробный замер, чтобы АЦП аппаратно переключил коммутатор
        bitSet(ADCSRA, ADSC);
        while (bit_is_set(ADCSRA, ADSC));

        digitalWrite(LED_PIN, LOW);

        // Отправляем ответ в Python, что регистр успешно обновлен
        Serial.print(F("✅ МК принял команду! ADMUX установлен в: 0x"));
        Serial.println(ADMUX, HEX);
      } else {
        Serial.println(F("❌ Ошибка: Индекс канала вне диапазона (0..16)"));
      }
    }
  }
}
