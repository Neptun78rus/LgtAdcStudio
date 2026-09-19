# FILE: adc_chart.py
import tkinter as tk
from tkinter import ttk
import collections

class AdcChartWindow(tk.Toplevel):
    def __init__(self, parent, max_points=150):
        super().__init__(parent)
        self.title("Осциллограф АЦП в реальном времени")
        self.geometry("700x380")

        self.max_points = max_points
        self.data_buffer = collections.deque(maxlen=self.max_points)

        self.canvas = tk.Canvas(self, bg="#111111", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.status_frame = ttk.Frame(self)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)
        self.value_label = ttk.Label(self.status_frame, text="Значение: --- (--- В)", font=("Arial", 10, "bold"))
        self.value_label.pack(side=tk.LEFT)

        self.canvas.bind("<Configure>", lambda e: self.redraw_chart())

    def add_sample(self, raw_value):
        self.data_buffer.append(raw_value)
        voltage = (raw_value / 4095.0) * 3.3
        self.value_label.config(text=f"Текущее значение: {raw_value} ({voltage:.3f} В)")
        self.redraw_chart()

    def redraw_chart(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 1 or h <= 1: return

        # Рисуем сетку уровней
        for text, ratio in [("4095", 0.05), ("2048", 0.5), ("0", 0.95)]:
            y = h * ratio
            self.canvas.create_line(50, y, w, y, fill="#252525", dash=(2, 2))
            self.canvas.create_text(25, y, text=text, fill="#666666", font=("Arial", 8))

        # Отрисовка кривой данных
        if len(self.data_buffer) < 2: return
        points = []
        x_step = (w - 50) / (self.max_points - 1)
        y_min, y_max = h * 0.95, h * 0.05
        y_range = y_min - y_max

        for i, val in enumerate(self.data_buffer):
            x = 50 + i * x_step
            y = y_min - (val / 4095.0) * y_range
            points.append((x, y))

        flat_points = [c for p in points for c in p]
        self.canvas.create_line(flat_points, fill="#00FF66", width=2, joinstyle=tk.ROUND)
