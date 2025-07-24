import os
import shutil
import json
from urllib.parse import unquote
from collections import Counter
from sklearn.model_selection import train_test_split
from ls_wb_pipeline import settings


def build_classification_dataset(all_tasks, train_ratio=0.8, test_ratio=0.1, val_ratio=0.1):
    entries = []
    stats = Counter()

    for task in all_tasks:
        anns = task.get("annotations", [])
        if not anns or not isinstance(anns, list):
            continue

        results = anns[0].get("result", [])
        if not results:
            continue

        try:
            class_name = results[0]["value"]["choices"][0]
            image_url = task["data"]["image"]
            image_name = os.path.basename(unquote(image_url))
            entries.append({
                "image": image_name,
                "class": class_name
            })
            stats[class_name] += 1
        except Exception as e:
            continue

    print("\n📊 Распределение классов:")
    for cls, count in stats.items():
        print(f"{cls:25} — {count} изображений")

    if not entries:
        print("❗ Нет валидных размеченных задач.")
        return

    # Разделение
    if len(entries) < 3:
        split_data = {"train": entries, "val": [], "test": []}
    else:
        train_val, test = train_test_split(entries, test_size=test_ratio, random_state=42)
        train, val = train_test_split(train_val, test_size=val_ratio / (train_ratio + val_ratio), random_state=42)
        split_data = {"train": train, "val": val, "test": test}

    # Копирование
    for split, items in split_data.items():
        for item in items:
            class_dir = os.path.join(settings.DATASET_PATH, split, item["class"])
            os.makedirs(class_dir, exist_ok=True)

            src = os.path.join(settings.MOUNTED_PATH, item["image"])
            dst = os.path.join(class_dir, item["image"])
            if os.path.exists(src):
                shutil.copy(src, dst)

    print(f"\n✅ Классификационный датасет собран: {settings.DATASET_PATH}")


def analyze_classification_dataset(dataset_path):
    """
    Анализирует датасет классификации (по структуре каталогов).
    Возвращает словарь с количеством изображений по классам и сплитам.
    """
    try:
        classes_file = os.path.join(dataset_path, "classes.txt")
        if not os.path.exists(classes_file):
            return {"error": "Файл classes.txt не найден — датасет ещё не создан"}

        with open(classes_file, "r", encoding="utf-8") as f:
            classes = [line.strip() for line in f if line.strip()]

        split_counters = {"train": Counter(), "val": Counter(), "test": Counter()}

        for split in split_counters:
            split_dir = os.path.join(dataset_path, split)
            if not os.path.exists(split_dir):
                continue
            for class_id, class_name in enumerate(classes):
                class_dir = os.path.join(split_dir, class_name)
                if not os.path.isdir(class_dir):
                    continue
                image_files = [
                    f for f in os.listdir(class_dir)
                    if f.lower().endswith((".jpg", ".jpeg", ".png"))
                ]
                split_counters[split][class_id] = len(image_files)

        total = sum(sum(c.values()) for c in split_counters.values())
        result = {
            "total": total,
            "classes": []
        }

        for class_id, class_name in enumerate(classes):
            tr = split_counters["train"][class_id]
            va = split_counters["val"][class_id]
            te = split_counters["test"][class_id]
            total_cls = tr + va + te
            percent = (total_cls / total) * 100 if total else 0
            result["classes"].append({
                "id": class_id,
                "name": class_name,
                "train": tr,
                "val": va,
                "test": te,
                "total": total_cls,
                "percent": round(percent, 1)
            })

        return result
    except Exception as e:
        return {"error": f"Ошибка при анализе датасета: {str(e)}"}


def main_from_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    build_classification_dataset(data)
