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
        self.root.geometry("850x680")
        self.root.configure(bg="#1e1e1e")

        self.channels = [
            "ADC0", "ADC1", "ADC2", "ADC3", "ADC4", "ADC5",
            "ADC6", "ADC7", "ADC8", "ADC9", "ADC10", "ADC11",
            "4/5 x VDD", "1/5 x VDD", "IVREF", "GND", "DAO"
        ]
        self.active_channel_idx = 0

        # Попытка открыть порт устройства
        try:
            self.ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=0.5)
            time.sleep(1.5)
            print(f"[Успех] Порт {COM_PORT} открыт.")
        except Exception as e:
            self.ser = None
            messagebox.showwarning("Внимание ⚠️", f"Не удалось открыть порт {COM_PORT}.\nСкрипт запущен в режиме симуляции.\nОшибка: {e}")

        # Информационная панель
        self.info_label = tk.Label(self.root, text="Канал: ADC0 | Выберите вход и нажмите ПУСК",
                                   font=("Courier", 14, "bold"), bg="#2d2d2d", fg="#00FF66", bd=2, relief="solid")
        self.info_label.pack(fill="x", padx=10, pady=10, ipady=8)

        # Большая кнопка запуска ручного замера АЦП внизу табло
        self.btn_trigger = tk.Button(self.root, text="⚡ ЗАПУСТИТЬ ПРЕОБРАЗОВАНИЕ АЦП (ОДИНОЧНЫЙ ЗАМЕР) ⚡",
                                     font=("Arial", 11, "bold"), bg="#FFB300", fg="#000000",
                                     activebackground="#B37700", activeforeground="#000000", bd=0,
                                     command=self.trigger_single_conversion)
        self.btn_trigger.pack(fill="x", padx=10, pady=(0, 10), ipady=8)

        # Холст для отрисовки большой схемы мультиплексора
        self.canvas = tk.Canvas(self.root, bg="#121212", highlightthickness=1, highlightbackground="#333333")
        self.canvas.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.draw_mux_schematic()

    def send_mux_cmd(self, index):
        """ Шаг 1: Просто настраиваем канал мультиплексора """
        cmd_string = f"CHMUX={index}"
        if self.ser and self.ser.is_open:
            self.ser.write((cmd_string + "\n").encode())
            print(f"[Отправлено в МК]: {cmd_string} (Настройка на {self.channels[index]})")

            # Сразу же считываем текстовый ответ-подтверждение от МК (наш ACK)
            rx_line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if rx_line:
                print(f"[Ответ МК]: {rx_line}")
                self.info_label.config(text=f"Канал настроен: {self.channels[index]} | {rx_line}")
        else:
            print(f"[Симуляция настройки]: {cmd_string}")

    def trigger_single_conversion(self):
        """ Шаг 2: Ручной пуск замера АЦП по кнопке """
        if self.ser and self.ser.is_open:
            print("[Python] Отправка команды ПУСК АЦП...")
            self.ser.write(b"START_ADC\n")

            # Ждем и считываем строго одну строчку ответа с результатом
            rx_line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if rx_line and rx_line.startswith("ADC:"):
                print(f"[Принят замер]: {rx_line}")
                try:
                    payload = rx_line.replace("ADC:", "")
                    adc_raw_str, admux_hex_str = payload.split(",")

                    adc_raw = int(adc_raw_str)
                    int_admux = int(admux_hex_str)

                    # Считаем милливольты для наглядности (при 5В питания)
                    millivolts = int((adc_raw / 4095.0) * 5000)
                    bin_pretty = f"{int_admux:08b}"
                    bin_pretty = f"{bin_pretty[:4]} {bin_pretty[4:]}"

                    ch_name = self.channels[self.active_channel_idx]
                    self.info_label.config(
                        text=f"Канал: {ch_name} | ЗАМЕР: {adc_raw:04d} ({millivolts} мВ) | ADMUX: 0x{int_admux:02X} [{bin_pretty}]"
                    )
                except Exception:
                    self.info_label.config(text=f"Ошибка разбора пакета: {rx_line}")
            else:
                self.info_label.config(text="Плата не ответила на запуск АЦП или пришел мусор")
        else:
            self.info_label.config(text="[Симуляция] Запуск АЦП: Замер равен 2048 (середина)")

    def draw_mux_schematic(self):
        self.canvas.delete("all")

        # Отрисовка трапеции мультиплексора
        self.canvas.create_polygon(320, 40, 370, 70, 370, 560, 320, 590, fill="#1f385c", outline="#4a7ebb", width=2)

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

        # Отрисовка 17 входов слева
        start_y = 60
        spacing_y = 30

        for i, ch_name in enumerate(self.channels):
            current_y = start_y + (i * spacing_y)
            is_active = (i == self.active_channel_idx)
            line_color = "#00FF66" if is_active else "#444444"
            btn_color = "#00aa44" if is_active else "#252526"

            self.canvas.create_line(180, current_y, 320, current_y, fill=line_color, width=2 if is_active else 1)
            self.canvas.create_rectangle(170, current_y-4, 180, current_y+4, fill="#4a7ebb", outline="")

            btn_id = self.canvas.create_rectangle(30, current_y-12, 160, current_y+12, fill=btn_color, outline="#333333")
            text_id = self.canvas.create_text(95, current_y, text=ch_name, fill="#FFFFFF" if not is_active else "#000000", font=("Arial", 9, "bold" if is_active else "normal"))

            self.canvas.tag_bind(btn_id, "<Button-1>", lambda e, ch_idx=i: self.select_channel(ch_idx))
            self.canvas.tag_bind(text_id, "<Button-1>", lambda e, ch_idx=i: self.select_channel(ch_idx))

    def select_channel(self, idx):
        self.active_channel_idx = idx
        self.send_mux_cmd(idx)
        self.draw_mux_schematic()

if __name__ == "__main__":
    root = tk.Tk()
    app = LgtMuxPanel(root)
    root.mainloop()
