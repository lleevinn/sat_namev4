"""
Модуль синтеза речи (TTS) для Ирис
Использует pyttsx3 для офлайн-озвучки
"""

import threading
import queue
import time

class TTSEngine:
    def __init__(self, voice=None, rate=200, volume=0.9):
        """
        Инициализация TTS движка pyttsx3
        
        Args:
            voice: Голос (если None - системный по умолчанию)
            rate: Скорость речи (слов в минуту, 150-250 нормально)
            volume: Громкость (0.0 - 1.0)
        """
        self.enabled = True
        self.engine = None
        self.queue = queue.Queue()
        self.is_speaking = False
        
        print("[TTS] Инициализация голосового движка...")
        
        try:
            import pyttsx3
            
            # Создаём движок
            self.engine = pyttsx3.init()
            
            # Настройка скорости (упрощённая, без умножения)
            self.engine.setProperty('rate', int(rate))
            
            # Настройка громкости
            self.engine.setProperty('volume', float(volume))
            
            # Настройка голоса, если указан
            if voice:
                voices = self.engine.getProperty('voices')
                for v in voices:
                    if voice in v.id or voice in v.name:
                        self.engine.setProperty('voice', v.id)
                        break
            
            print(f"[TTS] Движок инициализирован. Скорость: {rate}, Громкость: {volume}")
            
        except Exception as e:
            print(f"[TTS] ОШИБКА инициализации: {e}")
            print("[TTS] Голосовой движок отключён. Ирис будет выводить текст только в консоль.")
            self.enabled = False
            self.engine = None
    
    def speak(self, text: str, **kwargs):
        """
        Озвучивание текста. **kwargs нужен для игнорирования лишних параметров
        (например, priority, emotion), которые могут приходить из других модулей.
        
        Args:
            text: Текст для озвучки
            **kwargs: Дополнительные параметры (игнорируются)
        """
        if not text or not self.enabled or not self.engine:
            # Если движок не работает, просто выводим текст в консоль
            print(f"[IRIS] >> {text}")
            return
        
        print(f"[TTS] Озвучивание: {text[:50]}..." if len(text) > 50 else f"[TTS] Озвучивание: {text}")
        
        try:
            # Озвучиваем текст
            self.engine.say(text)
            self.engine.runAndWait()
            
        except Exception as e:
            print(f"[TTS] Ошибка при озвучивании: {e}")
            print(f"[IRIS] >> {text}")
    
    def stop(self):
        """Остановка TTS движка (корректная обработка для pyttsx3)"""
        if self.engine:
            try:
                # Останавливаем текущую речь
                self.engine.stop()
            except:
                pass
        
        print("[TTS] Движок остановлен")
    
    def set_voice(self, voice_name: str):
        """Смена голоса"""
        if not self.engine or not self.enabled:
            return False
        
        try:
            voices = self.engine.getProperty('voices')
            for v in voices:
                if voice_name in v.id or voice_name in v.name:
                    self.engine.setProperty('voice', v.id)
                    print(f"[TTS] Голос изменён на: {v.name}")
                    return True
        except Exception as e:
            print(f"[TTS] Ошибка смены голоса: {e}")
        
        return False
    
    def set_rate(self, rate: int):
        """Установка скорости речи"""
        if not self.engine or not self.enabled:
            return
        
        try:
            self.engine.setProperty('rate', rate)
            print(f"[TTS] Скорость речи установлена: {rate}")
        except Exception as e:
            print(f"[TTS] Ошибка установки скорости: {e}")
    
    def set_volume(self, volume: float):
        """Установка громкости"""
        if not self.engine or not self.enabled:
            return
        
        try:
            self.engine.setProperty('volume', max(0.0, min(1.0, volume)))
            print(f"[TTS] Громкость установлена: {volume}")
        except Exception as e:
            print(f"[TTS] Ошибка установки громкости: {e}")

# Тестирование при прямом запуске
if __name__ == "__main__":
    print("Тестирование TTS движка...")
    tts = TTSEngine(rate=200, volume=0.8)
    tts.speak("Привет! Я Ирис, ваш голосовой помощник.")
    print("Тест завершён успешно!")