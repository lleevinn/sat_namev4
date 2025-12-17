"""
IRIS Voice Input - Улучшенное распознавание голоса с Vosk
Офлайн распознавание с высокой чувствительностью к wake-word 'Ирис'
Поддержка Vosk (офлайн) и Google Speech Recognition (онлайн)
Версия: 3.0.0 - Объединенная и исправленная
"""

import threading
import time
import queue
import os
import json
import logging
import sys
from typing import Optional, Callable, List, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('VoiceInput')

# Перечисление режимов распознавания
class RecognitionMode(Enum):
    """Режимы распознавания речи"""
    VOSK = "vosk"           # Офлайн с Vosk
    GOOGLE = "google"       # Онлайн с Google
    HYBRID = "hybrid"       # Гибридный (Vosk + Google)
    SIMPLE = "simple"       # Простой консольный ввод


@dataclass
class RecognitionStats:
    """Статистика распознавания речи"""
    total_phrases: int = 0
    wake_detected: int = 0
    vosk_success: int = 0
    google_success: int = 0
    avg_confidence: float = 0.0
    last_recognition: str = ""
    audio_quality: float = 0.0


@dataclass
class AudioSettings:
    """Настройки аудио"""
    sample_rate: int = 16000
    chunk_size: int = 1600
    channels: int = 1
    energy_threshold: int = 3000
    pause_threshold: float = 0.5
    phrase_threshold: float = 0.3
    non_speaking_duration: float = 0.3
    dynamic_threshold: bool = True


# Динамический импорт зависимостей
try:
    from vosk import Model, KaldiRecognizer, SetLogLevel
    SetLogLevel(-1)  # Отключаем логи Vosk
    VOSK_AVAILABLE = True
    logger.info("Vosk успешно импортирован")
except ImportError as e:
    VOSK_AVAILABLE = False
    logger.warning(f"Vosk не установлен: {e}. Установите: pip install vosk")

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
    logger.info("SpeechRecognition успешно импортирован")
except ImportError as e:
    SR_AVAILABLE = False
    logger.warning(f"SpeechRecognition не установлен: {e}. Установите: pip install SpeechRecognition")

try:
    import numpy as np
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
    logger.info("SoundDevice и NumPy успешно импортированы")
except ImportError as e:
    SOUNDDEVICE_AVAILABLE = False
    logger.warning(f"SoundDevice/NumPy не установлены: {e}. Установите: pip install sounddevice numpy")

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
    logger.info("PyAudio успешно импортирован")
except ImportError as e:
    PYAUDIO_AVAILABLE = False
    logger.warning(f"PyAudio не установлен: {e}. Установите: pip install pyaudio")


