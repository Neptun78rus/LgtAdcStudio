import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import collections
import random
import time
import math
import adc_database
import adc_schematic
import adc_chart
from adc_database import adc_registers_data
from adc_schematic import SchematicWindow
from adc_chart import AdcChartWindow




from adc_database import adc_registers_data

# Глубокая инициализация структуры: добавляем динамические состояния для регистров и каждого бита
for reg_name, reg_data in adc_registers_data.items():
    # 1. Задаем общее начальное значение регистра из дефолтного
    reg_data["current_value"] = int(reg_data["default"], 16)

    # 2. Проходим по каждому биту и выставляем его начальное состояние (0 или 1)
    # Нам нужно сопоставить биты из списка (они идут от 7 к 0) с битовой маской
    for idx, bit_pos in enumerate(range(7, -1, -1)):
        if idx < len(reg_data["bits"]):
            # Выделяем конкретный бит из дефолтного байта
            initial_bit_state = (reg_data["current_value"] >> bit_pos) & 1
            reg_data["bits"][idx]["state"] = initial_bit_state


# ==========================================
# 2. МНОГОПОТОЧНЫЙ ДРАЙВЕР UART (SERIAL)
# ==========================================
class SerialWorker(threading.Thread):
    def __init__(self, port, baudrate, gui_queue, demo_mode=False):
        super().__init__(daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.queue = gui_queue
        self.demo_mode = demo_mode
        self.running = True
        self.demo_streaming = False  # Флаг гона данных
        self.ser = None
        self.sim_t = 0.0

    def run(self):
        if self.demo_mode:
            while self.running:
                time.sleep(0.01) # Шаг эмулятора 10мс (~100 Гц)
                if self.demo_streaming:
                    self.sim_t += 0.05
                    # Генерируем чистую синусоиду (12 бит: от 0 до 4095)
                    base_signal = 2048 + 1500 * math.sin(self.sim_t)
                    adc_val = int(base_signal + random.randint(-20, 20))
                    adc_val = max(0, min(4095, adc_val))

                    # Прямой перевод числа в 2 сырых байта (как из UART)
                    payload = adc_val.to_bytes(2, byteorder='big')
                    self.queue.put({"type": 0x03, "data": payload})
            return

        # Реальный UART (если demo_mode = False)
        try:
            import serial
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.05)
            while self.running:
                if self.ser.in_waiting >= 3:
                    marker = self.ser.read(1)
                    if marker != b'\xAA': continue
                    p_type = int.from_bytes(self.ser.read(1), 'big')
                    length = int.from_bytes(self.ser.read(1), 'big')
                    payload = self.ser.read(length)
                    self.queue.put({"type": p_type, "data": payload})
        except Exception as e:
            self.queue.put({"type": "ERROR", "message": str(e)})

    def send_packet(self, p_type, data_bytes):
        """Прямая отправка команды"""
        if self.demo_mode:
            if p_type == 0x04:  # Управление режимом АЦП
                mode = data_bytes[0] # Берем код режима напрямую из байта
                if mode == 2:    # Старт непрерывного вывода
                    self.demo_streaming = True
                elif mode == 0:  # Стоп поток
                    self.demo_streaming = False
                elif mode == 1:  # Одиночный выстрел
                    val = random.randint(1000, 3000)
                    self.queue.put({"type": 0x03, "data": val.to_bytes(2, 'big')})
            return

        if self.ser and self.ser.is_open:
            packet = b'\xAA' + bytes([p_type, len(data_bytes)]) + data_bytes
            self.ser.write(packet)

    def stop(self):
        self.running = False
        self.demo_streaming = False

