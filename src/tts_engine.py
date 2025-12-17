"""
Модуль утилит для преобразования текста в речь (TTS).
Вынесенная логика для чистоты основного движка.
"""
import tempfile
import os
import sys
from pathlib import Path

# Динамический импорт для гибкости и обработки отсутствия библиотек
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    print("Предупреждение: Библиотека 'gtts' не установлена. Установите: pip install gtts")

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("Предупреждение: Библиотека 'pygame' не установлена. Установите: pip install pygame")

# Добавляем корень проекта в путь для импорта других модулей, если потребуется
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def synthesize_to_file(text, lang='ru', output_path=None, slow=False):
    """
    Синтезирует речь из текста и сохраняет в аудиофайл.
    
    Аргументы:
        text (str): Текст для озвучивания.
        lang (str): Код языка (например, 'ru', 'en'). По умолчанию 'ru'.
        output_path (str, optional): Путь для сохранения файла.
                                     Если None, создается временный файл.
        slow (bool): Медленный режим речи (для gTTS). По умолчанию False.
    
    Возвращает:
        str: Путь к созданному аудиофайлу.
    
    Исключения:
        RuntimeError: Если библиотека gTTS недоступна или произошла ошибка синтеза.
    """
    if not GTTS_AVAILABLE:
        raise RuntimeError("Библиотека gTTS не установлена. Функция синтеза недоступна.")
    
    if not text or not isinstance(text, str):
        raise ValueError("Текст для синтеза должен быть непустой строкой.")
    
    try:
        tts = gTTS(text=text, lang=lang, slow=slow)
        
        if output_path is None:
            # Создаем временный файл с понятным префиксом
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False, prefix='tts_') as tmp:
                output_path = tmp.name
        
        tts.save(output_path)
        print(f"[TTS] Текст синтезирован в файл: {output_path}")
        return output_path
        
    except Exception as e:
        raise RuntimeError(f"Ошибка синтеза речи с gTTS: {e}") from e

def play_audio(file_path):
    """
    Воспроизводит аудиофайл с помощью pygame.
    
    Аргументы:
        file_path (str): Путь к аудиофайлу.
    
    Возвращает:
        bool: True, если воспроизведение успешно, иначе False.
    """
    if not PYGAME_AVAILABLE:
        print("Ошибка: Библиотека 'pygame' не установлена для воспроизведения.")
        return False
    
    if not os.path.exists(file_path):
        print(f"Ошибка: Аудиофайл не найден: {file_path}")
        return False
    
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        
        # Ожидание окончания воспроизведения
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        
        pygame.mixer.music.stop()
        pygame.mixer.quit()
        return True
        
    except Exception as e:
        print(f"Ошибка воспроизведения аудио: {e}")
        return False

def synthesize_and_play(text, lang='ru', cleanup=True):
    """
    Основная высокоуровневая функция: синтез и немедленное воспроизведение.
    
    Аргументы:
        text (str): Текст для озвучивания.
        lang (str): Код языка. По умолчанию 'ru'.
        cleanup (bool): Удалять ли временный файл после воспроизведения. По умолчанию True.
    
    Возвращает:
        bool: Общий успех операции.
    """
    temp_file = None
    try:
        # 1. Синтез во временный файл
        temp_file = synthesize_to_file(text, lang=lang)
        
        # 2. Воспроизведение
        success = play_audio(temp_file)
        
        if success:
            print(f"[TTS] Успешно озвучено: '{text[:50]}{'...' if len(text) > 50 else ''}'")
        else:
            print("[TTS] Не удалось воспроизвести аудио.")
        
        return success
        
    except Exception as e:
        print(f"[TTS] Ошибка в процессе синтеза и воспроизведения: {e}")
        return False
        
    finally:
        # 3. Очистка временного файла
        if cleanup and temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
                # print(f"[TTS] Временный файл удален: {temp_file}")
            except OSError as e:
                print(f"[TTS] Не удалось удалить временный файл {temp_file}: {e}")

def list_languages():
    """
    Выводит в консоль список поддерживаемых gTTS языков.
    """
    if not GTTS_AVAILABLE:
        print("gTTS не доступен для получения списка языков.")
        return
    
    # Основные языки, поддерживаемые gTTS
    languages = {
        'ru': 'Русский',
        'en': 'Английский',
        'de': 'Немецкий',
        'fr': 'Французский',
        'es': 'Испанский',
        'it': 'Итальянский',
        'ja': 'Японский',
        'ko': 'Корейский',
        'zh-CN': 'Китайский (упрощенный)',
        'zh-TW': 'Китайский (традиционный)',
    }
    
    print("Поддерживаемые языки (основные):")
    for code, name in languages.items():
        print(f"  {code}: {name}")

# Блок для простого тестирования модуля
if __name__ == "__main__":
    print("=== Тестирование модуля TTS утилит ===")
    
    # Проверка доступности библиотек
    print(f"gTTS доступен: {GTTS_AVAILABLE}")
    print(f"Pygame доступен: {PYGAME_AVAILABLE}")
    
    if GTTS_AVAILABLE:
        # Тестовый синтез и воспроизведение
        test_text = "Привет! Это тестовая фраза русского текста. Работает!"
        print(f"\nТестируем синтез фразы: '{test_text}'")
        
        result = synthesize_and_play(test_text, lang='ru', cleanup=True)
        print(f"Результат теста: {'УСПЕХ' if result else 'НЕУДАЧА'}")
        
        # Показ языков
        list_languages()
    else:
        print("\nУстановите gtts для тестирования: pip install gtts pygame")