class VoiceInput:
    """
    Улучшенный модуль распознавания голоса с поддержкой:
    - Vosk (офлайн, высокое качество, русский язык)
    - Google Speech Recognition (онлайн, высокая точность)
    - Гибридный режим (автоматический выбор лучшего)
    - Расширенная система wake word детекции
    - Статистика и аналитика качества распознавания
    """
    
    # Варианты wake word для fuzzy matching
    WAKE_WORD_VARIANTS = [
        'ирис', 'iris', 'ири', 'ириска', 'ирисс', 'ириса',
        'айрис', 'арис', 'ириш', 'ирись', 'рис', 'эрис',
        'ирисю', 'ирися', 'ирису', 'ирисе'
    ]
    
    # Быстрые команды для немедленного выполнения
    QUICK_COMMANDS = {
        'стоп': 'stop', 'остановись': 'stop', 'выход': 'stop', 'exit': 'stop',
        'пауза': 'pause', 'продолжить': 'resume', 'тише': 'volume_down',
        'громче': 'volume_up', 'выключи звук': 'mute', 'включи звук': 'unmute',
        'помощь': 'help', 'команды': 'commands', 'статистика': 'stats'
    }
    
    def __init__(self, 
                 wake_word: str = "ирис",
                 sensitivity: float = 0.8,
                 recognition_mode: str = "hybrid",
                 vosk_model_path: Optional[str] = None,
                 audio_device_index: Optional[int] = None,
                 sample_rate: int = 16000,
                 enable_analytics: bool = True):
        """
        Инициализация системы распознавания голоса
        
        Args:
            wake_word: Ключевое слово активации
            sensitivity: Чувствительность (0.1-1.0)
            recognition_mode: Режим распознавания (vosk, google, hybrid, simple)
            vosk_model_path: Путь к модели Vosk
            audio_device_index: Индекс аудиоустройства
            sample_rate: Частота дискретизации
            enable_analytics: Включить сбор статистики
        """
        print("=" * 60)
        print("🎤 ИНИЦИАЛИЗАЦИЯ СИСТЕМЫ ГОЛОСОВОГО ВВОДА")
        print("=" * 60)
        
        # Основные настройки
        self.wake_word = wake_word.lower()
        self.sensitivity = max(0.1, min(1.0, sensitivity))
        self.recognition_mode = recognition_mode
        self.audio_device_index = audio_device_index
        self.enable_analytics = enable_analytics
        
        # Определение режима распознавания
        self._determine_recognition_mode()
        
        # Настройки аудио
        self.sample_rate = sample_rate
        self.audio_settings = AudioSettings(
            sample_rate=sample_rate,
            energy_threshold=int(1500 + (3500 * (1 - sensitivity)))
        )
        
        # Система очередей
        self.command_queue = queue.PriorityQueue()  # (приоритет, время, команда)
        self.audio_buffer = queue.Queue()
        
        # Флаги состояния
        self.is_listening = False
        self.is_calibrating = False
        self.is_active = False  # Режим активации после wake word
        self.activation_timeout = 8.0  # Секунд активности после wake word
        self.last_activation_time = 0
        self.last_audio_time = 0
        
        # Коллбэки
        self.command_callback: Optional[Callable[[str], None]] = None
        self.wake_callback: Optional[Callable[[], None]] = None
        self.error_callback: Optional[Callable[[Exception], None]] = None
        
        # История и статистика
        self.recognition_history: List[Dict[str, Any]] = []
        self.max_history = 100
        self.stats = RecognitionStats()
        
        # Модели и распознаватели
        self.vosk_model = None
        self.vosk_recognizer = None
        self.sr_recognizer = None
        self.audio_stream = None
        self.pyaudio_instance = None
        
        # Потоки
        self.listener_thread: Optional[threading.Thread] = None
        self.processor_thread: Optional[threading.Thread] = None
        self.analytics_thread: Optional[threading.Thread] = None
        
        # Инициализация компонентов
        self._initialize_components(vosk_model_path)
        
        # Вывод информации о системе
        self._print_system_info()
        
        print("[VOICE] ✅ Система голосового ввода инициализирована")
        print("=" * 60)
    
    def _determine_recognition_mode(self):
        """Автоматическое определение оптимального режима распознавания"""
        if self.recognition_mode == "auto":
            if VOSK_AVAILABLE and self._check_vosk_model():
                self.recognition_mode = "vosk"
                print("[VOICE] Автовыбор: Vosk (офлайн режим)")
            elif SR_AVAILABLE:
                self.recognition_mode = "google"
                print("[VOICE] Автовыбор: Google Speech (онлайн режим)")
            else:
                self.recognition_mode = "simple"
                print("[VOICE] Автовыбор: Простой ввод (консольный режим)")
    
    def _check_vosk_model(self) -> bool:
        """Проверка наличия модели Vosk"""
        model_paths = [
            "models/vosk-model-small-ru",
            "vosk-model-small-ru-0.22",
            os.path.expanduser("~/.vosk/vosk-model-small-ru"),
            "/usr/share/vosk/vosk-model-small-ru",
        ]
        return any(os.path.exists(path) for path in model_paths)
    
    def _initialize_components(self, vosk_model_path: Optional[str] = None):
        """Инициализация всех компонентов системы"""
        print("[VOICE] Инициализация компонентов...")
        
        # Инициализация Vosk
        if VOSK_AVAILABLE and self.recognition_mode in ["vosk", "hybrid"]:
            self._init_vosk_model(vosk_model_path)
        
        # Инициализация SpeechRecognition
        if SR_AVAILABLE and self.recognition_mode in ["google", "hybrid"]:
            self._init_speech_recognition()
        
        # Инициализация аудиоустройства
        self._init_audio_device()
        
        print("[VOICE] ✅ Все компоненты инициализированы")
    
    def _init_vosk_model(self, model_path: Optional[str] = None):
        """Инициализация модели Vosk"""
        if not VOSK_AVAILABLE:
            print("[VOICE] ⚠️ Vosk недоступен, пропускаем инициализацию")
            return
        
        # Поиск модели Vosk
        model_paths = [
            model_path,
            "models/vosk-model-ru-0.22",
            "vosk-model-ru-0.22",
            os.path.expanduser("~/.vosk/vosk-model-ru-0.22"),
            "/usr/share/vosk/vosk-model-ru-0.22",
        ]
        
        for path in model_paths:
            if path and os.path.exists(path):
                try:
                    print(f"[VOICE] Загрузка модели Vosk: {path}")
                    self.vosk_model = Model(path)
                    self.vosk_recognizer = KaldiRecognizer(self.vosk_model, self.sample_rate)
                    self.vosk_recognizer.SetWords(True)
                    print(f"[VOICE] ✅ Модель Vosk загружена: {path}")
                    return
                except Exception as e:
                    print(f"[VOICE] Ошибка загрузки модели {path}: {e}")
        
        print("[VOICE] ⚠️ Модель Vosk не найдена, онлайн режим будет основным")
        if self.recognition_mode == "vosk":
            self.recognition_mode = "google"
    
    def _init_speech_recognition(self):
        """Инициализация SpeechRecognition"""
        if not SR_AVAILABLE:
            print("[VOICE] ⚠️ SpeechRecognition недоступен")
            return
        
        try:
            self.sr_recognizer = sr.Recognizer()
            # Оптимизированные настройки для быстрой речи
            self.sr_recognizer.pause_threshold = 0.5
            self.sr_recognizer.phrase_threshold = 0.3
            self.sr_recognizer.non_speaking_duration = 0.3
            self.sr_recognizer.energy_threshold = self.audio_settings.energy_threshold
            self.sr_recognizer.dynamic_energy_threshold = True
            
            print("[VOICE] ✅ SpeechRecognition инициализирован")
        except Exception as e:
            print(f"[VOICE] Ошибка инициализации SpeechRecognition: {e}")
    
    def _init_audio_device(self):
        """Инициализация аудиоустройства"""
        print("[VOICE] Поиск аудиоустройств...")
        
        try:
            if PYAUDIO_AVAILABLE:
                self.pyaudio_instance = pyaudio.PyAudio()
                device_count = self.pyaudio_instance.get_device_count()
                print(f"[VOICE] Найдено аудиоустройств: {device_count}")
                
                for i in range(device_count):
                    device_info = self.pyaudio_instance.get_device_info_by_index(i)
                    if device_info.get('maxInputChannels', 0) > 0:
                        print(f"  [{i}] {device_info.get('name')}")
                
                # Используем устройство по умолчанию
                self.audio_device_index = self.audio_device_index or self.pyaudio_instance.get_default_input_device_info().get('index')
                print(f"[VOICE] Используется устройство: {self.audio_device_index}")
            
            elif SOUNDDEVICE_AVAILABLE:
                devices = sd.query_devices()
                print(f"[VOICE] Найдено SoundDevice устройств: {len(devices)}")
                
            else:
                print("[VOICE] ⚠️ Нет доступных аудио библиотек, будет использоваться консольный ввод")
                self.recognition_mode = "simple"
                
        except Exception as e:
            print(f"[VOICE] Ошибка инициализации аудио: {e}")
            self.recognition_mode = "simple"
    
    def _print_system_info(self):
        """Вывод информации о системе"""
        print("\n[VOICE] 📊 СИСТЕМНАЯ ИНФОРМАЦИЯ")
        print(f"   • Wake word: '{self.wake_word}'")
        print(f"   • Чувствительность: {self.sensitivity:.1f}")
        print(f"   • Режим распознавания: {self.recognition_mode}")
        print(f"   • Частота дискретизации: {self.sample_rate} Hz")
        print(f"   • Vosk доступен: {'✅' if VOSK_AVAILABLE else '❌'}")
        print(f"   • Google Speech доступен: {'✅' if SR_AVAILABLE else '❌'}")
        print(f"   • PyAudio доступен: {'✅' if PYAUDIO_AVAILABLE else '❌'}")
        print(f"   • SoundDevice доступен: {'✅' if SOUNDDEVICE_AVAILABLE else '❌'}")
        print(f"   • Аналитика: {'✅' if self.enable_analytics else '❌'}")
    
    def _check_wake_word(self, text: str, confidence: float = 1.0) -> Tuple[bool, str]:
        """
        Улучшенная проверка wake word с fuzzy matching и confidence scoring
        
        Args:
            text: Распознанный текст
            confidence: Уверенность распознавания (0.0-1.0)
            
        Returns:
            Tuple[bool, str]: (найден ли wake word, очищенный текст)
        """
        if not text or len(text.strip()) < 2:
            return False, ""
        
        text_lower = text.lower().strip()
        words = text_lower.split()
        
        # 1. Точное совпадение с любым вариантом
        for variant in self.WAKE_WORD_VARIANTS:
            if variant in text_lower:
                print(f"[VOICE] 🔍 Wake word найден (точное): '{variant}'")
                return True, text_lower.replace(variant, "", 1).strip()
        
        # 2. Частичное совпадение (первые 3 символа)
        for word in words:
            if len(word) >= 3:
                for variant in self.WAKE_WORD_VARIANTS:
                    if (word.startswith(variant[:3]) or 
                        variant.startswith(word[:3])):
                        print(f"[VOICE] 🔍 Wake word найден (частичное): '{word}' ~ '{variant}'")
                        return True, text_lower.replace(word, "", 1).strip()
        
        # 3. Проверка начала текста
        for variant in self.WAKE_WORD_VARIANTS:
            if text_lower.startswith(variant):
                print(f"[VOICE] 🔍 Wake word найден (начало): '{variant}'")
                return True, text_lower[len(variant):].strip()
        
        # 4. Fuzzy matching по символам
        wake_chars = set(self.wake_word)
        for word in words:
            if len(word) >= 3:
                word_chars = set(word)
                overlap = len(wake_chars & word_chars)
                if overlap >= len(wake_chars) * 0.7:  # 70% совпадение символов
                    print(f"[VOICE] 🔍 Wake word найден (fuzzy): '{word}'")
                    return True, text_lower.replace(word, "", 1).strip()
        
        # 5. Проверка быстрой речи (слитные слова)
        for variant in self.WAKE_WORD_VARIANTS:
            if len(variant) >= 3 and text_lower[:3] == variant[:3]:
                # Пытаемся найти где заканчивается wake word
                for i in range(3, min(len(text_lower), len(variant) + 2)):
                    if text_lower[:i] == variant[:i]:
                        print(f"[VOICE] 🔍 Wake word найден (быстрая речь): '{variant[:i]}'")
                        return True, text_lower[i:].strip()
        
        return False, text_lower
    
    def _extract_command(self, text: str) -> str:
        """
        Извлечение команды из текста с обработкой быстрой речи
        
        Args:
            text: Текст для обработки
            
        Returns:
            str: Извлеченная команда
        """
        if not text:
            return ""
        
        text_lower = text.lower().strip()
        
        # Проверка быстрых команд
        for cmd_key, cmd_value in self.QUICK_COMMANDS.items():
            if cmd_key in text_lower:
                return cmd_value
        
        # Попытка извлечь команду после wake word
        is_wake, cleaned_text = self._check_wake_word(text_lower)
        if is_wake:
            return cleaned_text
        
        # Если wake word не найден, но текст похож на команду
        if len(text_lower.split()) <= 5:  # Короткие фразы
            return text_lower
        
        return ""
    
    def _recognize_with_vosk(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """Распознавание с помощью Vosk"""
        if not self.vosk_recognizer:
            return None
        
        try:
            if self.vosk_recognizer.AcceptWaveform(audio_data):
                result = json.loads(self.vosk_recognizer.Result())
                text = result.get('text', '').strip()
                if text:
                    return {
                        'text': text,
                        'confidence': 0.9,
                        'source': 'vosk',
                        'timestamp': time.time()
                    }
            else:
                partial = json.loads(self.vosk_recognizer.PartialResult())
                text = partial.get('partial', '').strip()
                if text and len(text) > 3:
                    return {
                        'text': text,
                        'confidence': 0.6,
                        'source': 'vosk_partial',
                        'timestamp': time.time()
                    }
        except Exception as e:
            logger.error(f"Ошибка Vosk распознавания: {e}")
        
        return None
    
    def _recognize_with_google(self, audio_data) -> Optional[Dict[str, Any]]:
        """Распознавание с помощью Google Speech API"""
        if not self.sr_recognizer:
            return None
        
        try:
            text = self.sr_recognizer.recognize_google(audio_data, language="ru-RU")
            return {
                'text': text,
                'confidence': 0.85,
                'source': 'google',
                'timestamp': time.time()
            }
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            logger.error(f"Ошибка Google Speech API: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка Google распознавания: {e}")
            return None
    
    def _process_audio_chunk(self, audio_data: bytes):
        """Обработка аудиочанка и распознавание речи"""
        # Обновляем время последнего аудио
        self.last_audio_time = time.time()
        
        # Распознавание в зависимости от режима
        results = []
        
        if self.recognition_mode in ["vosk", "hybrid"] and self.vosk_recognizer:
            vosk_result = self._recognize_with_vosk(audio_data)
            if vosk_result:
                results.append(vosk_result)
        
        # Для Google нужно преобразовать аудио в правильный формат
        if self.recognition_mode in ["google", "hybrid"] and self.sr_recognizer:
            try:
                # Создаем AudioData для SpeechRecognition
                import wave
                import io
                
                # Преобразуем bytes в AudioData
                audio_data_sr = sr.AudioData(
                    audio_data, 
                    self.sample_rate, 
                    2  # sample width in bytes
                )
                
                google_result = self._recognize_with_google(audio_data_sr)
                if google_result:
                    results.append(google_result)
            except Exception as e:
                logger.error(f"Ошибка подготовки аудио для Google: {e}")
        
        # Выбор лучшего результата
        if results:
            # Выбираем результат с наибольшей уверенностью
            best_result = max(results, key=lambda x: x.get('confidence', 0))
            self._process_recognition_result(best_result)
    
    def _process_recognition_result(self, result: Dict[str, Any]):
        """Обработка результата распознавания"""
        if not result or 'text' not in result:
            return
        
        text = result['text']
        confidence = result.get('confidence', 0.5)
        source = result.get('source', 'unknown')
        
        # Обновляем статистику
        self.stats.total_phrases += 1
        if source == 'vosk':
            self.stats.vosk_success += 1
        elif source == 'google':
            self.stats.google_success += 1
        
        self.stats.avg_confidence = (
            (self.stats.avg_confidence * (self.stats.total_phrases - 1) + confidence) 
            / self.stats.total_phrases
        )
        
        # Сохраняем в историю
        history_entry = {
            'text': text,
            'confidence': confidence,
            'source': source,
            'timestamp': time.time(),
            'mode': self.recognition_mode,
            'sensitivity': self.sensitivity
        }
        
        self.recognition_history.append(history_entry)
        if len(self.recognition_history) > self.max_history:
            self.recognition_history.pop(0)
        
        # Выводим информацию о распознавании
        source_icon = "🎤" if source == 'vosk' else "🌐"
        print(f"{source_icon} [VOICE] Распознано: '{text}' (доверие: {confidence:.1%})")
        
        # Проверяем wake word
        is_wake, cleaned_text = self._check_wake_word(text, confidence)
        
        if is_wake:
            self.stats.wake_detected += 1
            print(f"🔔 [VOICE] Wake word обнаружен! Активация на {self.activation_timeout}с")
            
            # Активируем режим прослушивания
            self.is_active = True
            self.last_activation_time = time.time()
            
            # Вызываем коллбэк wake word
            if self.wake_callback:
                try:
                    self.wake_callback()
                except Exception as e:
                    logger.error(f"Ошибка в wake коллбэке: {e}")
            
            # Если есть команда после wake word
            if cleaned_text:
                self._handle_command(cleaned_text, confidence)
        
        # Если уже в активном режиме, обрабатываем как команду
        elif self.is_active:
            # Проверяем таймаут активации
            if time.time() - self.last_activation_time > self.activation_timeout:
                print(f"[VOICE] Таймаут активации ({self.activation_timeout}с)")
                self.is_active = False
            else:
                self._handle_command(text, confidence)
    
    def _handle_command(self, command: str, confidence: float):
        """Обработка команды"""
        if not command or len(command.strip()) < 2:
            return
        
        # Извлекаем чистую команду
        clean_command = self._extract_command(command)
        if not clean_command:
            return
        
        print(f"💬 [VOICE] Команда: '{clean_command}' (доверие: {confidence:.1%})")
        
        # Добавляем в очередь с приоритетом
        priority = 0 if clean_command in self.QUICK_COMMANDS.values() else 1
        self.command_queue.put((priority, time.time(), clean_command))
        
        # Вызываем коллбэк команды
        if self.command_callback:
            try:
                self.command_callback(clean_command)
            except Exception as e:
                logger.error(f"Ошибка в command коллбэке: {e}")
                if self.error_callback:
                    self.error_callback(e)
    
    def _listen_loop_vosk(self):
        """Цикл прослушивания с Vosk через PyAudio"""
        print(f"[VOICE] Запуск Vosk прослушивания... (скажите '{self.wake_word}')")
        
        try:
            self.audio_stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=self.audio_settings.channels,
                rate=self.audio_settings.sample_rate,
                input=True,
                input_device_index=self.audio_device_index,
                frames_per_buffer=self.audio_settings.chunk_size,
                stream_callback=self._audio_callback_pyaudio
            )
            
            self.audio_stream.start_stream()
            
            while self.is_listening and self.audio_stream.is_active():
                time.sleep(0.1)
                
        except Exception as e:
            print(f"[VOICE] Ошибка аудиопотока Vosk: {e}")
            self._fallback_to_google()
        finally:
            if self.audio_stream:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
    
    def _audio_callback_pyaudio(self, in_data, frame_count, time_info, status):
        """Коллбэк для PyAudio"""
        if status:
            logger.warning(f"Аудио статус: {status}")
        
        self.audio_buffer.put(in_data)
        return (in_data, pyaudio.paContinue)
    
    def _audio_processor_loop(self):
        """Цикл обработки аудиобуфера"""
        print("[VOICE] Запуск процессора аудио...")
        
        while self.is_listening:
            try:
                audio_data = self.audio_buffer.get(timeout=0.5)
                self._process_audio_chunk(audio_data)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Ошибка обработки аудио: {e}")
    
    def _listen_loop_google(self):
        """Цикл прослушивания с Google Speech через SpeechRecognition"""
        print(f"[VOICE] Запуск Google прослушивания... (скажите '{self.wake_word}')")
        
        try:
            with sr.Microphone(
                device_index=self.audio_device_index,
                sample_rate=self.audio_settings.sample_rate
            ) as source:
                # Калибровка фонового шума
                print("[VOICE] Калибровка микрофона...")
                self.sr_recognizer.adjust_for_ambient_noise(source, duration=1)
                print(f"[VOICE] Порог энергии: {self.sr_recognizer.energy_threshold}")
                
                while self.is_listening:
                    try:
                        # Слушаем микрофон
                        audio = self.sr_recognizer.listen(
                            source,
                            timeout=2,
                            phrase_time_limit=5
                        )
                        
                        # Распознаем с Google
                        result = self._recognize_with_google(audio)
                        if result:
                            self._process_recognition_result(result)
                            
                    except sr.WaitTimeoutError:
                        continue
                    except Exception as e:
                        logger.error(f"Ошибка прослушивания Google: {e}")
                        
        except OSError as e:
            print(f"[VOICE] Нет аудиоустройств: {e}")
            print("[VOICE] Переключение на простой режим ввода...")
            self._fallback_to_simple()
        except Exception as e:
            print(f"[VOICE] Ошибка микрофона: {e}")
            self._fallback_to_simple()
    
    def _listen_loop_simple(self):
        """Цикл простого консольного ввода"""
        print(f"[VOICE] Простой режим. Введите команды вручную.")
        print(f"[VOICE] Для активации введите: '{self.wake_word}'")
        
        while self.is_listening:
            try:
                user_input = input("[Голос] > ").strip()
                
                if not user_input:
                    continue
                
                # Создаем искусственный результат распознавания
                result = {
                    'text': user_input,
                    'confidence': 1.0,
                    'source': 'console',
                    'timestamp': time.time()
                }
                
                self._process_recognition_result(result)
                
            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                logger.error(f"Ошибка ввода: {e}")
    
    def _fallback_to_google(self):
        """Переключение на Google Speech как резерв"""
        print("[VOICE] Переключение на Google Speech...")
        self.recognition_mode = "google"
        self.stop()
        time.sleep(1)
        self.start()
    
    def _fallback_to_simple(self):
        """Переключение на простой режим"""
        print("[VOICE] Переключение на простой режим ввода...")
        self.recognition_mode = "simple"
        self.stop()
        time.sleep(1)
        self.start()
    
    def _analytics_loop(self):
        """Цикл сбора аналитики"""
        if not self.enable_analytics:
            return
        
        print("[VOICE] Запуск системы аналитики...")
        
        while self.is_listening:
            try:
                time.sleep(30)  # Каждые 30 секунд
                
                # Расчет качества аудио
                if self.last_audio_time > 0:
                    time_since_audio = time.time() - self.last_audio_time
                    audio_quality = 1.0 - min(time_since_audio / 60, 1.0)  # Ухудшение со временем
                    self.stats.audio_quality = audio_quality
                
                # Логирование статистики
                if self.stats.total_phrases > 0:
                    logger.info(f"Статистика: {self.stats.total_phrases} фраз, "
                               f"{self.stats.wake_detected} wake, "
                               f"точность: {self.stats.avg_confidence:.1%}")
                    
            except Exception as e:
                logger.error(f"Ошибка аналитики: {e}")
    
    def start(self):
        """Запуск системы голосового ввода"""
        if self.is_listening:
            print("[VOICE] Система уже запущена")
            return
        
        print("[VOICE] 🚀 Запуск системы голосового ввода...")
        self.is_listening = True
        
        # Запускаем потоки в зависимости от режима
        if self.recognition_mode == "vosk" and VOSK_AVAILABLE and PYAUDIO_AVAILABLE:
            self.listener_thread = threading.Thread(target=self._listen_loop_vosk, daemon=True)
            self.processor_thread = threading.Thread(target=self._audio_processor_loop, daemon=True)
            self.processor_thread.start()
            
        elif self.recognition_mode == "google" and SR_AVAILABLE:
            self.listener_thread = threading.Thread(target=self._listen_loop_google, daemon=True)
            
        elif self.recognition_mode == "hybrid":
            # Запускаем оба режима
            self.listener_thread = threading.Thread(target=self._listen_loop_vosk, daemon=True)
            self.processor_thread = threading.Thread(target=self._audio_processor_loop, daemon=True)
            self.processor_thread.start()
            
        else:  # simple mode
            self.listener_thread = threading.Thread(target=self._listen_loop_simple, daemon=True)
        
        # Запускаем основной поток прослушивания
        if self.listener_thread:
            self.listener_thread.start()
        
        # Запускаем аналитику
        if self.enable_analytics:
            self.analytics_thread = threading.Thread(target=self._analytics_loop, daemon=True)
            self.analytics_thread.start()
        
        print(f"[VOICE] ✅ Система запущена в режиме: {self.recognition_mode}")
        print(f"[VOICE] Wake word: '{self.wake_word}', чувствительность: {self.sensitivity}")
    
    def stop(self):
        """Остановка системы голосового ввода"""
        if not self.is_listening:
            return
        
        print("[VOICE] Остановка системы голосового ввода...")
        self.is_listening = False
        self.is_active = False
        
        # Останавливаем аудиопоток
        if self.audio_stream and self.audio_stream.is_active():
            self.audio_stream.stop_stream()
            self.audio_stream.close()
        
        # Останавливаем PyAudio
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
        
        # Ожидаем завершения потоков
        threads = [self.listener_thread, self.processor_thread, self.analytics_thread]
        for thread in threads:
            if thread and thread.is_alive():
                thread.join(timeout=2.0)
        
        # Сохраняем статистику
        if self.enable_analytics:
            self._save_stats()
        
        print("[VOICE] ✅ Система остановлена")
    
    def calibrate_microphone(self):
        """Калибровка микрофона для текущих условий"""
        if self.is_calibrating:
            return
        
        self.is_calibrating = True
        print("[VOICE] Калибровка микрофона...")
        
        try:
            if self.sr_recognizer:
                with sr.Microphone() as source:
                    # Быстрая калибровка фонового шума
                    self.sr_recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    # Тестовое распознавание
                    print("[VOICE] Скажите тестовую фразу...")
                    audio = self.sr_recognizer.listen(source, timeout=3)
                    
                    try:
                        text = self.sr_recognizer.recognize_google(audio, language="ru-RU")
                        print(f"[VOICE] Распознано: '{text}'")
                        
                        # Автонастройка порога на основе энергии звука
                        if hasattr(audio, 'frame_data'):
                            import numpy as np
                            audio_data = np.frombuffer(audio.frame_data, dtype=np.int16)
                            energy = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
                            
                            # Устанавливаем порог на 60% от энергии тестовой фразы
                            new_threshold = int(energy * 0.6)
                            if 1000 < new_threshold < 10000:
                                self.sr_recognizer.energy_threshold = new_threshold
                                self.audio_settings.energy_threshold = new_threshold
                                print(f"[VOICE] Автонастройка порога: {new_threshold}")
                                
                    except sr.UnknownValueError:
                        print("[VOICE] Речь не распознана, используем настройки по умолчанию")
                        
        except Exception as e:
            print(f"[VOICE] Ошибка калибровки: {e}")
        finally:
            self.is_calibrating = False
            print("[VOICE] Калибровка завершена")
    
    def set_command_callback(self, callback: Callable[[str], None]):
        """Установка callback для обработки команд"""
        self.command_callback = callback
        print("[VOICE] Callback команд установлен")
    
    def set_wake_callback(self, callback: Callable[[], None]):
        """Установка callback для обработки wake word"""
        self.wake_callback = callback
        print("[VOICE] Callback wake word установлен")
    
    def set_error_callback(self, callback: Callable[[Exception], None]):
        """Установка callback для обработки ошибок"""
        self.error_callback = callback
        print("[VOICE] Callback ошибок установлен")
    
    def set_sensitivity(self, sensitivity: float):
        """Установка чувствительности (0.0-1.0)"""
        self.sensitivity = max(0.1, min(1.0, sensitivity))
        self.audio_settings.energy_threshold = int(1500 + (3500 * (1 - self.sensitivity)))
        
        if self.sr_recognizer:
            self.sr_recognizer.energy_threshold = self.audio_settings.energy_threshold
        
        print(f"[VOICE] Чувствительность изменена: {self.sensitivity}, "
              f"порог: {self.audio_settings.energy_threshold}")
    
    def set_activation_timeout(self, timeout: float):
        """Установка таймаута активации в секундах"""
        self.activation_timeout = max(1.0, timeout)
        print(f"[VOICE] Таймаут активации установлен: {timeout}с")
    
    def get_command(self) -> Optional[str]:
        """Получение следующей команды из очереди"""
        try:
            priority, timestamp, command = self.command_queue.get_nowait()
            return command
        except queue.Empty:
            return None
    
    def get_recognition_stats(self) -> Dict[str, Any]:
        """Получение статистики распознавания"""
        stats_dict = asdict(self.stats)
        
        # Добавляем дополнительную информацию
        stats_dict.update({
            'mode': self.recognition_mode,
            'sensitivity': self.sensitivity,
            'is_active': self.is_active,
            'is_listening': self.is_listening,
            'history_size': len(self.recognition_history),
            'queue_size': self.command_queue.qsize(),
            'activation_timeout': self.activation_timeout,
            'time_since_activation': time.time() - self.last_activation_time if self.last_activation_time > 0 else -1,
            'audio_available': PYAUDIO_AVAILABLE or SOUNDDEVICE_AVAILABLE,
        })
        
        return stats_dict
    
    def get_recent_history(self, count: int = 10) -> List[Dict[str, Any]]:
        """Получение последних записей истории"""
        return self.recognition_history[-count:] if self.recognition_history else []
    
    def clear_history(self):
        """Очистка истории распознавания"""
        self.recognition_history.clear()
        print("[VOICE] История распознавания очищена")
    
    def _save_stats(self):
        """Сохранение статистики в файл"""
        if not self.enable_analytics:
            return
        
        try:
            stats_file = "voice_stats.json"
            stats_data = {
                'timestamp': time.time(),
                'stats': asdict(self.stats),
                'settings': {
                    'wake_word': self.wake_word,
                    'sensitivity': self.sensitivity,
                    'mode': self.recognition_mode,
                    'sample_rate': self.sample_rate,
                },
                'recent_history': self.get_recent_history(20)
            }
            
            import json
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, indent=2, ensure_ascii=False)
                
            print(f"[VOICE] Статистика сохранена в {stats_file}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения статистики: {e}")
    
    def stop_listening(self):
        """Алиас для stop (совместимость)"""
        self.stop()
    
    def manual_activate(self, duration: float = 10.0):
        """Ручная активация режима прослушивания"""
        self.is_active = True
        self.last_activation_time = time.time()
        self.activation_timeout = duration
        print(f"[VOICE] Ручная активация на {duration} секунд")


