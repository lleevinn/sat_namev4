"""
Iris Voice Input - Улучшенное распознавание голоса с Vosk
Офлайн распознавание с высокой чувствительностью к wake-word 'Ирис'
"""
import threading
import time
import queue
import os
import json
import logging
from typing import Optional, Callable, List
from pathlib import Path

try:
    from vosk import Model, KaldiRecognizer, SetLogLevel
    SetLogLevel(-1)
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    print("[VOICE] Vosk не установлен. Установите: pip install vosk")

SOUNDDEVICE_AVAILABLE = False
sd = None
np = None
try:
    import numpy as np
    import sounddevice as sd
    sd.query_devices()
    SOUNDDEVICE_AVAILABLE = True
except (ImportError, OSError, Exception) as e:
    SOUNDDEVICE_AVAILABLE = False
    sd = None
    try:
        import numpy as np
    except ImportError:
        np = None
    print(f"[VOICE] sounddevice недоступен: {e}")

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False
    print("[VOICE] speech_recognition не установлен. Установите: pip install SpeechRecognition")

logger = logging.getLogger('VoiceInput')


class VoiceInput:
    """
    Улучшенный модуль распознавания голоса
    Поддерживает Vosk (офлайн) и Google Speech Recognition (онлайн)
    """
    
    WAKE_WORD_VARIANTS = [
        'ирис', 'iris', 'ири', 'ириска', 'ирисс', 'ириса',
        'айрис', 'арис', 'ириш', 'ирись', 'рис', 'эрис'
    ]
    
    def __init__(self, 
                 wake_word: str = "ирис",
                 sensitivity: float = 0.7,
                 use_vosk: bool = True,
                 vosk_model_path: str = None,
                 sample_rate: int = 16000):
        """
        Инициализация распознавания голоса
        
        Args:
            wake_word: Ключевое слово для активации
            sensitivity: Чувствительность (0.0-1.0)
            use_vosk: Использовать Vosk для офлайн распознавания
            vosk_model_path: Путь к модели Vosk
            sample_rate: Частота дискретизации
        """
        self.wake_word = wake_word.lower()
        self.sensitivity = max(0.1, min(1.0, sensitivity))
        self.sample_rate = sample_rate
        self.use_vosk = use_vosk and VOSK_AVAILABLE
        
        self.command_queue = queue.Queue()
        self.is_listening = False
        self.is_calibrating = False
        self.listener_thread: Optional[threading.Thread] = None
        self.command_callback: Optional[Callable] = None
        
        self.recognition_history: List[str] = []
        self.max_history = 50
        self.wake_word_detected_count = 0
        self.total_phrases_count = 0
        
        self.vosk_model = None
        self.recognizer = None
        
        self.energy_threshold = 1500 + (3500 * (1 - sensitivity))
        self.silence_threshold = 0.3
        self.phrase_timeout = 3.0
        
        if self.use_vosk:
            self._init_vosk(vosk_model_path)
        
        if SR_AVAILABLE:
            self._init_speech_recognition()
        
        print(f"[VOICE] Инициализирован с wake word: '{self.wake_word}'")
        print(f"[VOICE] Чувствительность: {self.sensitivity}")
        print(f"[VOICE] Vosk доступен: {VOSK_AVAILABLE}")
        print(f"[VOICE] SoundDevice доступен: {SOUNDDEVICE_AVAILABLE}")
    
    def _init_vosk(self, model_path: str = None):
        """Инициализация Vosk модели"""
        if not VOSK_AVAILABLE:
            return
        
        model_paths = [
            model_path,
            'models/vosk-model-small-ru',
            'vosk-model-small-ru-0.22',
            os.path.expanduser('~/.vosk/vosk-model-small-ru'),
            '/usr/share/vosk/vosk-model-small-ru',
        ]
        
        for path in model_paths:
            if path and os.path.exists(path):
                try:
                    self.vosk_model = Model(path)
                    self.recognizer = KaldiRecognizer(self.vosk_model, self.sample_rate)
                    self.recognizer.SetWords(True)
                    print(f"[VOICE] Vosk модель загружена: {path}")
                    return
                except Exception as e:
                    print(f"[VOICE] Ошибка загрузки модели {path}: {e}")
        
        print("[VOICE] Vosk модель не найдена. Используется онлайн распознавание.")
        self.use_vosk = False
    
    def _init_speech_recognition(self):
        """Инициализация speech_recognition"""
        if not SR_AVAILABLE:
            return
        
        self.sr_recognizer = sr.Recognizer()
        self.sr_recognizer.pause_threshold = 0.5
        self.sr_recognizer.phrase_threshold = 0.3
        self.sr_recognizer.non_speaking_duration = 0.3
        self.sr_recognizer.energy_threshold = self.energy_threshold
        self.sr_recognizer.dynamic_energy_threshold = False
    
    def _check_wake_word(self, text: str) -> bool:
        """
        Улучшенная проверка wake word с fuzzy matching
        
        Args:
            text: Распознанный текст
            
        Returns:
            bool: True если wake word обнаружен
        """
        if not text:
            return False
        
        text_lower = text.lower().strip()
        words = text_lower.split()
        
        for variant in self.WAKE_WORD_VARIANTS:
            if variant in text_lower:
                logger.debug(f"Wake word найден (точное): '{variant}' в '{text}'")
                return True
        
        for word in words:
            if len(word) >= 3:
                for variant in self.WAKE_WORD_VARIANTS:
                    if word.startswith(variant[:3]) or variant.startswith(word[:3]):
                        logger.debug(f"Wake word найден (частичное): '{word}' ~ '{variant}'")
                        return True
        
        if text_lower.startswith(self.wake_word[:2]):
            logger.debug(f"Wake word найден (начало): '{text_lower[:5]}...'")
            return True
        
        wake_chars = set(self.wake_word)
        for word in words:
            if len(word) >= 3:
                word_chars = set(word)
                overlap = len(wake_chars & word_chars)
                if overlap >= len(wake_chars) * 0.7:
                    logger.debug(f"Wake word найден (символы): '{word}'")
                    return True
        
        return False
    
    def _extract_command(self, text: str) -> str:
        """
        Извлечение команды из текста после wake word
        
        Args:
            text: Распознанный текст
            
        Returns:
            str: Команда или пустая строка
        """
        if not text:
            return ""
        
        text_lower = text.lower().strip()
        
        for variant in sorted(self.WAKE_WORD_VARIANTS, key=len, reverse=True):
            if variant in text_lower:
                parts = text_lower.split(variant, 1)
                if len(parts) > 1:
                    return parts[1].strip()
        
        if text_lower.startswith(self.wake_word):
            return text_lower[len(self.wake_word):].strip()
        
        return text_lower
    
    def _recognize_with_vosk(self, audio_data: bytes) -> Optional[str]:
        """Распознавание с помощью Vosk"""
        if not self.recognizer:
            return None
        
        try:
            if self.recognizer.AcceptWaveform(audio_data):
                result = json.loads(self.recognizer.Result())
                return result.get('text', '')
            else:
                partial = json.loads(self.recognizer.PartialResult())
                return partial.get('partial', '')
        except Exception as e:
            logger.error(f"Ошибка Vosk: {e}")
            return None
    
    def _recognize_with_google(self, audio) -> Optional[str]:
        """Распознавание с помощью Google Speech API"""
        if not SR_AVAILABLE:
            return None
        
        try:
            text = self.sr_recognizer.recognize_google(audio, language="ru-RU")
            return text
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            logger.error(f"Ошибка Google Speech: {e}")
            return None
    
    def _process_recognition(self, text: str):
        """Обработка распознанного текста"""
        if not text or len(text.strip()) < 2:
            return
        
        self.total_phrases_count += 1
        self.recognition_history.append(text)
        if len(self.recognition_history) > self.max_history:
            self.recognition_history.pop(0)
        
        print(f"[VOICE] Распознано: '{text}'")
        
        if self._check_wake_word(text):
            self.wake_word_detected_count += 1
            print(f"[VOICE] Wake word обнаружен!")
            
            command = self._extract_command(text)
            print(f"[VOICE] Команда: '{command}'")
            
            self.command_queue.put(command)
            
            if self.command_callback:
                try:
                    self.command_callback(command)
                except Exception as e:
                    logger.error(f"Ошибка callback: {e}")
        
        elif text.lower() in ["стоп", "остановись", "выход", "stop", "exit"]:
            print("[VOICE] Команда остановки")
            self.command_queue.put("стоп")
    
    def _listen_loop_vosk(self):
        """Цикл прослушивания с Vosk и sounddevice"""
        if not SOUNDDEVICE_AVAILABLE or sd is None:
            print("[VOICE] sounddevice недоступен, переключение на Google Speech...")
            self._listen_loop_sr()
            return
        
        print(f"[VOICE] Слушаю с Vosk... (Скажите '{self.wake_word}')")
        
        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"Audio status: {status}")
            
            audio_bytes = (indata * 32767).astype(np.int16).tobytes()
            
            text = self._recognize_with_vosk(audio_bytes)
            if text:
                self._process_recognition(text)
        
        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32',
                blocksize=int(self.sample_rate * 0.5),
                callback=audio_callback
            ):
                while self.is_listening:
                    time.sleep(0.1)
        except Exception as e:
            print(f"[VOICE] Ошибка потока аудио: {e}")
            print("[VOICE] Переключение на Google Speech как резерв...")
            self._listen_loop_sr()
    
    def _listen_loop_sr(self):
        """Цикл прослушивания с speech_recognition"""
        if not SR_AVAILABLE:
            print("[VOICE] speech_recognition недоступен")
            print("[VOICE] Голосовой ввод отключен - нет доступных аудио устройств")
            self.is_listening = False
            return
        
        print(f"[VOICE] Слушаю с Google Speech... (Скажите '{self.wake_word}')")
        
        try:
            with sr.Microphone() as source:
                print("[VOICE] Калибровка микрофона...")
                self.sr_recognizer.adjust_for_ambient_noise(source, duration=1)
                print("[VOICE] Калибровка завершена")
                
                while self.is_listening:
                    try:
                        audio = self.sr_recognizer.listen(
                            source,
                            timeout=2,
                            phrase_time_limit=5
                        )
                        
                        text = self._recognize_with_google(audio)
                        if text:
                            self._process_recognition(text)
                        
                    except sr.WaitTimeoutError:
                        continue
                    except Exception as e:
                        logger.error(f"Ошибка прослушивания: {e}")
                        time.sleep(0.5)
        
        except OSError as e:
            print(f"[VOICE] Нет аудио устройств: {e}")
            print("[VOICE] Голосовой ввод отключен - требуется микрофон")
            self.is_listening = False
        except Exception as e:
            print(f"[VOICE] Ошибка инициализации микрофона: {e}")
            self.is_listening = False
    
    def calibrate_microphone(self):
        """Калибровка микрофона"""
        if self.is_calibrating:
            return
        
        self.is_calibrating = True
        print("[VOICE] Калибровка микрофона...")
        
        try:
            if SR_AVAILABLE:
                with sr.Microphone() as source:
                    self.sr_recognizer.adjust_for_ambient_noise(source, duration=1)
                    print(f"[VOICE] Порог энергии: {self.sr_recognizer.energy_threshold}")
        except Exception as e:
            print(f"[VOICE] Ошибка калибровки: {e}")
        finally:
            self.is_calibrating = False
    
    def start(self):
        """Запуск голосового ввода"""
        if self.is_listening:
            print("[VOICE] Уже работает")
            return
        
        self.is_listening = True
        
        if self.use_vosk and self.vosk_model:
            self.listener_thread = threading.Thread(
                target=self._listen_loop_vosk,
                daemon=True
            )
        else:
            self.listener_thread = threading.Thread(
                target=self._listen_loop_sr,
                daemon=True
            )
        
        self.listener_thread.start()
        print("[VOICE] Голосовой ввод запущен")
    
    def stop(self):
        """Остановка голосового ввода"""
        self.is_listening = False
        if self.listener_thread:
            self.listener_thread.join(timeout=2)
        print("[VOICE] Голосовой ввод остановлен")
    
    def stop_listening(self):
        """Остановка прослушивания (алиас для stop)"""
        self.stop()
    
    def get_command(self) -> Optional[str]:
        """Получение следующей команды из очереди"""
        try:
            return self.command_queue.get_nowait()
        except queue.Empty:
            return None
    
    def set_command_callback(self, callback: Callable):
        """Установка callback для обработки команд"""
        self.command_callback = callback
    
    def set_sensitivity(self, sensitivity: float):
        """Установка чувствительности (0.0-1.0)"""
        self.sensitivity = max(0.1, min(1.0, sensitivity))
        self.energy_threshold = 1500 + (3500 * (1 - self.sensitivity))
        
        if SR_AVAILABLE and hasattr(self, 'sr_recognizer'):
            self.sr_recognizer.energy_threshold = self.energy_threshold
        
        print(f"[VOICE] Чувствительность: {self.sensitivity}, порог: {self.energy_threshold}")
    
    def get_recognition_stats(self) -> dict:
        """Получение статистики распознавания"""
        return {
            "total_phrases": self.total_phrases_count,
            "wake_detected": self.wake_word_detected_count,
            "detection_rate": self.wake_word_detected_count / max(1, self.total_phrases_count),
            "recent_phrases": self.recognition_history[-10:],
            "sensitivity": self.sensitivity,
            "energy_threshold": self.energy_threshold
        }


if __name__ == "__main__":
    print("=== Тест Voice Input ===")
    
    def on_command(cmd):
        print(f"\n>>> Получена команда: '{cmd}'\n")
    
    voice = VoiceInput(wake_word="ирис", sensitivity=0.8)
    voice.set_command_callback(on_command)
    
    print("\nСкажите 'Ирис' и команду...")
    voice.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nОстановка...")
        voice.stop()
        
        stats = voice.get_recognition_stats()
        print(f"\nСтатистика:")
        print(f"  Всего фраз: {stats['total_phrases']}")
        print(f"  Wake word: {stats['wake_detected']}")
        print(f"  Точность: {stats['detection_rate']:.1%}")
