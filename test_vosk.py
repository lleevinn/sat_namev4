import os
import sys

# Проверка существования модели
model_path = "models/vosk-model-ru-0.22"
if os.path.exists(model_path):
    print(f"✅ Модель найдена: {model_path}")
    print(f"   Размер папки: {sum(os.path.getsize(os.path.join(dirpath, filename)) 
    for dirpath, dirnames, filenames in os.walk(model_path) 
    for filename in filenames) / (1024**3):.2f} ГБ")
    
    # Проверка структуры
    print("\n📁 Структура модели:")
    for root, dirs, files in os.walk(model_path):
        level = root.replace(model_path, '').count(os.sep)
        indent = ' ' * 2 * level
        print(f'{indent}{os.path.basename(root)}/')
        subindent = ' ' * 2 * (level + 1)
        for file in files[:5]:  # Первые 5 файлов
            print(f'{subindent}{file}')
        if len(files) > 5:
            print(f'{subindent}... и еще {len(files) - 5} файлов')
        break  # Только первый уровень
else:
    print(f"❌ Модель не найдена: {model_path}")
    print("\n🔍 Ищем модель...")
    possible_paths = [
        "vosk-model-ru-0.22",
        "models/vosk-model-ru-0.22",
        os.path.expanduser("~/vosk-model-ru-0.22"),
        "C:/vosk-model-ru-0.22",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"✅ Найдена в: {path}")
            # Создаем симлинк или копируем
            os.makedirs("models", exist_ok=True)
            print(f"📁 Копируем в models/...")
            import shutil
            try:
                shutil.copytree(path, "models/vosk-model-ru-0.22", dirs_exist_ok=True)
                print("✅ Модель скопирована")
                break
            except Exception as e:
                print(f"❌ Ошибка копирования: {e}")