# ==========================================
# 5. ГЛАВНОЕ ОКНО ПРИЛОЖЕНИЯ (КАРКАС)
# ==========================================
class MainWindow(tk.Tk):
    def request_hardware_sync(self):
        """ Отправляет в МК запрос на выгрузку всех калибровочных и управляющих регистров """
        if self.worker and self.worker.is_alive():
            print("Шлем запрос синхронизации регистров в МК...")
            # Отправляем пакет типа 0x02. В качестве данных шлем байт 0xFF (флаг общего запроса)
            self.worker.send_packet(0x02, bytes([0xFF]))
        else:
            messagebox.showwarning("Ошибка связи", "Сначала откройте COM-порт микроконтроллера!")

    def refresh_com_ports(self):
        """ Автоматически сканирует систему на наличие доступных tty/COM портов """
        try:
            import serial.tools.list_ports
            # Получаем список всех активных портов в ОС
            ports = serial.tools.list_ports.comports()

            # Выдергиваем только их имена (например, '/dev/ttyACM0' или 'COM3')
            port_names = [port.device for port in ports]

            # Если портов в системе нет, добавляем дефолтные для удобства
            if not port_names:
                port_names = ["COM3", "/dev/ttyACM0", "/dev/ttyUSB0"]

            # Обновляем список вариантов в выпадающем меню интерфейса
            self.port_combo['values'] = port_names

            # Автоматически выбираем первый найденный порт в списке
            self.port_combo.current(0)
        except Exception as e:
            print(f"Ошибка сканирования портов: {e}")

    def __init__(self):
        super().__init__()
        self.title("Панель инженерии АЦП")
        self.geometry("900x500")

        self.gui_queue = queue.Queue()
        self.worker = None

        self.setup_menu()
        self.setup_ui()
        self.poll_queue()

    def setup_menu(self):
        menubar = tk.Menu(self)
        # Меню Окна
        windows_menu = tk.Menu(menubar, tearoff=0)
        windows_menu.add_command(label="Открыть схему связей", command=self.open_schematic)
        windows_menu.add_command(label="Открыть график осциллографа", command=self.open_chart)
        menubar.add_cascade(label="Окна визуализации", menu=windows_menu)
        self.config(menu=menubar)

    def setup_ui(self):
        # --- Верхняя панель: Подключение к UART ---
        conn_frame = ttk.LabelFrame(self, text=" Настройки подключения UART ")
        conn_frame.pack(fill=tk.X, padx=10, pady=5)


                # --- БЛОК НАСТРОЕК UART (Заменяем старый Entry на Combobox) ---
        ttk.Label(conn_frame, text="Порт:").pack(side=tk.LEFT, padx=5)

        # Создаем выпадающий список вместо обычного текстового поля
        self.port_combo = ttk.Combobox(conn_frame, width=15, state="readonly")
        self.port_combo.pack(side=tk.LEFT, padx=5)

        # Кнопка для ручного пересканирования (если плату перевоткнули в USB)
        self.btn_refresh_ports = ttk.Button(conn_frame, text="🔄", width=3, command=self.refresh_com_ports)
        self.btn_refresh_ports.pack(side=tk.LEFT, padx=2)

        # Запускаем первичный поиск портов при старте окна
        self.refresh_com_ports()
        # --- Добавляем кнопку Синхронизации в панель подключения ---
        self.btn_sync = ttk.Button(conn_frame, text="🔄 Синхронизация", state=tk.DISABLED, command=self.request_hardware_sync)
        self.btn_sync.pack(side=tk.LEFT, padx=10)


        self.demo_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(conn_frame, text="Демо-эмуляция (без МК)", variable=self.demo_var).pack(side=tk.LEFT, padx=15)

        self.btn_start = ttk.Button(conn_frame, text="Запуск Порта", command=self.start_serial)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        self.btn_stop = ttk.Button(conn_frame, text="Остановка Порта", command=self.stop_serial, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5)


        # --- Средняя панель: Управление режимами АЦП ---
        adc_frame = ttk.LabelFrame(self, text=" Управление режимами преобразования АЦП ")
        adc_frame.pack(fill=tk.X, padx=10, pady=5)

        self.btn_single = ttk.Button(adc_frame, text="Одиночное преобразование", command=lambda: self.set_adc_mode(1), state=tk.DISABLED)
        self.btn_single.pack(side=tk.LEFT, padx=5, pady=5)

        self.btn_cont = ttk.Button(adc_frame, text="Старт непрерывного вывода", command=lambda: self.set_adc_mode(2), state=tk.DISABLED)
        self.btn_cont.pack(side=tk.LEFT, padx=5, pady=5)

        self.btn_stop_adc = ttk.Button(adc_frame, text="Стоп поток", command=lambda: self.set_adc_mode(0), state=tk.DISABLED)
        self.btn_stop_adc.pack(side=tk.LEFT, padx=5, pady=5)

        # --- Нижняя часть: Таблица регистров ---
        table_frame = ttk.LabelFrame(self, text=" Регистры конфигурации АЦП ")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("name", "address", "val_hex", "val_bin", "description")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.tree.heading("name", text="Имя")
        self.tree.heading("address", text="Адрес")
        self.tree.heading("val_hex", text="Значение (HEX)")
        self.tree.heading("val_bin", text="Значение (БИНАРНОЕ)")
        self.tree.heading("description", text="Описание конфигурации")

        self.tree.column("name", width=90, anchor="center")
        self.tree.column("address", width=70, anchor="center")
        self.tree.column("val_hex", width=110, anchor="center")
        self.tree.column("val_bin", width=160, anchor="center")
        self.tree.column("description", width=400, anchor="w")

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.update_table_view()

        # Интерактив: двойной клик для изменения регистра/битов
        self.tree.bind("<Double-1>", self.on_register_double_click)

    def update_table_view(self):
        """Перерисовывает строки таблицы на основе единой структуры данных"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        for name, data in adc_registers_data.items():
            val = data["current_value"]  # Читаем из единой структуры
            hex_str = f"0x{val:02X}"
            bin_str = f"{val:08b}"
            self.tree.insert("", tk.END, values=(name, data["address"], hex_str, bin_str, data["description"]))

    def on_register_double_click(self, event):
        """Открывает подтаблицу редактирования отдельных битов при двойном клике"""
        item = self.tree.selection()
        if not item:
            return

        # БЕРЕМ ПЕРВЫЙ ЭЛЕМЕНТ [0] — это гарантированно будет чистое текстовое имя регистра, например, 'ADCH'
        values = self.tree.item(item)["values"]
        if not values:
            return
        reg_name = values[0]

        # Проверяем, есть ли регистр в базе данных
        if reg_name not in adc_registers_data:
            print(f"Ошибка: Регистр {reg_name} не найден в базе данных.")
            return

        # Теперь reg_info гарантированно определен!
        reg_info = adc_registers_data[reg_name]
        current_val = reg_info.get("current_value", 0)
        bits_list = reg_info.get("bits", [])

        # Создаем Toplevel окно редактирования 8 битов
        bit_win = tk.Toplevel(self)
        bit_win.title(f"Битовое редактирование: {reg_name}")
        bit_win.geometry("650x360")
        bit_win.transient(self)

        # Дожидаемся видимости окна, чтобы избежать ошибки TclError grab failed
        bit_win.wait_visibility()
        bit_win.grab_set()

        vars_list = []

        main_frame = ttk.Frame(bit_win, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Отрисовываем 8 бит от 7-го к 0-му
        for idx, bit_idx in enumerate(range(7, -1, -1)):
            frame = ttk.Frame(main_frame)
            frame.pack(fill=tk.X, padx=5, pady=4)

            # Получаем состояние бита в текущем байте
            bit_state = (current_val >> bit_idx) & 1
            var = tk.BooleanVar(value=bool(bit_state))
            vars_list.append(var)

            # Извлекаем имя, описание и тип конкретного бита из базы данных
            if idx < len(bits_list):
                b_name = bits_list[idx].get("name", f"BIT{bit_idx}")
                b_desc = bits_list[idx].get("desc", "")
                b_type = bits_list[idx].get("type", "R/W")
            else:
                b_name = f"BIT{bit_idx}"
                b_desc = "Зарезервировано"
                b_type = "R/W"

            # Чекбокс с именем бита (например, "Бит 7 [ADC11]")
            chk_text = f"Бит {bit_idx} [{b_name}]"

            # ШИРИНУ (width) нужно задавать здесь, при создании чекбокса:
            chk = ttk.Checkbutton(frame, text=chk_text, variable=var, width=15)

            # А в .pack() должны остаться только параметры размещения:
            chk.pack(side=tk.LEFT)


            # Защита: если бит только для чтения (тип "R"), отключаем чекбокс
            if b_type == "R":
                chk.config(state=tk.DISABLED)

            # Выводим текстовое описание бита из базы данных справа от чекбокса
            desc_label = ttk.Label(frame, text=f"—  {b_desc}", foreground="#444444", font=("Arial", 9))
            desc_label.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        def save_bits():
            new_val = 0
            for idx, var in enumerate(vars_list):
                bit_pos = 7 - idx
                bit_state = 1 if var.get() else 0

                # Записываем состояние конкретного бита в общую базу данных
                if idx < len(adc_registers_data[reg_name]["bits"]):
                    adc_registers_data[reg_name]["bits"][idx]["state"] = bit_state

                if bit_state:
                    new_val |= (1 << bit_pos)

            # Сохраняем общее значение регистра в базу
            adc_registers_data[reg_name]["current_value"] = new_val

            # Обновляем таблицу на главном экране
            self.update_table_view()

            # Отправка нового байта регистра по UART в МК (Тип пакета 0x01)
            if self.worker and self.worker.is_alive():
                addr = int(adc_registers_data[reg_name]["address"], 16)
                self.worker.send_packet(0x01, bytes([addr, new_val]))

            bit_win.destroy()

        # Кнопка сохранения в самом низу окна битов
        btn_save = ttk.Button(bit_win, text="Сохранить и Отправить в МК", command=save_bits)
        btn_save.pack(pady=10)

        def save_bits():
            new_val = 0
            for idx, var in enumerate(vars_list):
                bit_pos = 7 - idx
                bit_state = 1 if var.get() else 0

                # Записываем состояние конкретного бита в базу данных
                if idx < len(adc_registers_data[reg_name]["bits"]):
                    adc_registers_data[reg_name]["bits"][idx]["state"] = bit_state

                if bit_state:
                    new_val |= (1 << bit_pos)

            # Сохраняем общее значение регистра в базу
            adc_registers_data[reg_name]["current_value"] = new_val
            self.update_table_view()

            # Отправка по UART в МК
            if self.worker and self.worker.is_alive():
                addr = int(adc_registers_data[reg_name]["address"], 16)
                self.worker.send_packet(0x01, bytes([addr, new_val]))

            bit_win.destroy()

        # Кнопка сохранения в самом низу окна битов
        btn_save = ttk.Button(bit_win, text="Сохранить и Отправить в МК", command=save_bits)
        btn_save.pack(pady=10)


    # --- Управление потоками ---
    def start_serial(self):
        # Было: port = self.port_entry.get()
        # Стало: берем выбранную строчку из выпадающего списка
        port = self.port_combo.get()
        demo = self.demo_var.get()

        self.worker = SerialWorker(port, 115200, self.gui_queue, demo_mode=demo)
        self.worker.start()

        # ... остальной ваш код управления кнопками (config) без изменений ...


        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.btn_sync.config(state=tk.NORMAL)
        self.btn_single.config(state=tk.NORMAL)
        self.btn_cont.config(state=tk.NORMAL)
        self.btn_stop_adc.config(state=tk.NORMAL)

    def stop_serial(self):
        if self.worker:
            self.worker.stop()
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.btn_sync.config(state=tk.DISABLED)
        self.btn_single.config(state=tk.DISABLED)
        self.btn_cont.config(state=tk.DISABLED)
        self.btn_stop_adc.config(state=tk.DISABLED)

    def set_adc_mode(self, mode_id):
        """Отправляет команду изменения режима АЦП (Тип фрейма 0x04)"""
        if self.worker and self.worker.is_alive():
            self.worker.send_packet(0x04, bytes([mode_id]))

    def poll_queue(self):
        """Асинхронный разбор сырых данных из порта без посредников"""
        while not self.gui_queue.empty():
            msg = self.gui_queue.get()

            if msg["type"] == "ERROR":
                messagebox.showerror("Ошибка связи", msg["message"])
                self.stop_serial()

            elif msg["type"] == 0x03:  # СЫРЫЕ ДАННЫЕ АЦП (2 БАЙТА)
                # Переводим 2 байта напрямую в число 0-4095
                raw_val = int.from_bytes(msg["data"], byteorder='big')

                # Шлем напрямую в открытое окно осциллографа
                if hasattr(self, 'chart_window') and self.chart_window.winfo_exists():
                    self.chart_window.add_sample(raw_val)

            elif msg["type"] == 0x02:  # МК прислал данные регистра для синхронизации
                payload = msg["data"]  # Ожидаем 2 байта: [Адрес_Регистра, Значение_Регистра]
                if len(payload) >= 2:
                    reg_addr_hex = f"0x{payload[0]:02X}"
                    reg_val = payload[1]

                    # Бежим по всей нашей базе данных и ищем, какому регистру принадлежит этот адрес
                    found = False
                    for reg_name, reg_info in adc_registers_data.items():
                        if reg_info["address"].upper() == reg_addr_hex.upper():
                            # Нашли совпадение! Обновляем живое значение в базе
                            reg_info["current_value"] = reg_val

                            # Также обновляем внутренние флаги state для всех битов этого регистра
                            for idx, bit_info in enumerate(reg_info["bits"]):
                                # Считаем позицию бита (от 7 к 0)
                                bit_pos = 7 - idx
                                bit_info["state"] = (reg_val >> bit_pos) & 0x01

                            print(f" Синхронизирован регистр {reg_name} ({reg_addr_hex}) = 0x{reg_val:02X}")
                            found = True
                            break

                    if found:
                        # Принудительно перерисовываем главную таблицу Treeview
                        self.update_table_view()

                        # Если окно векторной схемы сейчас открыто, заставляем его тоже перерисовать зеленые линии!
                        if hasattr(self, 'schematic_window') and self.schematic_window.winfo_exists():
                            self.schematic_window.update_schematic()

        # Перевызов через 10мс (как прерывание)
        self.after(10, self.poll_queue)



    # --- Вызовы дополнительных окон ---
    def open_schematic(self):
        if not hasattr(self, 'schema_window') or not self.schema_window.winfo_exists():
            self.schema_window = SchematicWindow(self)
        else:
            self.schema_window.lift()

    def open_chart(self):
        if not hasattr(self, 'chart_window') or not self.chart_window.winfo_exists():
            self.chart_window = AdcChartWindow(self)
        else:
            self.chart_window.lift()

if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
