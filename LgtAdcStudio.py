import tkinter as tk
from tkinter import messagebox
import serial
import time

COM_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200

class LgtMuxPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("Интерактивный мультиплексор АЦП LGT8F328P")
        self.root.geometry("850x650") # Увеличили окно под все 17 входов
        self.root.configure(bg="#1e1e1e")

        # Список всех 17 входов мультиплексора согласно инструкции
        self.channels = [
            "ADC0", "ADC1", "ADC2", "ADC3", "ADC4", "ADC5",
            "ADC6", "ADC7", "ADC8", "ADC9", "ADC10", "ADC11",
            "4/5 x VDD", "1/5 x VDD", "IVREF", "GND", "DAO"
        ]
        self.active_channel_idx = 0 # По умолчанию выбран первый канал (ADC0)

        # Попытка открыть порт устройства
        try:
            self.ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
            time.sleep(1.5)
            print(f"[Успех] Порт {COM_PORT} открыт.")
        except Exception as e:
            self.ser = None
            messagebox.showwarning("Внимание ⚠️", f"Не удалось открыть порт {COM_PORT}.\nСкрипт запущен в режиме симуляции.\nОшибка: {e}")

        # Информационная панель
        self.info_label = tk.Label(self.root, text="Активный канал: ADC0 | Сырой отсчет: ----",
                                   font=("Courier", 14, "bold"), bg="#2d2d2d", fg="#00FF66", bd=2, relief="solid")
        self.info_label.pack(fill="x", padx=10, pady=10, ipady=8)

        # Холст для отрисовки большой схемы мультиплексора
        self.canvas = tk.Canvas(self.root, bg="#121212", highlightthickness=1, highlightbackground="#333333")
        self.canvas.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.draw_mux_schematic()

    def send_mux_cmd(self, index):
        """ Отправка индекса выбранного канала в порт """
        # В реальной прошивке это будет записываться в биты регистра управления каналами
        cmd_string = f"CHMUX={index}"
        if self.ser and self.ser.is_open:
            self.ser.write((cmd_string + "\n").encode())
            print(f"[Отправлено в МК]: {cmd_string} (Выбран {self.channels[index]})")
        else:
            print(f"[Симуляция]: {cmd_string} (Выбран {self.channels[index]})")

    def draw_mux_schematic(self):
        self.canvas.delete("all")

        # 1. Отрисовка трапеции мультиплексора (как на твоей схеме)
        # Координаты углов: верхний левый, верхний правый, нижний правый, нижний левый
        mux_poly = self.canvas.create_polygon(320, 40, 370, 70, 370, 560, 320, 590,
                                              fill="#1f385c", outline="#4a7ebb", width=2)

        # Подпись сверху шины управления
        self.canvas.create_line(345, 40, 345, 15, fill="#4a7ebb", width=2)
        self.canvas.create_line(345, 15, 250, 15, fill="#4a7ebb", width=2)
        self.canvas.create_text(200, 15, text="CHMUX[4:0]", fill="#4a7ebb", font=("Arial", 10, "bold"))

        # Выходной провод из мультиплексора в ядро АЦП
        self.canvas.create_line(370, 315, 480, 315, fill="#888888", width=3, arrow=tk.LAST)

        # Блок самого АЦП справа
        self.canvas.create_rectangle(480, 250, 640, 380, fill="#2d2d2d", outline="#BB86FC", width=2)
        self.canvas.create_text(560, 280, text="ЯДРО АЦП", fill="#FFFFFF", font=("Arial", 12, "bold"))
        self.canvas.create_text(560, 330, text="12-бит оцифровка\n(Регистр ADC)", fill="#BB86FC", font=("Arial", 9), justify=tk.CENTER)

        # 2. Отрисовка 17 входов слева
        start_y = 60
        spacing_y = 30 # Шаг между линиями входов

        for i, ch_name in enumerate(self.channels):
            current_y = start_y + (i * spacing_y)

            # Если канал активный - подсвечиваем его ярким цветом, иначе - тусклым серым
            is_active = (i == self.active_channel_idx)
            line_color = "#00FF66" if is_active else "#444444"
            text_color = "#00FF66" if is_active else "#888888"
            btn_color = "#00aa44" if is_active else "#252526"

            # Рисуем горизонтальную линию входа к мультиплексору
            self.canvas.create_line(180, current_y, 320, current_y, fill=line_color, width=2 if is_active else 1)

            # Маленький синий разъемчик на конце линии (как на схеме)
            self.canvas.create_rectangle(170, current_y-4, 180, current_y+4, fill="#4a7ebb", outline="")

            # Интерактивная кнопка-текст для выбора канала
            btn_id = self.canvas.create_rectangle(30, current_y-12, 160, current_y+12, fill=btn_color, outline="#333333")
            text_id = self.canvas.create_text(95, current_y, text=ch_name, fill="#FFFFFF" if not is_active else "#000000", font=("Arial", 9, "bold" if is_active else "normal"))

            # Привязываем клик мыши к кнопке канала
            # Использование дефолтных аргументов в lambda (ch_idx=i) критично, чтобы сохранялся правильный индекс!
            self.canvas.tag_bind(btn_id, "<Button-1>", lambda e, ch_idx=i: self.select_channel(ch_idx))
            self.canvas.tag_bind(text_id, "<Button-1>", lambda e, ch_idx=i: self.select_channel(ch_idx))

    def select_channel(self, idx):
        self.active_channel_idx = idx
        # Обновляем табло
        self.info_label.config(text=f"Активный канал: {self.channels[idx]} | Сырой отсчет: ----")
        # Отправляем команду переключения в МК
        self.send_mux_cmd(idx)
        # Перерисовываем схему, чтобы подсветить новую активную линию
        self.draw_mux_schematic()

if __name__ == "__main__":
    root = tk.Tk()
    app = LgtMuxPanel(root)
    root.mainloop()