# Простой режим для тестирования (без микрофона)
class SimpleVoiceInput:
    """
    Упрощенная версия голосового ввода для тестирования
    Использует консольный ввод вместо микрофона
    """
    
    def __init__(self, wake_word: str = "ирис", sensitivity: float = 0.8):
        print("[SimpleVoice] Инициализация упрощенного голосового ввода...")
        self.wake_word = wake_word
        self.sensitivity = sensitivity
        self.command_callback = None
        self.wake_callback = None
        self.is_running = False
        self.input_thread = None
    
    def set_command_callback(self, callback):
        self.command_callback = callback
    
    def set_wake_callback(self, callback):
        self.wake_callback = callback
    
    def _input_loop(self):
        print(f"[SimpleVoice] Введите команды. Для активации: '{self.wake_word}'")
        
        while self.is_running:
            try:
                user_input = input("[Голосовой ввод] > ").strip().lower()
                
                if not user_input:
                    continue
                
                # Проверка на wake word
                if self.wake_word in user_input:
                    print(f"[SimpleVoice] Wake word обнаружен: '{self.wake_word}'")
                    if self.wake_callback:
                        self.wake_callback()
                
                # Передача команды
                if self.command_callback:
                    self.command_callback(user_input)
                    
            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                print(f"[SimpleVoice] Ошибка ввода: {e}")
    
    def start(self):
        self.is_running = True
        self.input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self.input_thread.start()
        print("[SimpleVoice] Упрощенный голосовой ввод запущен")
    
    def stop(self):
        self.is_running = False
        if self.input_thread and self.input_thread.is_alive():
            self.input_thread.join(timeout=1.0)
        print("[SimpleVoice] Упрощенный голосовой ввод остановлен")


