# FILE: adc_schematic.py
import tkinter as tk
from tkinter import ttk
import os

# Подгружаем нашу общую базу данных
from adc_database import adc_registers_data

class SchematicWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Блок-схема АЦП из документации (Чистый вектор)")
        self.geometry("1100x750")

        self.padding = 20
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.svg_path = os.path.join(os.path.dirname(__file__), "adc_scheme.svg")
        self.bg_image = None

        # Размеры исходного SVG-файла (Inkscape).
        # Если вы обрезали холст впритык, эти значения не важны, программа сама их вычислит
        self.svg_orig_w = 930
        self.svg_orig_h = 600

        # Переменные для хранения текущего масштаба и сдвига схемы на экране
        self.current_scale = 1.0
        self.offset_x = self.padding
        self.offset_y = self.padding

        try:
            self.tk.call('package', 'require', 'tksvg')
        except Exception as e:
            print(f"Ошибка tksvg: {e}")

        # Инженерный кликер: ТЕПЕРЬ ОН ВЫВОДИТ СРАЗУ ОТНОСИТЕЛЬНЫЕ КООРДИНАТЫ (0.0 - 1.0)!
        self.canvas.bind("<Button-1>", self.on_engineer_click)
        self.canvas.bind("<Configure>", self.resize_vector)

        self.update_schematic()

    def resize_vector(self, event):
        """Умное масштабирование с защитным запасом по высоте для 1080p экранов"""
        if not os.path.exists(self.svg_path): return

        win_w = event.width
        win_h = event.height

        # Считаем доступное пространство внутри окна с учетом полей
        avail_w = win_w - (self.padding * 2)
        avail_h = win_h - (self.padding * 2)

        if avail_w <= 10 or avail_h <= 10: return

        # Вычисляем коэффициенты масштабирования по ширине и по высоте
        scale_x = avail_w / self.svg_orig_w
        scale_y = avail_h / self.svg_orig_h

        # Вводим защитный коэффициент 0.93 для вертикальной оси.
        # Это искусственно уменьшит схему по высоте на 7%, чтобы она никогда не поджималась снизу
        scale_y_safe = scale_y * 0.91

        # Выбираем МИНИМАЛЬНЫЙ масштаб из двух осей для сохранения жестких инженерных пропорций
        self.current_scale = min(scale_x, scale_y_safe)

        # Вычисляем итоговый размер картинки на экране
        target_w = int(self.svg_orig_w * self.current_scale)
        target_h = int(self.svg_orig_h * self.current_scale)

        # Центрируем схему в окне по горизонтали и вертикали
        self.offset_x = self.padding + (avail_w - target_w) // 2
        self.offset_y = self.padding + (avail_h - target_h) // 2

        try:
            # Рендерим SVG строго по рассчитанной ширине target_w
            self.bg_image = tk.PhotoImage(file=self.svg_path, format=f"svg -scaletowidth {target_w}")

            self.canvas.delete("static_bg")
            self.canvas.create_image(self.offset_x, self.offset_y, image=self.bg_image, anchor="nw", tags="static_bg")

            # Сразу заставляем обновиться динамические линии
            self.update_schematic()
        except Exception as e:
            print(f"Ошибка рендеринга векторов: {e}")


    def on_engineer_click(self, event):
        """Кликер: выводит координаты в консоль И обрабатывает клик по мультиплексору"""
        # Считаем положение клика относительно левого верхнего угла схемы (в процентах от 0.0 до 1.0)
        rel_x = (event.x - self.offset_x) / (self.svg_orig_w * self.current_scale)
        rel_y = (event.y - self.offset_y) / (self.svg_orig_h * self.current_scale)

        print(f"Относительные координаты для кода: {rel_x:.4f}, {rel_y:.4f}")

        # =========================================================================
        # ИНТЕРАКТИВНЫЙ КЛИК ПО МУЛЬТИПЛЕКСОРУ CHMUX (Каналы 0-16)
        # =========================================================================
        if 0.2029 <= rel_x <= 0.2850 and 0.1500 <= rel_y <= 0.6000:
            current_admux = adc_registers_data["ADMUX"].get("current_value", 0)

            # Сохраняем текущую опору REFS (старшие биты 7 и 6, маска 0xC0)
            current_refs_bits = current_admux & 0xC0

            # Выделяем старый канал и прибавляем 1
            current_channel = current_admux & 0x1F
            new_channel = (current_channel + 1) % 17

            # Собираем новый байт: склеиваем сохраненную опору и новый канал!
            new_admux = current_refs_bits | new_channel
            adc_registers_data["ADMUX"]["current_value"] = new_admux

            # Обновляем биты канала CHMUX[4:0] в массиве (индексы 3-7)
            for idx, bit_pos in enumerate(range(4, -1, -1)):
                if (3 + idx) < len(adc_registers_data["ADMUX"]["bits"]):
                    adc_registers_data["ADMUX"]["bits"][3 + idx]["state"] = (new_channel >> bit_pos) & 0x01

            if hasattr(self.master, 'update_table_view'): self.master.update_table_view()
            if hasattr(self.master, 'worker') and self.master.worker and self.master.worker.is_alive():
                addr = int(adc_registers_data["ADMUX"]["address"], 16)
                self.master.worker.send_packet(0x01, bytes([addr, new_admux]))
            self.update_schematic()
            return

         # =========================================================================
        # 1. ИНТЕРАКТИВНЫЙ КЛИК ПО МУЛЬТИПЛЕКСОРУ REFS (Трапеция сверху)
        # =========================================================================
        if 0.8100 <= rel_x <= 0.8600 and 0.1200 <= rel_y <= 0.1800:
            current_admux = adc_registers_data["ADMUX"].get("current_value", 0)
            current_adcsrd = adc_registers_data["ADCSRD"].get("current_value", 0)

            # Вычисляем текущий сквозной шаг по честной бинарной формуле
            admux_refs = (current_admux >> 6) & 0x03
            refs2_bit = (current_adcsrd >> 6) & 0x01

            if refs2_bit == 1 and admux_refs == 0:
                current_mode = 4  # 4.096V
            else:
                current_mode = admux_refs  # 0: AREF, 1: AVCC, 2: 2.048V, 3: 1.024V

            # Инкремент сквозного шага по кругу (от 0 до 4)
            new_mode = (current_mode + 1) % 5

            # --- НАКЛАДЫВАЕМ МАСКИ НА ADMUX (биты 7 и 6) ---
            # Очищаем биты 7 и 6 (маска ~0xC0), берем младшие 2 бита от new_mode и двигаем их на место
            new_admux = (current_admux & ~0xC0) | ((new_mode & 0x03) << 6)
            adc_registers_data["ADMUX"]["current_value"] = new_admux

            # --- НАКЛАДЫВАЕМ МАСКИ НА ADCSRD (бит 6) ---
            # Очищаем бит 6 (маска ~0x40), берем старший бит от new_mode (бит позиция 2) и двигаем в бит 6
            refs2_new_value = (new_mode >> 2) & 0x01
            new_adcsrd = (current_adcsrd & ~0x40) | (refs2_new_value << 6)
            adc_registers_data["ADCSRD"]["current_value"] = new_adcsrd

            # --- СИНХРОНИЗАЦИЯ ЧЕКБОКСОВ GUI ---
            # ADMUX биты REFS1 и REFS0 (обычно индексы 0 и 1 в массиве bits от 7 к 0)
            if len(adc_registers_data["ADMUX"]["bits"]) >= 2:
                adc_registers_data["ADMUX"]["bits"][0]["state"] = (new_admux >> 7) & 0x01
                adc_registers_data["ADMUX"]["bits"][1]["state"] = (new_admux >> 6) & 0x01

            # ADCSRD бит REFS2 (обычно индекс 1 в массиве битов от 7 к 0)
            if len(adc_registers_data["ADCSRD"]["bits"]) >= 2:
                adc_registers_data["ADCSRD"]["bits"][1]["state"] = (new_adcsrd >> 6) & 0x01

            # Синхронизируем главную таблицу интерфейса
            if hasattr(self.master, 'update_table_view'):
                self.master.update_table_view()

            # Отправляем измененные регистры по UART в микроконтроллер LGT
            if hasattr(self.master, 'worker') and self.master.worker and self.master.worker.is_alive():
                addr_admux = int(adc_registers_data["ADMUX"]["address"], 16)
                addr_asrd = int(adc_registers_data["ADCSRD"]["address"], 16)
                self.master.worker.send_packet(0x01, bytes([addr_admux, new_admux]))
                self.master.worker.send_packet(0x01, bytes([addr_asrd, new_adcsrd]))

            print(f" Мультиплексор REFS! Переключен на шаг {new_mode} (ADMUX: 0x{new_admux:02X}, ADCSRD: 0x{new_adcsrd:02X})")

            self.update_schematic()
            return


        # =========================================================================
        # ИНТЕРАКТИВНЫЙ КЛИК ПО МУЛЬТИПЛЕКСОРУ DIFF (DIFS)
        # Проверяем, попал ли клик внутрь оранжевой трапеции DIFF на схеме
        # =========================================================================
        if 0.6511 <= rel_x <= 0.6745 and 0.3428 <= rel_y <= 0.4620:
            # 1. Читаем текущее полное значение регистра ADCSRC из базы данных
            current_adcsrc = adc_registers_data["ADCSRC"].get("current_value", 0)

            # 2. Инвертируем Бит 1 (маска 0x02) с помощью операции XOR (Исключающее ИЛИ)
            new_adcsrc = current_adcsrc ^ 0x02

            # 3. Записываем обновленный байт обратно в централизованную базу данных
            adc_registers_data["ADCSRC"]["current_value"] = new_adcsrc

            # 4. Обновляем флаг бита state в структуре для корректного отображения чекбоксов
            # Бит 1 — это обычно 6-й элемент по счету от 7-го бита (7, 6, 5, 4, 3, 2, 1, 0)
            # Для надежности просто найдем его по индексу в массиве bits
            if len(adc_registers_data["ADCSRC"]["bits"]) > 6:
                adc_registers_data["ADCSRC"]["bits"][6]["state"] = (new_adcsrc >> 1) & 0x01

            # 5. Синхронизируем главную таблицу на основном экране
            if hasattr(self.master, 'update_table_view'):
                self.master.update_table_view()

            # 6. Отправляем измененный байт регистра по UART в реальный микроконтроллер (Тип пакета 0x01)
            if hasattr(self.master, 'worker') and self.master.worker and self.master.worker.is_alive():
                addr = int(adc_registers_data["ADCSRC"]["address"], 16)
                self.master.worker.send_packet(0x01, bytes([addr, new_adcsrc]))

            # Выводим инженерный лог для контроля в терминале
            old_state = (current_adcsrc >> 1) & 0x01
            new_state = (new_adcsrc >> 1) & 0x01
            print(f" Схема переключила мультиплексор DIFS! Старый бит: {old_state} -> Новый: {new_state} (ADCSRC: 0x{new_adcsrc:02X})")

            # Принудительно перерисовываем динамические зеленые линии
            self.update_schematic()
        # =========================================================================
        # ИНТЕРАКТИВНЫЙ КЛИК ПО ТРАНЗИСТОРУ ЗАЗЕМЛЕНИЯ ADEN (Питание АЦП)
        # =========================================================================
        # ЗАМЕНИТЕ КООРДИНАТЫ НИЖЕ НА ТЕ, ЧТО ВЫДАСТ КЛИКЕР ПРИ НАЖАТИИ НА КЛЮЧ ADEN СНИЗУ АЦП!
        if 0.7346 <= rel_x <= 0.8437 and 0.5824 <= rel_y <= 0.6232:
            # 1. Читаем регистр ADCSRA
            current_adcsra = adc_registers_data["ADCSRA"].get("current_value", 0)

            # 2. Инвертируем Бит 7 (маска 0x80) с помощью XOR
            new_adcsra = current_adcsra ^ 0x80

            # 3. Сохраняем в базу данных
            adc_registers_data["ADCSRA"]["current_value"] = new_adcsra

            # 4. Обновляем бит state для чекбоксов (Бит 7 — это самый первый элемент)
            if len(adc_registers_data["ADCSRA"]["bits"]) > 0:
                adc_registers_data["ADCSRA"]["bits"][0]["state"] = (new_adcsra >> 7) & 0x01

            # 5. Синхронизируем GUI-таблицу
            if hasattr(self.master, 'update_table_view'):
                self.master.update_table_view()

            # 6. Шлем пакет в МК
            if hasattr(self.master, 'worker') and self.master.worker and self.master.worker.is_alive():
                addr = int(adc_registers_data["ADCSRA"]["address"], 16)
                self.master.worker.send_packet(0x01, bytes([addr, new_adcsra]))

            print(f" Ключ ADEN изменен! Старый: {(current_adcsra >> 7) & 1} -> Новый: {(new_adcsra >> 7) & 1} (ADCSRA: 0x{new_adcsra:02X})")
            self.update_schematic()

        # =========================================================================
        # ИНТЕРАКТИВНЫЙ КЛИК ПО ТРАНЗИСТОРУ ЗАЗЕМЛЕНИЯ DAPEN (Питание диф. усилителя)
        # =========================================================================
        # ЗАМЕНИТЕ КООРДИНАТЫ НИЖЕ НА ТЕ, ЧТО ВЫДАСТ КЛИКЕР ПРИ НАЖАТИИ НА КЛЮЧ DAPEN СНИЗУ DAP!
        if 0.4153 <= rel_x <= 0.5193 and 0.9570 <= rel_y <= 1.0069:
            # 1. Читаем регистр DAPCR
            current_dapcr = adc_registers_data["DAPCR"].get("current_value", 0)

            # 2. Инвертируем Бит 7 (маска 0x80) с помощью XOR
            new_dapcr = current_dapcr ^ 0x80

            # 3. Сохраняем в базу
            adc_registers_data["DAPCR"]["current_value"] = new_dapcr

            # 4. Обновляем бит state для чекбоксов (Бит 7 — это самый первый элемент)
            if len(adc_registers_data["DAPCR"]["bits"]) > 0:
                adc_registers_data["DAPCR"]["bits"][0]["state"] = (new_dapcr >> 7) & 0x01

            # 5. Синхронизируем GUI-таблицу
            if hasattr(self.master, 'update_table_view'):
                self.master.update_table_view()

            # 6. Шлем пакет в МК
            if hasattr(self.master, 'worker') and self.master.worker and self.master.worker.is_alive():
                addr = int(adc_registers_data["DAPCR"]["address"], 16)
                self.master.worker.send_packet(0x01, bytes([addr, new_dapcr]))

            print(f" Ключ DAPEN изменен! Старый: {(current_dapcr >> 7) & 1} -> Новый: {(new_dapcr >> 7) & 1} (DAPCR: 0x{new_dapcr:02X})")
            self.update_schematic()
        # =========================================================================
        # ИНТЕРАКТИВНЫЙ КЛИК ПО КВАДРАТИКУ ПРЕДДЕЛИТЕЛЯ (Prescaler)
        # =========================================================================
        # ПОДСТАВЬТЕ СЮДА ВАШИ ТОЧНЫЕ КООРДИНАТЫ ИЗ ТЕРМИНАЛА ПРИ КЛИКЕ НА КВАДРАТИК:
        if 0.7440 <= rel_x <= 0.7940 and 0.3740 <= rel_y <= 0.4240:
            # 1. Читаем текущее значение регистра ADCSRA
            current_adcsra = adc_registers_data["ADCSRA"].get("current_value", 0)

            # 2. Выделяем 3 младших бита предделителя (маска 0x07)
            current_ps = current_adcsra & 0x07

            # 3. Увеличиваем на 1 циклом (от 0 до 7)
            new_ps = current_ps + 1
            if new_ps > 7:
                new_ps = 0

            # 4. Сохраняем остальные старшие биты регистра ADCSRA, очищая старый предделитель
            new_adcsra = (current_adcsra & ~0x07) | new_ps

            # 5. Записываем обновленный байт обратно в базу данных
            adc_registers_data["ADCSRA"]["current_value"] = new_adcsra

            # Обновляем флаги bits state для трех младших чекбокса (биты 2, 1, 0)
            # В массиве базы данных от 7 к 0 они лежат на индексах 5, 6, 7
            if len(adc_registers_data["ADCSRA"]["bits"]) >= 8:
                adc_registers_data["ADCSRA"]["bits"][5]["state"] = (new_ps >> 2) & 0x01  # ADPS2
                adc_registers_data["ADCSRA"]["bits"][6]["state"] = (new_ps >> 1) & 0x01  # ADPS1
                adc_registers_data["ADCSRA"]["bits"][7]["state"] = (new_ps >> 0) & 0x01  # ADPS0

            # 6. Синхронизируем главную таблицу на основном экране
            if hasattr(self.master, 'update_table_view'):
                self.master.update_table_view()

            # 7. Отправляем байт по UART в МК
            if hasattr(self.master, 'worker') and self.master.worker and self.master.worker.is_alive():
                addr = int(adc_registers_data["ADCSRA"]["address"], 16)
                self.master.worker.send_packet(0x01, bytes([addr, new_adcsra]))

            print(f" Схема изменила предделитель АЦП! Старый код: {current_ps} -> Новый код: {new_ps} (ADCSRA: 0x{new_adcsra:02X})")

            # Принудительно перерисовываем схему для вывода нового числа
            self.update_schematic()
        # =========================================================================
        # ИНТЕРАКТИВНЫЙ КЛИК ПО КВАДРАТИКУ КОЭФФИЦИЕНТА УСИЛЕНИЯ DAP (GA[1:0])
        # =========================================================================
        # Зона клика рассчитана от вашего левого верхнего угла (0.4833, 0.8017)
        if 0.4833 <= rel_x <= 0.5433 and 0.8017 <= rel_y <= 0.8517:
            # 1. Читаем текущее значение регистра DAPCR
            current_dapcr = adc_registers_data["DAPCR"].get("current_value", 0)

            # 2. Выделяем биты 6 и 5 (GA1 и GA0). Сдвигаем их на 5 позиций вправо, чтобы получить число от 0 до 3
            current_gain_code = (current_dapcr >> 5) & 0x03

            # 3. Циклически увеличиваем код множителя от 0 до 3 (0 -> 1 -> 2 -> 3 -> 0)
            new_gain_code = current_gain_code + 1
            if new_gain_code > 3:
                new_gain_code = 0

            # 4. Очищаем старые биты 6 и 5 в регистре (маска ~(0x03 << 5) = ~0x60) и записываем новые
            new_dapcr = (current_dapcr & ~0x60) | (new_gain_code << 5)

            # 5. Записываем обновленный байт обратно в базу данных
            adc_registers_data["DAPCR"]["current_value"] = new_dapcr

            # Обновляем флаги bits state для чекбоксов (GA1 и GA0).
            # В массиве от 7 к 0 они лежат на индексах 1 и 2
            if len(adc_registers_data["DAPCR"]["bits"]) >= 3:
                adc_registers_data["DAPCR"]["bits"][1]["state"] = (new_gain_code >> 1) & 0x01  # GA1
                adc_registers_data["DAPCR"]["bits"][2]["state"] = (new_gain_code >> 0) & 0x01  # GA0

            # 6. Синхронизируем главную таблицу на основном экране
            if hasattr(self.master, 'update_table_view'):
                self.master.update_table_view()

            # 7. Отправляем байт по UART в МК
            if hasattr(self.master, 'worker') and self.master.worker and self.master.worker.is_alive():
                addr = int(adc_registers_data["DAPCR"]["address"], 16)
                self.master.worker.send_packet(0x01, bytes([addr, new_dapcr]))

            print(f" Схема изменила усиление DAP! Старый код: {current_gain_code} -> Новый: {new_gain_code} (DAPCR: 0x{new_dapcr:02X})")

            # Принудительно перерисовываем схему для вывода нового текста
            self.update_schematic()


        # =========================================================================
        # 2. ИНТЕРАКТИВНЫЙ КЛИК ПО ТАБЛО ИОН: РУЧНОЙ ЦИКЛ КОПИРОВАНИЯ КОНСТАНТ В VCAL
        # =========================================================================
        if 0.9200 <= rel_x <= 1.0100 and 0.0200 <= rel_y <= 0.0900:
            if not hasattr(self, 'vcal_cycle_mode'):
                self.vcal_cycle_mode = 0  # 0: VCAL1(1V), 1: VCAL2(2V), 2: VCAL3(4V), 3: Default

            self.vcal_cycle_mode = (self.vcal_cycle_mode + 1) % 4

            if self.vcal_cycle_mode == 0:
                chosen_vcal = adc_registers_data.get("VCAL1", {}).get("current_value", int(adc_registers_data["VCAL"]["default"], 16))
                msg = "Записана константа VCAL1 (для 1.024V)"
            elif self.vcal_cycle_mode == 1:
                chosen_vcal = adc_registers_data.get("VCAL2", {}).get("current_value", 0x4A)
                msg = "Записана константа VCAL2 (для 2.048V)"
            elif self.vcal_cycle_mode == 2:
                chosen_vcal = adc_registers_data.get("VCAL3", {}).get("current_value", 0x8F)
                msg = "Записана константа VCAL3 (для 4.096V)"
            else:
                chosen_vcal = int(adc_registers_data["VCAL"]["default"], 16)
                msg = "Записано дефолтное значение VCAL"

            # Записываем в базу данных рабочего регистра VCAL
            adc_registers_data["VCAL"]["current_value"] = chosen_vcal

            # Синхронизируем основную GUI-таблицу
            if hasattr(self.master, 'update_table_view'):
                self.master.update_table_view()

            # Шлем по UART в МК
            if hasattr(self.master, 'worker') and self.master.worker and self.master.worker.is_alive():
                addr_vcal = int(adc_registers_data["VCAL"]["address"], 16)
                self.master.worker.send_packet(0x01, bytes([addr_vcal, chosen_vcal]))

            print(f" Ручная калибровка: {msg} -> VCAL: 0x{chosen_vcal:02X}")
            self.update_schematic()
            return

        # =========================================================================
        # УМНЫЙ РАДИАЛЬНЫЙ КЛИК ПО ПИНАМ DIDR (Включая вход APN4 на ножке PE0)
        # =========================================================================
        # Твои точные координаты центров пинов на схеме (12 основных + 1 для APN4)
        didr_coords = {
            0:  (0.0630, 0.1697),  # ADC0
            1:  (0.0630, 0.1924),  # ADC1
            2:  (0.0630, 0.2174),  # ADC2
            3:  (0.0630, 0.2414),  # ADC3
            4:  (0.0630, 0.2650),  # ADC4
            5:  (0.0630, 0.2892),  # ADC5
            6:  (0.0630, 0.3131),  # ADC6
            7:  (0.0630, 0.3370),  # ADC7
            8:  (0.0630, 0.3608),  # ADC8
            9:  (0.0630, 0.3847),  # ADC9
            10: (0.0630, 0.4086),  # ADC10
            11: (0.0630, 0.4330),  # ADC11
            12: (0.0666, 0.9286)   # APN4 (Ножка PE0)
        }

        closest_channel = None
        min_distance = 999.0

        for ch, (pin_x, pin_y) in didr_coords.items():
            dx = rel_x - pin_x
            dy = rel_y - pin_y
            distance = (dx**2 + dy**2) ** 0.5

            if distance < min_distance:
                min_distance = distance
                closest_channel = ch

        # Ловим прецизионный клик с комфортным радиусом захвата 0.035
        if closest_channel is not None and min_distance <= 0.035:

            # Карта соответствия: Номер канала -> (Имя регистра, Бит в регистре)
            # Добавлен 12-й канал, который управляет битом PE0D (Бит 0) в DIDR1!
            didr_mapping = {
                0:  ("DIDR0", 0), 1: ("DIDR0", 1), 2: ("DIDR0", 2), 3: ("DIDR0", 3),
                4:  ("DIDR0", 4), 5: ("DIDR0", 5), 6: ("DIDR0", 6), 7: ("DIDR0", 7),
                8:  ("DIDR1", 2), 9: ("DIDR1", 3), 10: ("DIDR1", 6), 11: ("DIDR1", 7),
                12: ("DIDR1", 0)   # APN4 -> Регистр DIDR1, Бит 0 (PE0D)
            }

            reg_name, bit_pos = didr_mapping[closest_channel]

            # 1. Читаем текущее значение нужного регистра
            current_reg_value = adc_registers_data[reg_name].get("current_value", 0)

            # 2. Переключаем нужный бит через XOR маску
            bit_mask = 1 << bit_pos
            new_reg_value = current_reg_value ^ bit_mask

            # 3. Сохраняем обновленный байт обратно в базу данных панели
            adc_registers_data[reg_name]["current_value"] = new_reg_value

            # 4. Обновляем бит state для чекбоксов (индекс = 7 - bit_pos)
            bit_idx = 7 - bit_pos
            if bit_idx < len(adc_registers_data[reg_name]["bits"]):
                adc_registers_data[reg_name]["bits"][bit_idx]["state"] = (new_reg_value >> bit_pos) & 0x01

            # 5. Синхронизируем главную GUI-таблицу на экране
            if hasattr(self.master, 'update_table_view'):
                self.master.update_table_view()

            # 6. Отправляем байт регистра по UART в реальный микроконтроллер LGT
            if hasattr(self.master, 'worker') and self.master.worker and self.master.worker.is_alive():
                addr = int(adc_registers_data[reg_name]["address"], 16)
                self.master.worker.send_packet(0x01, bytes([addr, new_reg_value]))

            # Инженерный лог контроля
            p_name = f"ADC{closest_channel}" if closest_channel < 12 else "APN4(PE0)"
            print(f"🎯 Радиальный клик! {p_name} -> {reg_name}, Бит {bit_pos}. Статус: {abs((new_reg_value >> bit_pos) & 1)}")

            self.update_schematic()
            return


        # =========================================================================
        # КЛИК ПО МУЛЬТИПЛЕКСОРУ ПОЛОЖИТЕЛЬНОГО ВХОДA ОУ (Биты DPS[1:0] в DAPCR)
        # =========================================================================
        if 0.3415 <= rel_x <= 0.3685 and 0.6470 <= rel_y <= 0.7630:
            current_dapcr = adc_registers_data["DAPCR"].get("current_value", 0)
            current_dps = current_dapcr & 0x03
            new_dps = (current_dps + 1) % 4

            new_dapcr = (current_dapcr & ~0x03) | new_dps
            adc_registers_data["DAPCR"]["current_value"] = new_dapcr

            if len(adc_registers_data["DAPCR"]["bits"]) >= 8:
                adc_registers_data["DAPCR"]["bits"][6]["state"] = (new_dps >> 1) & 0x01
                adc_registers_data["DAPCR"]["bits"][7]["state"] = (new_dps >> 0) & 0x01

            if hasattr(self.master, 'update_table_view'): self.master.update_table_view()
            if hasattr(self.master, 'worker') and self.master.worker and self.master.worker.is_alive():
                addr = int(adc_registers_data["DAPCR"]["address"], 16)
                self.master.worker.send_packet(0x01, bytes([addr, new_dapcr]))

            print(f"🎯 Клик DPS: {current_dps} -> {new_dps} (DAPCR: 0x{new_dapcr:02X})")
            self.update_schematic()
            return
        # =========================================================================
        # КЛИК ПО МУЛЬТИПЛЕКСОРУ ОТРИЦАТЕЛЬНОГО ВХОДА ОУ (Биты DNS[2:0] в DAPCR)
        # =========================================================================
        # Зона клика рассчитана строго под нижнюю оранжевую трапецию на схеме
        if 0.3425 <= rel_x <= 0.3665 and 0.8172 <= rel_y <= 0.9967:
            current_dapcr = adc_registers_data["DAPCR"].get("current_value", 0)

            # Выделяем текущий код DNS (биты 4, 3, 2 — сдвигаем вправо на 2 и берем маску 0x07)
            current_dns = (current_dapcr >> 2) & 0x07
            # Циклический инкремент по кругу от 0 до 6
            new_dns = (current_dns + 1) % 7

            # Накладываем маску: очищаем биты 4, 3, 2 (маска ~(0x07 << 2) = ~0x1C) и пишем новый код
            new_dapcr = (current_dapcr & ~0x1C) | (new_dns << 2)
            adc_registers_data["DAPCR"]["current_value"] = new_dapcr

            # Синхронизируем чекбоксы GUI (биты DNS2, DNS1, DNS0 лежат на индексах 3, 4, 5)
            if len(adc_registers_data["DAPCR"]["bits"]) >= 6:
                adc_registers_data["DAPCR"]["bits"][3]["state"] = (new_dns >> 2) & 0x01  # DNS2
                adc_registers_data["DAPCR"]["bits"][4]["state"] = (new_dns >> 1) & 0x01  # DNS1
                adc_registers_data["DAPCR"]["bits"][5]["state"] = (new_dns >> 0) & 0x01  # DNS0

            if hasattr(self.master, 'update_table_view'):
                self.master.update_table_view()

            if hasattr(self.master, 'worker') and self.master.worker and self.master.worker.is_alive():
                addr = int(adc_registers_data["DAPCR"]["address"], 16)
                self.master.worker.send_packet(0x01, bytes([addr, new_dapcr]))

            print(f"🎯 Клик DNS! Коммутатор ОУ (-) изменен: {current_dns} -> {new_dns} (DAPCR: 0x{new_dapcr:02X})")
            self.update_schematic()
            return
        # =========================================================================
        # КЛИК ПО МУЛЬТИПЛЕКСОРУ ДЕЛИТЕЛЯ НАПРЯЖЕНИЯ (Биты VDS[2:0] в ADCSRD)
        # =========================================================================
        # Ориентировочная зона трапеции делителя (подправь, если твоя шире)
        if 0.8018 <= rel_x <= 0.8278 and 0.7708 <= rel_y <= 0.9256:
            current_adcsrd = adc_registers_data["ADCSRD"].get("current_value", 0)

            # Выделяем биты 2, 1, 0 (маска 0x07)
            current_vds = current_adcsrd & 0x07
            # Крутим циклически по кругу рабочие состояния от 0 до 5
            new_vds = (current_vds + 1) % 7

            # Точечно очищаем младшие 3 бита и пишем новый код VDS
            new_adcsrd = (current_adcsrd & ~0x07) | new_vds
            adc_registers_data["ADCSRD"]["current_value"] = new_adcsrd

            # Синхронизируем флаги чекбоксов в GUI (биты 2, 1, 0 лежат в конце массива bits)
            if len(adc_registers_data["ADCSRD"]["bits"]) >= 8:
                adc_registers_data["ADCSRD"]["bits"][5]["state"] = (new_vds >> 2) & 0x01  # VDS2
                adc_registers_data["ADCSRD"]["bits"][6]["state"] = (new_vds >> 1) & 0x01  # VDS1
                adc_registers_data["ADCSRD"]["bits"][7]["state"] = (new_vds >> 0) & 0x01  # VDS0

            if hasattr(self.master, 'update_table_view'):
                self.master.update_table_view()

            if hasattr(self.master, 'worker') and self.master.worker and self.master.worker.is_alive():
                addr = int(adc_registers_data["ADCSRD"]["address"], 16)
                self.master.worker.send_packet(0x01, bytes([addr, new_adcsrd]))

            print(f"🎯 Клик VDS! Коммутатор делителя изменен: {current_vds} -> {new_vds} (ADCSRD: 0x{new_adcsrd:02X})")
            self.update_schematic()
            return


    def draw_rel_line(self, x1, y1, x2, y2, color, width):
        """Вспомогательный метод: переводит проценты обратно в пиксели экрана под любой текущий масштаб"""
        w_pixels = self.svg_orig_w * self.current_scale
        h_pixels = self.svg_orig_h * self.current_scale

        px1 = self.offset_x + (x1 * w_pixels)
        py1 = self.offset_y + (y1 * h_pixels)
        px2 = self.offset_x + (x2 * w_pixels)
        py2 = self.offset_y + (y2 * h_pixels)

        self.canvas.create_line(px1, py1, px2, py2, fill=color, width=width, tags="dynamic_lines")

    def draw_rel_pin(self, cx, cy, w_len, h_thick, color):
        """Вспомогательный метод: рисует скругленный горизонтальный пин (прямоугольник)"""
        w_pixels = self.svg_orig_w * self.current_scale
        h_pixels = self.svg_orig_h * self.current_scale

        # Вычисляем центральную точку в пикселях
        px = self.offset_x + (cx * w_pixels)
        py = self.offset_y + (cy * h_pixels)

        # Рисуем пин как толстую линию со скругленными краями
        half_w = w_len / 2
        self.canvas.create_line(px - half_w, py, px + half_w, py,
                                fill=color, width=h_thick, capstyle="round", tags="dynamic_lines")


    def update_schematic(self):
        """ Динамическая подсветка дорожек в зависимости от бит в регистрах """
        self.canvas.delete("dynamic_lines")

        # 1. Считываем байты регистров из нашей централизованной базы данных
        admux = adc_registers_data["ADMUX"].get("current_value", 0)
        adcsrc = adc_registers_data["ADCSRC"].get("current_value", 0)
        dapcr = adc_registers_data["DAPCR"].get("current_value", 0)
        adcsra = adc_registers_data["ADCSRA"].get("current_value", 0)

        # 2. Выделяем управляющие биты
        chmux_val = admux & 0x1F          # Выбор канала (0-31)
        difs_val = (adcsrc >> 1) & 0x01   # Переключатель DIFS
        dap_en = (dapcr >> 7) & 0x01      # Включение усилителя DAPEN
        aden_val = (adcsra >> 7) & 0x01   # Питание ядра АЦП (ADEN)

        c_active = "#2ECC71"  # Ярко-зеленый (активный сигнальный тракт)

        # =========================================================================
        # ЛОГИКА 1: ВХОДНОЙ МУЛЬТИПЛЕКСОР (Всегда подсвечивает выбранный канал!)
        # =========================================================================
        # Базовый X начала — 0.0630, X конца — 0.2029.
        # Вы для ADC0 уже измерили точный Y = 0.1680.
        # Когда вы кликните по остальным каналам (ADC1, ADC2...), просто забейте их Y-координаты сюда:
        ch_y_coords = {
            0: 0.1697,
            1: 0.1924,
            2: 0.2174,
            3: 0.2414,
            4: 0.2650,
            5: 0.2892,
            6: 0.3131,
            7: 0.3370,
            8: 0.3608,
            9: 0.3847,
            10: 0.4086,
            11: 0.4330,
            12: 0.4857,
            13: 0.5099,
            14: 0.5342,
            15: 0.5571,
            16: 0.5820


            # ... и так далее для всех нужных каналов
        }


