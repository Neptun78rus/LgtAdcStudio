// Переменные для отслеживания режима работы АЦП
byte adc_work_mode = 0; // 0 - стоп, 1 - одиночный, 2 - непрерывный поток

void setup() {
    Serial.begin(115200);

    // Базовая инициализация АЦП (включаем АЦП, задаем предделитель /32)
    ADCSRA = (1 << ADEN) | (1 << ADPS2 | 1 << ADPS0);
}

void loop() {
    // 1. ПАРСЕР БИНАРНОГО ПРОТОКОЛА UART
    if (Serial.available() >= 3) {
        // Ищем маркер начала пакета 0xAA
        if (Serial.read() == 0xAA) {
            byte p_type = Serial.read();  // Читаем тип фрейма
            byte length = Serial.read();  // Читаем длину полезных данных

            // Дожидаемся полной просадки полезных байт в буфер порта
            while (Serial.available() < length);

            // Обработка пакета ТИП 0x01: Прямая запись в физический регистр чипа
            if (p_type == 0x01 && length == 2) {
                byte reg_addr = Serial.read();
                byte reg_val  = Serial.read();
                volatile byte* pointer = (volatile byte*)reg_addr;
                *pointer = reg_val;
            }

            // =========================================================================
            // ДОБАВЛЕНО: Обработка пакета ТИП 0x02: Запрос синхронизации регистров из ПК
            // =========================================================================
            else if (p_type == 0x02 && length == 1) {
                byte cmd_data = Serial.read();

                // Если прилетел байт запроса 0xFF — выгружаем всю карту ADC-регистров обратно в ПК
                if (cmd_data == 0xFF) {
                    // Перечень адресов регистров (проверьте, чтобы они совпадали с adc_database.py!)
                    // Базовые: 0x27 (ADMUX), 0x26 (ADCSRA), 0xAD (ADCSRD)
                    // Калибровочные: 0xC8 (VCAL), 0xD1 (VCAL1), 0xCE (VCAL2), 0xCC (VCAL3)
                    // ТЕПЕРЬ СТРОГО ПО ВАШЕМУ ДАТАШИТУ (Для выгрузки в ПК):
                    uint8_t target_registers[] = {
                        0x7C,  // ADMUX (из таблицы)
                        0x7A,  // ADCSRA (из таблицы)
                        0xAD,  // ADCSRD (из таблицы)
                        0xC8,  // VCAL
                        0xCD,  // VCAL1
                        0xCE,  // VCAL2
                        0xCC   // VCAL3
                    };

                    uint8_t total_regs = sizeof(target_registers);

                    for (uint8_t i = 0; i < total_regs; i++) {
                        uint8_t addr = target_registers[i];

                        // Используем вашу магию указателей, чтобы прочитать живой байт из регистра МК
                        volatile byte* pointer = (volatile byte*)addr;
                        uint8_t val = *pointer;

                        // Формируем бинарный пакет ответа 0x02 для Python:
                        // Маркер (0xAA), Тип (0x02), Длина полезных данных (2 байта), [Адрес, Значение]
                        Serial.write(0xAA);
                        Serial.write(0x02);
                        Serial.write(0x02); // Длина — 2 байта
                        Serial.write(addr); // Байт 1: Физический адрес регистра
                        Serial.write(val);  // Байт 2: Текущее живое значение в чипе

                        // Крошечная микро-пауза, чтобы буфер UART МК успевал проплевывать байты
                        delayMicroseconds(50);
                    }
                }
            }

            // Обработка пакета ТИП 0x04: Управление режимом оцифровки
            else if (p_type == 0x04 && length == 1) {
                // ... ваш неизмененный код обработки adc_work_mode ...

                adc_work_mode = Serial.read();

                // Если попросили одиночный выстрел АЦП (mode_id = 1)
                if (adc_work_mode == 1) {
                    send_single_adc_sample();
                    adc_work_mode = 0; // Сбрасываем в стоп
                }
            }

            // Если прилетели неизвестные байты, просто вычищаем их из буфера
            else {
                for (int i = 0; i < length; i++) Serial.read();
            }
        }
    }

    // 2. АВТОМАТ НЕПРЕРЫВНОГО ПОТОКА АЦП (Режим mode_id = 2)
    if (adc_work_mode == 2) {
        // Делаем замер на максимальной аппаратной скорости, заданной регистрами
        bitSet(ADCSRA, ADSC);
        while (bit_is_set(ADCSRA, ADSC)); // Ждем окончания оцифровки

        uint16_t adc_val = ADC; // Забираем полные 12 бит

        // Собираем бинарный ответ ТИП 0x03 (Сырые данные АЦП)
        // Формат пакета: 0xAA, Тип (0x03), Длина (2 байта), Старший байт, Младший байт
        byte high_b = (adc_val >> 8) & 0xFF;
        byte low_b  = adc_val & 0xFF;

        Serial.write(0xAA);
        Serial.write(0x03);
        Serial.write(0x02); // Длина данных — 2 байта
        Serial.write(high_b);
        Serial.write(low_b);

        // Небольшая микро-пауза, чтобы не душить графику Python (примерно 100 Гц выдачи)
        delay(10);
    }
}

// Функция отправки одиночного замера (для кнопки "Одиночное преобразование")
void send_single_adc_sample() {
    bitSet(ADCSRA, ADSC);
    while (bit_is_set(ADCSRA, ADSC));
    uint16_t adc_val = ADC;

    Serial.write(0xAA);
    Serial.write(0x03);
    Serial.write(0x02);
    Serial.write((adc_val >> 8) & 0xFF);
    Serial.write(adc_val & 0xFF);
}
