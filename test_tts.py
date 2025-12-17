# test_tts.py
import sys
import os

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.tts_engine import TTSEngine
    print("✓ Импорт TTSEngine успешен!")
    
    # Простой тест
    def test_callback(speaking, intensity):
        status = "ГОВОРИТ" if speaking else "МОЛЧИТ"
        print(f"[CALLBACK] {status} (интенсивность: {intensity:.2f})")
    
    tts = TTSEngine(visual_callback=test_callback)
    tts.start()
    
    print("Тест 1: Нейтральная фраза...")
    tts.speak("Привет, мир! Это тест TTS системы.", emotion='neutral')
    
    import time
    time.sleep(5)
    
    print("Тест 2: Радостная фраза...")
    tts.speak("Ура! Всё работает отлично!", emotion='happy')
    
    time.sleep(5)
    
    tts.stop()
    print("✓ Тест завершен успешно!")
    
except SyntaxError as e:
    print(f"✗ Синтаксическая ошибка в tts_engine.py: {e}")
    print("Убедитесь, что все кавычки закрыты правильно.")
except ImportError as e:
    print(f"✗ Ошибка импорта: {e}")
    print("Установите зависимости: pip install edge-tts pygame")
except Exception as e:
    print(f"✗ Общая ошибка: {e}")
    import traceback
    traceback.print_exc()