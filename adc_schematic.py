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
        """Кликер автоматически переводит пиксели экрана в проценты от схемы (от 0.0 до 1.0)"""
        # Считаем положение клика относительно левого верхнего угла САМОЙ СХЕМЫ
        rel_x = (event.x - self.offset_x) / (self.svg_orig_w * self.current_scale)
        rel_y = (event.y - self.offset_y) / (self.svg_orig_h * self.current_scale)

        print(f"Относительные координаты для кода: {rel_x:.4f}, {rel_y:.4f}")

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
            # ... и так далее для всех нужных каналов
        }

        # Если текущий канал есть в нашей базе замеров, рисуем линию.
        # Она ВСЕГДА горит зеленым и просто меняет высоту при переключении CHMUX
        if chmux_val in ch_y_coords:
            target_y = ch_y_coords[chmux_val]
            self.draw_rel_line(0.0630, target_y, 0.2029, target_y, color=c_active, width=3.5)

        # =========================================================================
        # ЛОГИКА 2: ЦЕПИ ПОСЛЕ МУЛЬТИПЛЕКСОРА (Зависят от общего питания ядра ADEN)
        # =========================================================================
        if aden_val == 1:
            # Если выбран путь напрямую (DIFS == 0)
            if difs_val == 0:
            # 2. ТРАКТ ВЫХОДА: от CHMUX через DIFS в ядро 12bit A/D
            self.draw_rel_line(0.2402, 0.3712, 0.6496, 0.3712, color=c_active, width=3.5)

            # Финальный отрезок: заводим сигнал прямо в оранжевое ядро АЦП
            self.draw_rel_line(0.6753, 0.4041, 0.8291, 0.4041, color=c_active, width=3.5)

            # Если выбран путь через дифференциальный усилитель (DIFS == 1)
            elif difs_val == 1:
                if dap_en == 1:
                    # Сигнал уходит вниз в DAP и возвращается в АЦП
                    # (Сюда вы подставите новые относительные координаты для обхода)
                    pass

        # Поднимаем все зеленые трассы над векторной картинкой
        self.canvas.tag_raise("dynamic_lines")
        self.after(250, self.update_schematic)