# Фабричная функция для создания экземпляра
def create_voice_input(wake_word: str = "ирис", 
                       sensitivity: float = 0.8,
                       mode: str = "auto",
                       **kwargs) -> VoiceInput:
    """
    Создание экземпляра голосового ввода
    
    Args:
        wake_word: Ключевое слово активации
        sensitivity: Чувствительность (0.1-1.0)
        mode: Режим распознавания (auto, vosk, google, hybrid, simple)
        **kwargs: Дополнительные аргументы
        
    Returns:
        VoiceInput или SimpleVoiceInput
    """
    print(f"Создание VoiceInput: wake_word='{wake_word}', mode={mode}")
    
    # Проверяем доступность компонентов
    has_audio = PYAUDIO_AVAILABLE or SOUNDDEVICE_AVAILABLE
    has_vosk = VOSK_AVAILABLE
    has_google = SR_AVAILABLE
    
    # Если режим auto, определяем лучший доступный
    if mode == "auto":
        if has_vosk and has_audio:
            mode = "vosk"
        elif has_google and has_audio:
            mode = "google"
        else:
            mode = "simple"
    
    # Если запрошен сложный режим, но нет компонентов - упрощаем
    if mode in ["vosk", "hybrid"] and not has_vosk:
        print("⚠️ Vosk недоступен, переключаемся на Google или простой режим")
        mode = "google" if has_google else "simple"
    
    if mode == "google" and not has_google:
        print("⚠️ Google Speech недоступен, переключаемся на простой режим")
        mode = "simple"
    
    # Если запрошен любой аудио режим, но нет аудиоустройств
    if mode in ["vosk", "google", "hybrid"] and not has_audio:
        print("⚠️ Аудиоустройства недоступны, переключаемся на простой режим")
        mode = "simple"
    
    # Создаем экземпляр
    if mode == "simple":
        return SimpleVoiceInput(wake_word, sensitivity)
    else:
        return VoiceInput(
            wake_word=wake_word,
            sensitivity=sensitivity,
            recognition_mode=mode,
            **kwargs
        )