# Конец линии всегда упирается в синюю трапецию CHMUX
        x_end = 0.2029

        if chmux_val in ch_y_coords:
            target_y = ch_y_coords[chmux_val]

            # ЖЕСТКАЯ СХЕМОТЕХНИЧЕСКАЯ ЛОГИКА:
            # Если выбран внутренний сигнал (канал 12 и выше), сдвигаем начало линии вправо
            if chmux_val >= 12:
                x_start = 0.1318  # Линия короче, начинается ближе к мультиплексору
            else:
                x_start = 0.0720  # Базовые внешние пины ADC0-ADC11 от края окна

            # Рисуем активную входную трассу
            self.draw_rel_line(x_start, target_y, x_end, target_y, color=c_active, width=3.5)

            if chmux_val == 12:
                self.draw_rel_line(0.8787, 0.7955, 0.9507, 0.7955, color=c_active, width=3.5)
            if chmux_val == 13:
                self.draw_rel_line(0.9324, 0.8470, 0.9507, 0.8470, color=c_active, width=3.5)


        # =========================================================================
        # ЛОГИКА 2: ЗАТВОР ТРАНЗИСТОРА (КЛЮЧ ADEN СНИЗУ ЯДРА АЦП)
        # =========================================================================
        if aden_val == 1:
            # Снимите кликером точные координаты линии заземления (ключа) под блоком 12bit A/D!
            # Пока пропишем ориентировочные, чтобы прорисовать сплошную зеленую линию (замкнутый ключ)
            # Например, вертикальный отрезок, который «замыкает» транзистор на массу:
            self.draw_rel_line(0.8305, 0.4938, 0.8305, 0.6584, color=c_active, width=3.0)

            # -----------------------------------------------------------------
            # СИГНАЛ ИДЕТ ДАЛЬШЕ ТОЛЬКО ЕСЛИ ТРАНЗИСТОР ЗАМКНУТ (ADEN == 1)
            # -----------------------------------------------------------------
        if difs_val == 0:
                # Прямой путь от CHMUX в ядро АЦП
            self.draw_rel_line(0.2410, 0.3701, 0.6496, 0.3701, color=c_active, width=3.5)

        if difs_val == 1:
                # Путь через дифференциальный усилитель DAP
            self.draw_rel_line(0.6130, 0.4371, 0.6489, 0.4371, color=c_active, width=3.5)
            self.draw_rel_line(0.6116, 0.4359, 0.6116, 0.8276, color=c_active, width=3.5)
            self.draw_rel_line(0.5720, 0.8276, 0.6116, 0.8276, color=c_active, width=3.5)
        if dap_en == 1:
            self.draw_rel_line(0.5090, 0.8775, 0.5090, 1.0433, color=c_active, width=3.5)

        # =========================================================================
        # ВЫВОД ЗНАЧЕНИЯ ПРЕДДЕЛИТЕЛЯ НА СХЕМУ (Квадратик-индикатор)
        # =========================================================================
        # 1. Считываем биты предделителя
        adcsra_val = adc_registers_data["ADCSRA"].get("current_value", 0)
        ps_code = adcsra_val & 0x07  # Число от 0 до 7

        # 2. Определяем, где на экране сейчас должен быть нарисован квадратик
        # Мы используем те же относительные координаты. Подставьте ваши точные X и Y!
        box_x1 = self.offset_x + (0.7440 * (self.svg_orig_w * self.current_scale))
        box_y1 = self.offset_y + (0.3740 * (self.svg_orig_h * self.current_scale))
        box_x2 = self.offset_x + (0.7940 * (self.svg_orig_w * self.current_scale))
        box_y2 = self.offset_y + (0.4240 * (self.svg_orig_h * self.current_scale))

        # 3. Рисуем аккуратный прямоугольник поверх вектора (например, серый с черной рамкой)
        self.canvas.create_rectangle(box_x1, box_y1, box_x2, box_y2, fill="#F2F4F4", outline="#34495E", width=2, tags="dynamic_lines")

        # 4. Пишем по центру текст коэффициента или просто код (например, "DIV: 128" или просто код "Код: 7")
        # Вы можете выводить сюда коэффициенты деления строками, так даже проще чем считать:
        factors = ["/2", "/2", "/4", "/8", "/16", "/32", "/64", "/128"]
        display_text = factors[ps_code]

        center_x = (box_x1 + box_x2) / 2
        center_y = (box_y1 + box_y2) / 2
        self.canvas.create_text(center_x, center_y, text=display_text, fill="black", font=("Arial", 10, "bold"), tags="dynamic_lines")

        # =========================================================================
        # ВЫВОД ЗНАЧЕНИЯ МНОЖИТЕЛЯ УСИЛЕНИЯ НА СХЕМУ (Квадратик-индикатор)
        # =========================================================================
        # 1. Считываем биты GA1 и GA0 из регистра DAPCR
        dapcr_val = adc_registers_data["DAPCR"].get("current_value", 0)
        gain_code = (dapcr_val >> 5) & 0x03  # Получаем число от 0 до 3

        # 2. Вычисляем пиксельные координаты по вашей относительной сетке
        # Используем ширину зоны 0.0600 и высоту 0.0500 для идеальных пропорций
        g_box_x1 = self.offset_x + (0.4833 * (self.svg_orig_w * self.current_scale))
        g_box_y1 = self.offset_y + (0.8017 * (self.svg_orig_h * self.current_scale))
        g_box_x2 = self.offset_x + ((0.4833 + 0.0600) * (self.svg_orig_w * self.current_scale))
        g_box_y2 = self.offset_y + ((0.8017 + 0.0500) * (self.svg_orig_h * self.current_scale))

        # 3. Рисуем прямоугольник поверх вектора (нежно-серый с рамкой)
        self.canvas.create_rectangle(g_box_x1, g_box_y1, g_box_x2, g_box_y2, fill="#F2F4F4", outline="#2C3E50", width=2, tags="dynamic_lines")

        # 4. Сопоставляем код с реальными множителями из даташита
        gain_factors = ["x1", "x8", "x16", "x32"]
        display_gain = gain_factors[gain_code]

        g_center_x = (g_box_x1 + g_box_x2) / 2
        g_center_y = (g_box_y1 + g_box_y2) / 2

        # Выводим надпись по центру (например: "x16")
        self.canvas.create_text(g_center_x, g_center_y, text=display_gain, fill="black", font=("Arial", 10, "bold"), tags="dynamic_lines")

         # =========================================================================
        # ЛОГИКА 3: ПОДСВЕТКА ЛИНИЙ ОПОРНОГО НАПРЯЖЕНИЯ (Битовый сквозной код)
        # =========================================================================
        # 1. Достаем биты REFS[1:0] из ADMUX (сдвигаем биты 7:6 на шаг вправо)
        refs_1_0 = (admux >> 6) & 0x03

        # 2. Достаем бит REFS2 из ADCSRD (бит 6) и сдвигаем его так, чтобы он стал 3-м битом (маска 4)
        adcsrd_val = adc_registers_data["ADCSRD"].get("current_value", 0)
        refs2 = (adcsrd_val >> 4) & 0x04  # Сдвиг на 4 позиции превратит 6-й бит в значение 4 (или 0)

        # 3. Собираем монолитное бинарное число! (Результат от 0 до 7)
        refs_val = refs2 | refs_1_0

        # Теперь refs_val принимает строго даташитные комбинации:
        # 0 (0b000) -> Внешний пин AREF
        # 1 (0b001) -> Питание AVCC
        # 2 (0b010) -> Внутренний ИОН 2.048V
        # 3 (0b011) -> Внутренний ИОН 1.024V (по твоей логике это refs_val == 4, если нужно оставить 4 - поменяем)
        # 4 (0b100) -> Внутренний ИОН 4.096V (REFS2=1, REFS[1:0]=00)

        # Подстраиваем ветвление под собранный битовый код:
        if refs_val == 1:    # Выбрано питание VCC
            self.draw_rel_line(0.6094, 0.0114, 0.8591, 0.0102, color=c_active, width=3.5)
            self.draw_rel_line(0.8591, 0.0102, 0.8591, 0.1487, color=c_active, width=3.5)

        elif refs_val == 0:  # Выбрана внешняя ножка AVREF
            self.draw_rel_line(0.6094, 0.0534, 0.8305, 0.0534, color=c_active, width=3.5)
            self.draw_rel_line(0.8305, 0.0534, 0.8305, 0.1487, color=c_active, width=3.5)

        elif refs_val == 2:  # Внутренний 2.048V (0b010)
            self.draw_rel_line(0.6452, 0.0988, 0.8027, 0.0988, color=c_active, width=3.5)
            self.draw_rel_line(0.8027, 0.0988, 0.8027, 0.1487, color=c_active, width=3.5)

        elif refs_val == 3:  # Внутренний 1.024V (0b011)
            self.draw_rel_line(0.6452, 0.0988, 0.8027, 0.0988, color=c_active, width=3.5)
            self.draw_rel_line(0.8027, 0.0988, 0.8027, 0.1487, color=c_active, width=3.5)

        elif refs_val == 4:  # Внутренний 4.096V (0b100)
            self.draw_rel_line(0.6452, 0.0988, 0.8027, 0.0988, color=c_active, width=3.5)
            self.draw_rel_line(0.8027, 0.0988, 0.8027, 0.1487, color=c_active, width=3.5)

        # =========================================================================
        # ВЫВОД ИНФОРМАЦИИ НА ТАБЛО С УМНОЙ ПОДСВЕТКОЙ СВЕРКИ
        # =========================================================================
        admux_val = adc_registers_data["ADMUX"].get("current_value", 0)
        adcsrd_val = adc_registers_data["ADCSRD"].get("current_value", 0)
        vcal_now = adc_registers_data["VCAL"].get("current_value", 0)

        # Вычисляем, какой ИОН реально выбран мультиплексором
        r_1_0 = (admux_val >> 6) & 0x03
        r2 = (adcsrd_val >> 4) & 0x04
        skvoznoi_refs = r2 | r_1_0

        # Вытаскиваем эталонные константы из базы для проверки соответствия
        vcal1_ref = adc_registers_data.get("VCAL1", {}).get("current_value", 0x00)
        vcal2_ref = adc_registers_data.get("VCAL2", {}).get("current_value", 0x4A)
        vcal3_ref = adc_registers_data.get("VCAL3", {}).get("current_value", 0x8F)

        # Определяем базовый цвет фона табло (по умолчанию белый/нейтральный)
        bg_color = "#FBFCFC"
        is_mismatch = False

        # Логика сверки: проверяем соответствие физического ИОН и загруженной константы
        if skvoznoi_refs == 3:  # На мультиплексоре ИОН 1.024V
            display_text = f"ИОН: 1.024V\nVCAL: 0x{vcal_now:02X}"
            if vcal_now != vcal1_ref: is_mismatch = True
        elif skvoznoi_refs == 2:  # На мультиплексоре ИОН 2.048V
            display_text = f"ИОН: 2.048V\nVCAL: 0x{vcal_now:02X}"
            if vcal_now != vcal2_ref: is_mismatch = True
        elif skvoznoi_refs == 4:  # На мультиплексоре ИОН 4.096V
            display_text = f"ИОН: 4.096V\nVCAL: 0x{vcal_now:02X}"
            if vcal_now != vcal3_ref: is_mismatch = True
        elif skvoznoi_refs == 0:
            display_text = "Вход:\nAREF"
        elif skvoznoi_refs == 1:
            display_text = "Вход:\nAVCC"
        else:
            display_text = "ИОН:\nНеизв."

        # Если обнаружено несовпадение — подсвечиваем табло светло-красным алармом!
        if is_mismatch:
            bg_color = "#FADBD8"  # Мягкий красный инжиниринговый аларм
            display_text += "\n⚠️ МИСМАТЧ!"
        elif skvoznoi_refs in[2, 3, 4]:
            bg_color = "#EAFAF1"  # Мягкий зеленый — всё откалибровано верно!

        # Отрисовка табло
        box_x1 = self.offset_x + (0.9200 * (self.svg_orig_w * self.current_scale))
        box_y1 = self.offset_y + (0.0200 * (self.svg_orig_h * self.current_scale))
        box_x2 = self.offset_x + (1.0100 * (self.svg_orig_w * self.current_scale))
        box_y2 = self.offset_y + (0.0900 * (self.svg_orig_h * self.current_scale))

        # Рисуем рамку и заливаем вычисленным цветом bg_color
        self.canvas.create_rectangle(box_x1, box_y1, box_x2, box_y2, fill=bg_color, outline="#1B4F72", width=2, tags="dynamic_lines")

        cx = (box_x1 + box_x2) / 2
        cy = (box_y1 + box_y2) / 2
        self.canvas.create_text(cx, cy, text=display_text, fill="black", font=("Arial", 9, "bold"), justify=tk.CENTER, tags="dynamic_lines")

        # =========================================================================
        # ОТРЕСОВКА ИНДИКАТОРОВ DIDR (Скругленные пины для всех 12 внешних входов)
        # =========================================================================
        # Твоя прецизионная ручная сетка по оси Y для всех 12 внешних каналов
        didr_y_coords = {
            0: 0.1697, 1: 0.1924, 2: 0.2174, 3: 0.2414,
            4: 0.2650, 5: 0.2892, 6: 0.3131, 7: 0.3370,
            8: 0.3608, 9: 0.3847, 10: 0.4086, 11: 0.4330
        }

        # Карта соответствия: Номер канала ADC -> (Имя регистра, Бит в регистре)
        didr_mapping = {
            0:  ("DIDR0", 0), 1: ("DIDR0", 1), 2: ("DIDR0", 2), 3: ("DIDR0", 3),
            4:  ("DIDR0", 4), 5: ("DIDR0", 5), 6: ("DIDR0", 6), 7: ("DIDR0", 7),
            8:  ("DIDR1", 2), 9: ("DIDR1", 3), 10: ("DIDR1", 6), 11: ("DIDR1", 7)
        }

        # Вытаскиваем состояние каждого канала в удобный словарь цветов, чтобы не читать регистры по сто раз
        ch_colors = {}
        for ch, (reg_name, bit_pos) in didr_mapping.items():
            reg_value = adc_registers_data[reg_name].get("current_value", 0)
            is_disabled = (reg_value >> bit_pos) & 0x01
            ch_colors[ch] = "#2ECC71" if is_disabled else "#E74C3C"

        # Отрисовка базовых пинов DIDR на входе
        pin_x = 0.0630
        for ch, pin_y in didr_y_coords.items():
            self.draw_rel_pin(pin_x, pin_y, w_len=14, h_thick=6, color=ch_colors[ch])


        # =========================================================================
        # СИНХРОННАЯ ОТРЕСОВКА ДОПОЛНИТЕЛЬНЫХ ПИНОВ ОУ (DAP) И ДЕЛИТЕЛЯ (VDS)
        # =========================================================================
        # --- ВХОДЫ ОУ (DAP): Полностью синхронны со своими базовыми аналоговыми пинами ---
        self.draw_rel_pin(0.0681, 0.6879, w_len=14, h_thick=6, color=ch_colors[0])  # APP0 делит ногу с ADC0
        self.draw_rel_pin(0.0666, 0.7186, w_len=14, h_thick=6, color=ch_colors[1])  # APP1 делит ногу с ADC1

        self.draw_rel_pin(0.0674, 0.8412, w_len=14, h_thick=6, color=ch_colors[2])  # APN0 делит ногу с ADC2
        self.draw_rel_pin(0.0681, 0.8662, w_len=14, h_thick=6, color=ch_colors[3])  # APN1 делит ногу с ADC3
        self.draw_rel_pin(0.0674, 0.8900, w_len=14, h_thick=6, color=ch_colors[8])  # APN2 делит ногу с ADC8
        self.draw_rel_pin(0.0666, 0.9093, w_len=14, h_thick=6, color=ch_colors[9])  # APN3 делит ногу с ADC9

        # На ножке PE0 (куда заведен APN4) нет АЦП, но в DIDR1 есть бит 0 (PE0D). Снимем состояние с него для индикатора
        pe0_disabled = (adc_registers_data["DIDR1"].get("current_value", 0) >> 0) & 0x01
        c_pe0 = "#2ECC71" if pe0_disabled else "#E74C3C"
        self.draw_rel_pin(0.0666, 0.9286, w_len=14, h_thick=6, color=c_pe0)  # APN4 на порту PE0

        # --- ВХОДЫ ДЕЛИТЕЛЯ НАПРЯЖЕНИЯ (VDS): Полностью синхронны со своими каналами ---
        self.draw_rel_pin(0.7383, 0.7981, w_len=14, h_thick=6, color=ch_colors[0])  # Вход от ADC0
        self.draw_rel_pin(0.7383, 0.8208, w_len=14, h_thick=6, color=ch_colors[1])  # Вход от ADC1
        self.draw_rel_pin(0.7390, 0.8423, w_len=14, h_thick=6, color=ch_colors[4])  # Вход от ADC4
        self.draw_rel_pin(0.7375, 0.8616, w_len=14, h_thick=6, color=ch_colors[5])  # Вход от ADC5
        self.draw_rel_pin(0.7390, 0.8832, w_len=14, h_thick=6, color=ch_colors[10]) # Вход от AVREF (Пин ADC10)

        # --- КОММУТАТОР ВХОДОВ ОПОРНОГО НАПРЯЖЕНИЯ ---
        # Точка AVREF на коммутаторе загорается синхронно с состоянием пина ADC10 (где сидит внешняя опора)
        self.draw_rel_pin(0.5991, 0.0545, w_len=12, h_thick=6, color=ch_colors[10])

        # =========================================================================
        # ЛОГИКА ТРАКТА: ПОЛОЖИТЕЛЬНЫЙ ВХОД ДИФФЕРЕНЦИАЛЬНОГО УСИЛИТЕЛЯ (DAP +)
        # =========================================================================
        dapcr_val = adc_registers_data["DAPCR"].get("current_value", 0)
        dps_code = dapcr_val & 0x03

        x_start_pins = 0.0779
        x_end_mux = 0.3415
        c_green = "#2ECC71"

        # Если выбран код 00 (ADMUXO), рисуем строго перпендикулярную змейку-магистраль
        if dps_code == 0:
            self.draw_rel_line(0.3420, 0.6664, 0.2856, 0.6664, color=c_green, width=3.5)
            self.draw_rel_line(0.2856, 0.6664, 0.2856, 0.3724, color=c_green, width=3.5)
            self.draw_rel_line(0.2856, 0.3724, 0.2410, 0.3724, color=c_green, width=3.5)

        if dps_code == 1:
            self.draw_rel_line(x_start_pins, 0.6887, x_end_mux, 0.6887, color=c_green, width=3.5)

        if dps_code == 2:
            self.draw_rel_line(x_start_pins, 0.7166, x_end_mux, 0.7166, color=c_green, width=3.5)

        if dps_code == 3:
            self.draw_rel_line(x_end_mux, 0.7429, 0.3205, 0.7429, color=c_green, width=3.5)
            self.draw_rel_line(0.3205, 0.7429, 0.3205, 0.7677, color=c_green, width=3.5)


        # =========================================================================
        # ЛОГИКА ТРАКТА: ОТРИЦАТЕЛЬНЫЙ ВХОД ДИФФЕРЕНЦИАЛЬНОГО УСИЛИТЕЛЯ (DAP -)
        # =========================================================================
        # Выделяем биты DNS[2:0] (биты 4, 3, 2 в DAPCR)
        dns_code = (dapcr_val >> 2) & 0x07

        x_start_opn = 0.0779
        x_end_opn_mux = 0.3415
        c_green = "#2ECC71"

        # Рисуем строго те линии, условия которых совпали прямо сейчас
        if dns_code == 0:  # APN0 (ADC2)
            self.draw_rel_line(x_start_opn, 0.8412, x_end_opn_mux, 0.8412, color=c_green, width=3.5)

        if dns_code == 1:  # APN1 (ADC3)
            self.draw_rel_line(x_start_opn, 0.8662, x_end_opn_mux, 0.8662, color=c_green, width=3.5)

        if dns_code == 2:  # APN2 (ADC8)
            self.draw_rel_line(x_start_opn, 0.8900, x_end_opn_mux, 0.8900, color=c_green, width=3.5)

        if dns_code == 3:  # APN3 (ADC9)
            self.draw_rel_line(x_start_opn, 0.9093, x_end_opn_mux, 0.9093, color=c_green, width=3.5)

        if dns_code == 4:  # APN4 (PE0)
            self.draw_rel_line(x_start_opn, 0.9286, x_end_opn_mux, 0.9286, color=c_green, width=3.5)

        if dns_code == 5:  # Выходная перпендикулярная змейка-магистраль к CHMUX
            self.draw_rel_line(0.3428, 0.9525, 0.2856, 0.9525, color=c_green, width=3.5)
            self.draw_rel_line(0.2856, 0.9525, 0.2856, 0.3712, color=c_green, width=3.5)
            self.draw_rel_line(0.2856, 0.3712, 0.2417, 0.3712, color=c_green, width=3.5)

        if dns_code == 6:  # Линия перпендикулярного заземления (масса)
            self.draw_rel_line(0.3428, 0.9763, 0.3215, 0.9763, color=c_green, width=3.5)
            self.draw_rel_line(0.3215, 0.9763, 0.3215, 0.9956, color=c_green, width=3.5)

        # =========================================================================
        # ЛОГИКА ТРАКТА: МУЛЬТИПЛЕКСОР ДЕЛИТЕЛЯ НАПРЯЖЕНИЯ (VDS)
        # =========================================================================
        # Выделяем младшие биты VDS[2:0] (биты 2, 1, 0 в регистре ADCSRD)
        adcsrd_val = adc_registers_data["ADCSRD"].get("current_value", 0)
        vds_code = adcsrd_val & 0x07

        x_start_vds = 0.7471
        x_end_vds_mux = 0.8034
        c_green = "#2ECC71"

        # Рисуем горизонтальную линию строго для того входа, который выбран в регистре
        if vds_code == 1:
            self.draw_rel_line(x_start_vds, 0.7981, x_end_vds_mux, 0.7981, color=c_green, width=3.5)

        if vds_code == 2:
            self.draw_rel_line(x_start_vds, 0.8208, x_end_vds_mux, 0.8208, color=c_green, width=3.5)

        if vds_code == 3:
            self.draw_rel_line(x_start_vds, 0.8423, x_end_vds_mux, 0.8423, color=c_green, width=3.5)

        if vds_code == 4:
            self.draw_rel_line(x_start_vds, 0.8616, x_end_vds_mux, 0.8616, color=c_green, width=3.5)

        if vds_code == 5:
            self.draw_rel_line(x_start_vds, 0.8832, x_end_vds_mux, 0.8832, color=c_green, width=3.5)

        if vds_code == 6:
            self.draw_rel_line(x_start_vds, 0.9025, x_end_vds_mux, 0.9025, color=c_green, width=3.5)


###################################################################################################################
        # Поднимаем все зеленые трассы над векторной картинкой
        self.canvas.tag_raise("dynamic_lines")
        self.after(250, self.update_schematic)
