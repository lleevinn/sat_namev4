# setup.py
import os

# Создаем необходимые файлы и папки
paths = [
    "src/__init__.py",
    "src/utils/__init__.py",
    "src/utils/tts_utils.py",
    "src/tts_engine.py",
    "main.py"
]

for path in paths:
    dir_name = os.path.dirname(path)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)
    
    if not os.path.exists(path):
        if path.endswith("__init__.py"):
            # Создаем пустой файл
            with open(path, 'w', encoding='utf-8') as f:
                f.write("# Package initializer\n")
        print(f"Создан: {path}")

print("Структура проекта готова!")