# Тестирование модуля
if __name__ == "__main__":
    print("=" * 60)
    print("🔊 ТЕСТ МОДУЛЯ ГОЛОСОВОГО ВВОДА")
    print("=" * 60)
    
    def test_wake():
        print("\n🎯 ТЕСТ: Wake word обнаружен!")
    
    def test_command(command: str):
        print(f"\n💬 ТЕСТ: Получена команда: '{command}'")
    
    def test_error(error: Exception):
        print(f"\n⚠️ ТЕСТ: Ошибка: {error}")
    
    try:
        # Создаем экземпляр
        voice = create_voice_input(
            wake_word="ирис",
            sensitivity=0.8,
            mode="auto",
            enable_analytics=True
        )
        
        # Устанавливаем коллбэки
        voice.set_wake_callback(test_wake)
        voice.set_command_callback(test_command)
        voice.set_error_callback(test_error)
        
        # Запускаем
        print("\n▶️ Запуск системы...")
        voice.start()
        
        print("\n📝 Инструкция:")
        print("   • Скажите 'Ирис' для активации")
        print("   • Затем произнесите команду")
        print("   • Или введите команду вручную (в простом режиме)")
        print("   • Скажите 'стоп' для остановки теста")
        print("\n⏳ Тест на 30 секунд...")
        
        # Ждем 30 секунд или команду стоп
        import time
        start_time = time.time()
        
        while time.time() - start_time < 30:
            time.sleep(1)
            
            # Проверяем команду стоп
            cmd = voice.get_command()
            if cmd == "stop":
                print("\n🛑 Получена команда стоп")
                break
            
            # Раз в 5 секунд выводим статистику
            if int(time.time() - start_time) % 5 == 0:
                stats = voice.get_recognition_stats()
                print(f"\n📊 Статистика: {stats['total_phrases']} фраз, "
                      f"{stats['wake_detected']} wake, "
                      f"очередь: {stats['queue_size']}")
        
        # Останавливаем
        print("\n⏹️ Остановка системы...")
        voice.stop()
        
        # Финальная статистика
        print("\n" + "=" * 60)
        print("📈 ФИНАЛЬНАЯ СТАТИСТИКА")
        print("=" * 60)
        
        stats = voice.get_recognition_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        print("\n" + "=" * 60)
        print("✅ Тест завершен успешно!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Ошибка теста: {e}")
        import traceback
        traceback.print_exc()