# -*- coding: utf-8 -*-
"""Собирает сайт-выставку из папки с фотографиями.

Запуск:  python build.py
Оригиналы в ../Beauty не меняются: скрипт только читает их и кладёт
уменьшенные копии в img/. Год берётся из даты съёмки внутри файла.
Для файлов без даты год можно вписать в years.csv (имя файла;год).
"""
import csv
import hashlib
import json
import os
import sys

from PIL import Image, ImageOps
import pillow_heif

pillow_heif.register_heif_opener()
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "Beauty"))
FULL = os.path.join(HERE, "img", "full")
THUMB = os.path.join(HERE, "img", "thumb")
YEARS_CSV = os.path.join(HERE, "years.csv")
EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
FULL_SIDE, THUMB_SIDE = 2000, 720


def read_overrides():
    """years.csv: имя файла;год. Пустой год = пока неизвестен."""
    out = {}
    if os.path.exists(YEARS_CSV):
        with open(YEARS_CSV, encoding="utf-8-sig", newline="") as f:
            for row in csv.reader(f, delimiter=";"):
                if len(row) >= 2 and row[0].strip() and not row[0].startswith("#"):
                    out[row[0].strip()] = row[1].strip()
    return out


def exif_date(im):
    ex = im.getexif()
    dt = ex.get_ifd(0x8769).get(36867) or ex.get(306)
    if dt and len(str(dt)) >= 10 and str(dt)[:4].isdigit():
        return str(dt)
    return None


def save_copy(im, path, side):
    c = im.copy()
    c.thumbnail((side, side), Image.LANCZOS)
    c.save(path, "JPEG", quality=86, optimize=True, progressive=True)


def main():
    os.makedirs(FULL, exist_ok=True)
    os.makedirs(THUMB, exist_ok=True)
    overrides = read_overrides()
    photos, undated = [], []

    for name in sorted(os.listdir(SRC)):
        if os.path.splitext(name)[1].lower() not in EXTS:
            continue
        src = os.path.join(SRC, name)
        pid = hashlib.md5(name.encode("utf-8")).hexdigest()[:10]
        full = os.path.join(FULL, pid + ".jpg")
        thumb = os.path.join(THUMB, pid + ".jpg")

        im = Image.open(src)
        date = exif_date(im)
        fresh = (
            os.path.exists(full)
            and os.path.exists(thumb)
            and os.path.getmtime(full) >= os.path.getmtime(src)
        )
        if fresh:
            w, h = Image.open(full).size
        else:
            im = ImageOps.exif_transpose(im).convert("RGB")
            save_copy(im, full, FULL_SIDE)
            save_copy(im, thumb, THUMB_SIDE)
            w, h = Image.open(full).size
            print("копия:", name)

        year = overrides.get(name) or (date[:4] if date else "")
        if not year:
            undated.append(name)
        photos.append(
            {
                "id": pid,
                "file": name,
                "year": year,
                "date": date[:10].replace(":", "-") if date else "",
                "sort": (date or "") if date else "",
                "w": w,
                "h": h,
            }
        )

    # убрать копии фотографий, которых больше нет в исходной папке — не удаляем,
    # только сообщаем (удаление файлов делается вручную)
    known = {p["id"] + ".jpg" for p in photos}
    stale = [f for f in os.listdir(FULL) if f not in known]
    if stale:
        print("лишние копии в img/ (исходника больше нет):", len(stale))

    # дополнить years.csv строками для файлов без даты
    missing = [n for n in undated if n not in overrides]
    if missing or not os.path.exists(YEARS_CSV):
        new = not os.path.exists(YEARS_CSV)
        with open(YEARS_CSV, "a", encoding="utf-8-sig", newline="") as f:
            if new:
                f.write("# имя файла;год  — впишите год после точки с запятой и запустите build.py\n")
            for n in missing:
                f.write(n + ";\n")

    photos.sort(key=lambda p: (p["year"] or "0000", p["sort"], p["file"]))
    for p in photos:
        del p["sort"]
    with open(os.path.join(HERE, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.PHOTOS = " + json.dumps(photos, ensure_ascii=False, indent=1) + ";\n")

    years = sorted({p["year"] for p in photos if p["year"]})
    print(f"всего фото: {len(photos)}, с годом: {len(photos) - len(undated)}, без года: {len(undated)}")
    print("годы:", ", ".join(years))


if __name__ == "__main__":
    main()
