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

            # Сохраняем текущий выбранный канал CHMUX (младшие биты 4-0, маска 0x1F)
            # И сохраняем бит ADLAR (бит 5, маска 0x20)
            saved_lower_bits = current_admux & 0x3F

            # Выделяем старую опору и крутим по кругу: 0 -> 1 -> 2 -> 0
            current_refs = (current_admux >> 6) & 0x03
            new_refs = (current_refs + 1) % 3

            # Собираем новый байт: склеиваем новую опору и сохраненные младшие биты!
            new_admux = (new_refs << 6) | saved_lower_bits
            adc_registers_data["ADMUX"]["current_value"] = new_admux

            # Обновляем биты state для чекбоксов
            if len(adc_registers_data["ADMUX"]["bits"]) >= 2:
                if new_refs == 0:    # AREF
                    adc_registers_data["ADMUX"]["bits"][0]["state"] = 0
                    adc_registers_data["ADMUX"]["bits"][1]["state"] = 0
                elif new_refs == 1:  # AVCC
                    adc_registers_data["ADMUX"]["bits"][0]["state"] = 0
                    adc_registers_data["ADMUX"]["bits"][1]["state"] = 1
                elif new_refs == 2:  # Internal
                    adc_registers_data["ADMUX"]["bits"][0]["state"] = 1
                    adc_registers_data["ADMUX"]["bits"][1]["state"] = 0

            if hasattr(self.master, 'update_table_view'): self.master.update_table_view()
            if hasattr(self.master, 'worker') and self.master.worker and self.master.worker.is_alive():
                addr = int(adc_registers_data["ADMUX"]["address"], 16)
                self.master.worker.send_packet(0x01, bytes([addr, new_admux]))

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
        # 2. ИНТЕРАКТИВНЫЙ КЛИК ПО ТАБЛО ВНУТРЕННЕЙ ОПОРЫ (Квадратик с вольтажом)
        # =========================================================================
        if 0.7400 <= rel_x <= 0.8100 and 0.0200 <= rel_y <= 0.0900:
            current_admux = adc_registers_data["ADMUX"].get("current_value", 0)
            current_refs = (current_admux >> 6) & 0x03

            # Меняем вольтаж только если мультиплексор переключен на внутренний ИОН (код 2)
            if current_refs == 2:
                current_adcsrd = adc_registers_data["ADCSRD"].get("current_value", 0)

                if not hasattr(self, 'internal_ref_mode'):
                    self.internal_ref_mode = 0 # 0: 1.024V, 1: 2.048V, 2: 4.096V

                self.internal_ref_mode = (self.internal_ref_mode + 1) % 3

                # Жестко и явно выставляем биты в ADCSRD, чтобы таблица видела изменения!
                if self.internal_ref_mode == 0:     # 1.024V (REFS2 = 0)
                    new_adcsrd = (current_adcsrd & ~0x40)
                    vcal_default = int(adc_registers_data["VCAL"]["default"], 16)
                    adc_registers_data["VCAL"]["current_value"] = vcal_default
                elif self.internal_ref_mode == 1:   # 2.048V (Давайте для теста или по даташиту LGT временно поднимем другой бит, если нужно, но пока сбросим REFS2=0)
                    new_adcsrd = (current_adcsrd & ~0x40)
                    vcal2 = adc_registers_data["VCAL2"].get("current_value", 0x4A)
                    adc_registers_data["VCAL"]["current_value"] = vcal2
                elif self.internal_ref_mode == 2:   # 4.096V (REFS2 = 1)
                    new_adcsrd = (current_adcsrd | 0x40) # Взводим 6-й бит (маска 0x40)
                    vcal3 = adc_registers_data["VCAL3"].get("current_value", 0x8F)
                    adc_registers_data["VCAL"]["current_value"] = vcal3

                # КРИТИЧЕСКИ ВАЖНО: Записываем обновленное число в поле current_value
                adc_registers_data["ADCSRD"]["current_value"] = new_adcsrd

                # Обновляем состояние бита REFS2 (индекс 1 в массиве битов от 7 к 0)
                if len(adc_registers_data["ADCSRD"]["bits"]) >= 2:
                    adc_registers_data["ADCSRD"]["bits"][1]["state"] = (new_adcsrd >> 6) & 0x01

                # Принудительно заставляем главное окно полностью перерисовать Treeview
                if hasattr(self.master, 'update_table_view'):
                    self.master.update_table_view()

                # Шлем пакеты по UART в железный МК
                if hasattr(self.master, 'worker') and self.master.worker and self.master.worker.is_alive():
                    addr_asrd = int(adc_registers_data["ADCSRD"]["address"], 16)
                    addr_vcal = int(adc_registers_data["VCAL"]["address"], 16)
                    self.master.worker.send_packet(0x01, bytes([addr_asrd, new_adcsrd]))
                    self.master.worker.send_packet(0x01, bytes([addr_vcal, adc_registers_data["VCAL"]["current_value"]]))

                print(f" Изменен режим ИОН: {self.internal_ref_mode} (ADCSRD: 0x{new_adcsrd:02X}, VCAL: 0x{adc_registers_data['VCAL']['current_value']:02X})")
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
            0: 0.1680,  # Ваш проверенный Y для канала ADC0
            1: 0.1930,  # Примерное положение для ADC1 (подставьте свое из терминала)
            2: 0.2180,  # Примерное положение для ADC2
            3: 0.2429,
            4: 0.2668,
            5: 0.2918,
            6: 0.3133,
            7: 0.3372,
            8: 0.3610,
            9: 0.3871,
            10: 0.4075,
            11: 0.4325,
            12: 0.4847,
            13: 0.5109,
            14: 0.5336,
            15: 0.5574,
            16: 0.5812,

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
                x_start = 0.0630  # Базовые внешние пины ADC0-ADC11 от края окна

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
        # ЛОГИКА 3: ПОДСВЕТКА ЛИНИЙ ОПОРНОГО НАПРЯЖЕНИЯ (REFS[1:0])
        # =========================================================================
        # Читаем биты REFS из регистра ADMUX
        refs_val = (admux >> 6) & 0x03

        # Снимите кликером точные координаты трех входных стрелок над трапецией REFS!
        # Когда refs_val переключается, соответствующая дорожка загорится зеленым:
        if refs_val == 1:    # Выбрано питание VCC
            self.draw_rel_line(0.6094, 0.0114, 0.8591, 0.0102, color=c_active, width=3.5)
            self.draw_rel_line(0.8591, 0.0102, 0.8591, 0.1487, color=c_active, width=3.5)
            pass
        elif refs_val == 0:  # Выбрана внешняя ножка AVREF
            self.draw_rel_line(0.6094, 0.0534, 0.8305, 0.0534, color=c_active, width=3.5)
            self.draw_rel_line(0.8305, 0.0534, 0.8305, 0.1487, color=c_active, width=3.5)

            pass
        elif refs_val == 2:  # Выбрана внутренняя опора (Internal Reference)
            self.draw_rel_line(0.6452, 0.0988, 0.8027, 0.0988, color=c_active, width=3.5)
            self.draw_rel_line(0.8027, 0.0988, 0.8027, 0.1487, color=c_active, width=3.5)
            pass

        # =========================================================================
        # ВЫВОД ИНФОРМАЦИИ НА ТАБЛО ВНУТРЕННЕЙ ОПОРЫ
        # =========================================================================
        admux_val = adc_registers_data["ADMUX"].get("current_value", 0)
        refs_val = (admux_val >> 6) & 0x03  # Читаем направление из ADMUX
        vcal_now = adc_registers_data["VCAL"].get("current_value", 0)

        # Определяем текст для вывода на табло квадратика
        if refs_val == 0:
            display_text = "Вход:\nAREF"
        elif refs_val == 1:
            display_text = "Вход:\nAVCC"
        elif refs_val == 2:
            # Если выбрана внутренняя опора, текст зависит от текущего режима калибровки
            if not hasattr(self, 'internal_ref_mode'):
                self.internal_ref_mode = 0

            modes_labels = {0: "1.024V", 1: "2.048V", 2: "4.096V"}
            display_text = f"ИОН: {modes_labels[self.internal_ref_mode]}\nVCAL: 0x{vcal_now:02X}"

        # Рисуем квадратик-табло по вашим относительным координатам (например, X=0.7200, Y=0.0200)
        box_x1 = self.offset_x + (0.7200 * (self.svg_orig_w * self.current_scale))
        box_y1 = self.offset_y + (0.0200 * (self.svg_orig_h * self.current_scale))
        box_x2 = self.offset_x + (0.8000 * (self.svg_orig_w * self.current_scale))
        box_y2 = self.offset_y + (0.0900 * (self.svg_orig_h * self.current_scale))

        # Рисуем рамку табло
        self.canvas.create_rectangle(box_x1, box_y1, box_x2, box_y2, fill="#FBFCFC", outline="#1B4F72", width=2, tags="dynamic_lines")

        # Выводим текст по центру табло
        cx = (box_x1 + box_x2) / 2
        cy = (box_y1 + box_y2) / 2
        self.canvas.create_text(cx, cy, text=display_text, fill="black", font=("Arial", 9, "bold"), justify=tk.CENTER, tags="dynamic_lines")


        # Поднимаем все зеленые трассы над векторной картинкой
        self.canvas.tag_raise("dynamic_lines")
        self.after(250, self.update_schematic)
