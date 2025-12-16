import speech_recognition as sr
import threading
import time
import queue
import os
from typing import Optional, Callable
import logging

# Настройка логирования для этого модуля
logger = logging.getLogger('VoiceInput')

class VoiceInput:
    def __init__(self, wake_word: str = "ирис", sensitivity: float = 0.5):
        """
        Инициализация голосового ввода
        
        Args:
            wake_word: Ключевое слово для активации
            sensitivity: Чувствительность (0.0-1.0)
        """
        self.wake_word = wake_word.lower()
        self.sensitivity = max(0.1, min(1.0, sensitivity))
        
        # Очередь для распознанных команд
        self.command_queue = queue.Queue()
        
        # Инициализация распознавателя
        self.recognizer = sr.Recognizer()
        
        # НАСТРОЙКИ ДЛЯ БЫСТРОЙ РЕЧИ:
        # Более короткая пауза для конца фразы
        self.recognizer.pause_threshold = 0.2  # Было 0.8, теперь 0.3 секунды
        
        # Более высокий порог энергии (чувствительность)
        # sensitivity=1.0 -> высокий порог (менее чувствителен)
        # sensitivity=0.0 -> низкий порог (более чувствителен)
        self.recognizer.energy_threshold = 2000 + (4000 * (1 - sensitivity))
        
        # Отключаем динамическую регулировку для стабильности
        self.recognizer.dynamic_energy_threshold = False
        
        # Минимальная длительность тишины для конца фразы
        self.recognizer.non_speaking_duration = 0.1
        
        # Флаги состояния
        self.is_listening = False
        self.is_calibrating = False
        
        # Поток для прослушивания
        self.listener_thread: Optional[threading.Thread] = None
        
        # Callback для обработки команд
        self.command_callback: Optional[Callable] = None
        
        # История распознаваний для отладки
        self.recognition_history = []
        self.max_history = 20
        
        logger.info(f"Инициализация с wake word: '{self.wake_word}', чувствительность: {sensitivity}")
        print(f"[VOICE] Инициализация с wake word: '{self.wake_word}'")
        
    def calibrate_microphone(self):
        """Калибровка микрофона для текущих условий"""
        if self.is_calibrating:
            return
            
        self.is_calibrating = True
        print("[VOICE] Калибровка микрофона...")
        
        try:
            with sr.Microphone() as source:
                # Слушаем фоновый шум 0.5 секунды (быстрее калибровка)
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                # Тестовое распознавание
                print("[VOICE] Скажите что-нибудь для теста...")
                audio = self.recognizer.listen(source, timeout=2, phrase_time_limit=2)
                
                try:
                    text = self.recognizer.recognize_google(audio, language="ru-RU")
                    print(f"[VOICE] Распознано: '{text}'")
                    
                    # Автонастройка порога на основе энергии звука
                    import numpy as np
                    audio_data = np.frombuffer(audio.frame_data, dtype=np.int16)
                    energy = np.sqrt(np.mean(audio_data**2))
                    
                    # Устанавливаем порог на 60% от энергии тестовой фразы
                    new_threshold = int(energy * 0.6)
                    if new_threshold > 1000 and new_threshold < 10000:
                        self.recognizer.energy_threshold = new_threshold
                        print(f"[VOICE] Автонастройка порога: {new_threshold}")
                        
                except sr.UnknownValueError:
                    print("[VOICE] Речь не распознана, используем настройки по умолчанию")
                except sr.RequestError as e:
                    print(f"[VOICE] Ошибка сервиса распознавания: {e}")
                    
        except Exception as e:
            print(f"[VOICE] Ошибка калибровки: {e}")
        finally:
            self.is_calibrating = False
            print("[VOICE] Калибровка завершена")
            
    def _check_wake_word(self, text: str) -> bool:
        """
        Улучшенная проверка wake word с поддержкой быстрой речи
        
        Args:
            text: Распознанный текст
            
        Returns:
            bool: True если wake word обнаружен
        """
        text_lower = text.lower().strip()
        
        # 1. Точное совпадение
        if self.wake_word in text_lower:
            return True
            
        # 2. Быстрая речь: wake word и команда могут быть слитно
        # Пример: "ириспривет" вместо "ирис привет"
        if len(text_lower) >= len(self.wake_word):
            # Проверяем начало строки
            if text_lower.startswith(self.wake_word):
                return True
                
            # Проверяем первые 3 символа (для частичного распознавания)
            if text_lower[:3] == self.wake_word[:3]:
                return True
                
        # 3. Распространённые ошибки распознавания
        common_errors = {
            'ирис': ['рис', 'ири', 'ириса', 'ириска', 'iris', 'ирись'],
            'iris': ['ирис', 'арис', 'ариш', 'ириш']
        }
        
        if self.wake_word in common_errors:
            for error in common_errors[self.wake_word]:
                if error in text_lower:
                    return True
                    
        # 4. Разделяем текст на слова и проверяем каждое
        words = text_lower.split()
        for word in words:
            if len(word) >= 3:
                # Проверяем похожесть начала слова
                if word.startswith(self.wake_word[:3]):
                    return True
                    
        return False
        
    def _extract_command(self, text: str) -> str:
        """
        Извлечение команды из текста
        
        Args:
            text: Распознанный текст
            
        Returns:
            str: Команда или пустая строка
        """
        text_lower = text.lower().strip()
        
        # 1. Пытаемся найти точное совпадение wake word
        if self.wake_word in text_lower:
            parts = text_lower.split(self.wake_word, 1)
            if len(parts) > 1:
                return parts[1].strip()
                
        # 2. Проверяем начало строки (для быстрой речи)
        if text_lower.startswith(self.wake_word):
            return text_lower[len(self.wake_word):].strip()
            
        # 3. Проверяем первые 3 символа
        if text_lower[:3] == self.wake_word[:3]:
            # Пытаемся найти где заканчивается wake word
            for i in range(3, min(len(text_lower), len(self.wake_word) + 2)):
                if text_lower[:i] == self.wake_word[:i]:
                    return text_lower[i:].strip()
                    
        # 4. Если ничего не нашли, возвращаем весь текст
        # (возможно сказали только команду без wake word)
        return text_lower
        
    def _listen_loop(self):
        """Основной цикл прослушивания"""
        print("[VOICE] Слушаю... Скажите 'Ирис' для активации")
        
        with sr.Microphone() as source:
            # Однократная калибровка при запуске
            if not self.is_calibrating:
                self.calibrate_microphone()
                
            while self.is_listening:
                try:
                    # Прослушивание микрофона с короткими таймаутами
                    audio = self.recognizer.listen(
                        source, 
                        timeout=0.5,  # Короткий таймаут ожидания
                        phrase_time_limit=3  # Максимальная длина фразы
                    )
                    
                    # Распознавание речи
                    text = self.recognizer.recognize_google(audio, language="ru-RU")
                    
                    # Сохраняем в историю
                    self.recognition_history.append(text)
                    if len(self.recognition_history) > self.max_history:
                        self.recognition_history.pop(0)
                    
                    print(f"[VOICE] Распознано: {text}")
                    
                    # Проверка на наличие wake word
                        if command:
                            print(f"[IRIS] Команда: {command}")
                        
                        
                        # Извлечение команды
                        command = self._extract_command(text)
                        if command:
                            print(f"[IRIS] Команда: {command}")
                        else:
                            print(f"[IRIS] Просто активация (команда пустая)")
                            command = "привет"  # Дефолтная команда при просто "ирис"
                            
                        # Добавление команды в очередь
                        self.command_queue.put(command)
                            
                        # Вызов callback, если задан
                        if self.command_callback:
                            self.command_callback(command)
                        else:
                            # Если команда пустая, всё равно добавляем в очередь
                            # для обработки простой активации
                            self.command_queue.put("")
                                
                    # Обработка специальных команд
                    elif text.lower() in ["стоп", "остановись", "выход", "stop", "exit"]:
                        print("[IRIS] Команда на остановку получена")
                        self.command_queue.put("стоп")
                        
                except sr.WaitTimeoutError:
                    # Таймаут - ничего не сказали, продолжаем
                    continue
                except sr.UnknownValueError:
                    # Речь не распознана
                    continue
                except sr.RequestError as e:
                    logger.error(f"Ошибка сервиса распознавания: {e}")
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"Неожиданная ошибка: {e}")
                    time.sleep(0.1)
                    
    def start(self):
        """Запуск голосового ввода"""
        if self.is_listening:
            print("[VOICE] Уже работает")
            return
            
        self.is_listening = True
        self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listener_thread.start()
        print("[VOICE] Голосовой ввод запущен")
        
    def stop(self):
        """Остановка голосового ввода"""
        self.is_listening = False
        if self.listener_thread:
            self.listener_thread.join(timeout=2)
        print("[VOICE] Голосовой ввод остановлен")
        
    def get_command(self) -> Optional[str]:
        """
        Получение следующей команды из очереди
        
        Returns:
            str: Команда или None если очередь пуста
        """
        try:
            return self.command_queue.get_nowait()
        except queue.Empty:
            return None
            
    def set_command_callback(self, callback: Callable):
        """
        Установка callback-функции для обработки команд
        
        Args:
            callback: Функция, принимающая команду (str)
        """
        self.command_callback = callback
        
    def get_recognition_stats(self) -> dict:
        """
        Получение статистики распознавания
        
        Returns:
            dict: Статистика
        """
        total = len(self.recognition_history)
        wake_detected = sum(1 for text in self.recognition_history 
                          if self._check_wake_word(text))
        
        return {
            "total_phrases": total,
            "wake_detected": wake_detected,
            "detection_rate": wake_detected / total if total > 0 else 0,
            "recent_phrases": self.recognition_history[-5:] if total > 0 else []
        }