import sys
import os
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import squarify
from shapely.geometry import Point


def load_region_polygon(geojson_path: str):
    gdf = gpd.read_file(geojson_path)
    region_poly = gdf.geometry.unary_union

    if region_poly.geom_type == "MultiPolygon":
        region_poly = max(region_poly.geoms, key=lambda p: p.area)

    return region_poly, gdf


def load_excel_data(excel_path: str):
    df = pd.read_excel(excel_path)

    cols = {c.strip().lower(): c for c in df.columns}
    if "district" not in cols:
        raise ValueError("В Excel нет колонки 'district'.")
    if "value" not in cols:
        raise ValueError("В Excel нет колонки 'value'.")

    col_district = cols["district"]
    col_value = cols["value"]

    data = df[[col_district, col_value]].copy()
    data.columns = ["district", "value"]

    data = data.dropna(subset=["district", "value"])
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    data = data.dropna(subset=["value"])

    if data.empty:
        raise ValueError("Нет валидных данных для построения Treemap.")

    return data.to_dict("records")


def pack_treemap_inside_region(values, labels, region_poly):
    minx, miny, maxx, maxy = region_poly.bounds
    width = maxx - minx
    height = maxy - miny

    rects = squarify.squarify(values, x=0, y=0, width=1, height=1)

    scaled_rects = []
    for r in rects:
        x = minx + r["x"] * width
        y = miny + r["y"] * height
        w = r["dx"] * width
        h = r["dy"] * height
        scaled_rects.append((x, y, w, h))

    valid_rects = []
    valid_labels = []
    for (x, y, w, h), label in zip(scaled_rects, labels):
        cx, cy = x + w / 2, y + h / 2
        point = Point(cx, cy)
        if region_poly.contains(point):
            valid_rects.append((x, y, w, h))
            valid_labels.append(label)

    return valid_rects, valid_labels


def plot_treemap_on_region(region_gdf, rects, labels, output_path):
    fig, ax = plt.subplots(figsize=(10, 8))
    region_gdf.plot(ax=ax, color="lightgray", edgecolor="black", linewidth=1.5)

    n = len(rects)
    if n == 0:
        plt.savefig(output_path, dpi=300)
        plt.close()
        return

    colors = plt.cm.Blues(np.linspace(0.4, 0.9, n))

    for (x, y, w, h), label, color_val in zip(rects, labels, colors):
        rect = plt.Rectangle((x, y), w, h, color=color_val, ec="white", linewidth=0.8)
        ax.add_patch(rect)
        ax.text(
            x + w / 2,
            y + h / 2,
            label,
            ha="center",
            va="center",
            fontsize=9,
            color="black",
            fontweight="bold",
            wrap=True,
        )

    ax.set_aspect("equal")
    ax.axis("off")
    plt.title("Treemap внутри контура региона")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


class TreemapApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Treemap в регионе (GUI)")
        self.root.geometry("500x350")

        self.map_path_var = tk.StringVar()
        self.data_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar(value="treemap_result.png")

        # Карта
        tk.Label(root, text="Файл карты (GeoJSON):").pack(anchor="w", padx=10, pady=(15, 5))
        frame_map = tk.Frame(root)
        frame_map.pack(fill="x", padx=10)
        tk.Entry(frame_map, textvariable=self.map_path_var, state="readonly", width=40).pack(side="left", fill="x", expand=True)
        tk.Button(frame_map, text="Выбрать", command=self.select_map).pack(side="left", padx=(10, 0))

        # Данные
        tk.Label(root, text="Файл данных (Excel):").pack(anchor="w", padx=10, pady=(15, 5))
        frame_data = tk.Frame(root)
        frame_data.pack(fill="x", padx=10)
        tk.Entry(frame_data, textvariable=self.data_path_var, state="readonly", width=40).pack(side="left", fill="x", expand=True)
        tk.Button(frame_data, text="Выбрать", command=self.select_data).pack(side="left", padx=(10, 0))

        # Выход
        tk.Label(root, text="Куда сохранить (PNG):").pack(anchor="w", padx=10, pady=(15, 5))
        frame_out = tk.Frame(root)
        frame_out.pack(fill="x", padx=10)
        tk.Entry(frame_out, textvariable=self.output_path_var, width=40).pack(side="left", fill="x", expand=True)
        tk.Button(frame_out, text="Папка", command=self.select_output_folder).pack(side="left", padx=(10, 0))

        # Кнопка запуска
        self.btn_run = tk.Button(root, text="Построить Treemap", command=self.run_treemap, bg="#ddddff", font=("Arial", 11, "bold"))
        self.btn_run.pack(pady=25, fill="x", padx=40)

        self.status_label = tk.Label(root, text="", fg="blue")
        self.status_label.pack(pady=(0, 10))

    def select_map(self):
        path = filedialog.askopenfilename(
            filetypes=[("GeoJSON files", "*.geojson"), ("All files", "*.*")]
        )
        if path:
            self.map_path_var.set(path)

    def select_data(self):
        path = filedialog.askopenfilename(
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if path:
            self.data_path_var.set(path)

    def select_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            base = "treemap_result.png"
            self.output_path_var.set(os.path.join(folder, base))

    def run_treemap(self):
        map_path = self.map_path_var.get()
        data_path = self.data_path_var.get()
        output_path = self.output_path_var.get()

        if not map_path or not data_path:
            messagebox.showerror("Ошибка", "Выберите оба файла: карту и данные.")
            return

        try:
            self.status_label.config(text="Обработка…")
            self.root.update()

            region_poly, region_gdf = load_region_polygon(map_path)
            data = load_excel_data(data_path)

            values = [item["value"] for item in data]
            labels = [str(item["district"]) for item in data]

            rects, labels_filtered = pack_treemap_inside_region(values, labels, region_poly)

            if len(rects) == 0:
                messagebox.showwarning("Предупреждение", "Не получилось разместить прямоугольники внутри контура. Попробуйте другой GeoJSON или данные.")
                self.status_label.config(text="Готово (без прямоугольников)")
                return

            plot_treemap_on_region(region_gdf, rects, labels_filtered, output_path)
            self.status_label.config(text=f"Готово: {output_path}")
            messagebox.showinfo("Успех", f"Treemap сохранён:\n{output_path}")

        except Exception as e:
            self.status_label.config(text="Ошибка")
            messagebox.showerror("Ошибка", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = TreemapApp(root)
    root.mainloop()
