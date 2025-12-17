"""
Модуль TTS (Text-to-Speech) движка для IRIS AI Companion
Использует Edge TTS для высококачественного синтеза речи
"""

import asyncio
import threading
import queue
import time
import os
from typing import Optional, Callable, Dict, Any

try:
    import edge_tts
    from edge_tts import VoicesManager
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    print("[TTS] Edge TTS не установлен. Установите: pip install edge-tts")

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("[TTS] Pygame не установлен. Установите: pip install pygame")


class TTSEngine:
    """
    Асинхронный движок синтеза речи с очередью и приоритетами
    Поддерживает эмоциональную окраску и визуальную обратную связь
    """
    
    # Настройки голосов (Edge TTS)
    VOICE_PRESETS = {
        'ru_female_soft': 'ru-RU-SvetlanaNeural',      # Мягкий женский
        'ru_female_energetic': 'ru-RU-DariyaNeural',   # Энергичный женский
        'ru_male_deep': 'ru-RU-DmitryNeural',          # Глубокий мужской
        'en_female': 'en-US-JennyNeural',              # Английский женский
        'en_male': 'en-US-GuyNeural',                  # Английский мужской
    }
    
    # Настройки эмоций (изменение скорости и тона)
    EMOTION_SETTINGS = {
        'neutral': {'rate': 0, 'pitch': 0, 'volume': 100},
        'happy': {'rate': 10, 'pitch': 5, 'volume': 110},
        'excited': {'rate': 15, 'pitch': 10, 'volume': 120},
        'gentle': {'rate': -5, 'pitch': -3, 'volume': 90},
        'sad': {'rate': -10, 'pitch': -5, 'volume': 80},
        'supportive': {'rate': 0, 'pitch': 2, 'volume': 100},
        'tense': {'rate': 5, 'pitch': 0, 'volume': 105},
    }
    
    def __init__(self, 
                 voice: str = 'ru_female_soft',
                 rate: int = 0,
                 volume: float = 0.9,
                 visual_callback: Optional[Callable] = None):
        """
        Инициализация TTS движка
        
        Args:
            voice: Предустановка голоса
            rate: Скорость речи (-50 до 50)
            volume: Громкость (0.0 до 1.0)
            visual_callback: Функция для визуальной обратной связи
        """
        print("[TTS] Инициализация движка синтеза речи...")
        
        if not EDGE_TTS_AVAILABLE:
            raise RuntimeError("Edge TTS не установлен. Установите: pip install edge-tts")
        
        if not PYGAME_AVAILABLE:
            raise RuntimeError("Pygame не установлен. Установите: pip install pygame")
        
        # Инициализация pygame для воспроизведения
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
        
        # Настройки
        self.voice_preset = voice
        self.base_rate = rate
        self.base_volume = volume
        self.visual_callback = visual_callback
        
        # Очередь сообщений (текст, эмоция, приоритет)
        self.message_queue = queue.PriorityQueue()
        self.is_running = False
        self.currently_speaking = False
        self.current_task = None
        
        # Поток обработки очереди
        self.processing_thread = None
        
        # Получение доступных голосов
        try:
            self.available_voices = self._get_available_voices()
            print(f"[TTS] Доступные голоса: {', '.join(list(self.VOICE_PRESETS.keys()))}")
        except Exception as e:
            print(f"[TTS] Ошибка получения голосов: {e}")
            self.available_voices = []
        
        print(f"[TTS] Движок инициализирован. Голос: {voice}, Громкость: {volume}")
    
    def _get_available_voices(self) -> list:
        """Получение списка доступных голосов"""
        try:
            # Edge TTS требует асинхронного контекста
            voices = []
            for name in self.VOICE_PRESETS.keys():
                voices.append(name)
            return voices
        except Exception as e:
            print(f"[TTS] Ошибка получения голосов: {e}")
            return list(self.VOICE_PRESETS.keys())
    
    def _get_voice_id(self, emotion: str = 'neutral') -> str:
        """Получение ID голоса с учетом эмоции"""
        voice_name = self.voice_preset
        
        # Если голос не найден в пресетах, используем первый доступный
        if voice_name not in self.VOICE_PRESETS:
            voice_name = list(self.VOICE_PRESETS.keys())[0]
            print(f"[TTS] Голос '{self.voice_preset}' не найден. Используем '{voice_name}'")
        
        return self.VOICE_PRESETS[voice_name]
    
    def _get_speech_params(self, emotion: str = 'neutral') -> Dict[str, Any]:
        """Получение параметров речи для эмоции"""
        if emotion not in self.EMOTION_SETTINGS:
            emotion = 'neutral'
        
        settings = self.EMOTION_SETTINGS[emotion]
        return {
            'rate': self.base_rate + settings['rate'],
            'pitch': settings['pitch'],
            'volume': self.base_volume * (settings['volume'] / 100)
        }
    
    async def _synthesize_speech(self, text: str, emotion: str = 'neutral') -> bytes:
        """
        Асинхронный синтез речи
        
        Args:
            text: Текст для синтеза
            emotion: Эмоциональная окраска
            
        Returns:
            bytes: Аудиоданные в формате MP3
        """
        if not text or not isinstance(text, str):
            raise ValueError("Текст должен быть непустой строкой")
        
        try:
            voice_id = self._get_voice_id(emotion)
            params = self._get_speech_params(emotion)
            
            # Формирование SSML с эмоциональными параметрами
            ssml_text = f"""
            <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ru-RU">
                <voice name="{voice_id}">
                    <prosody rate="{params['rate']}%" pitch="{params['pitch']}%">
                        {text}
                    </prosody>
                </voice>
            </speak>
            """
            
            # Синтез через Edge TTS
            communicate = edge_tts.Communicate(ssml_text, voice_id)
            
            # Сохранение в байты
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            
            print(f"[TTS] Синтезировано: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            return audio_data
            
        except Exception as e:
            print(f"[TTS] Ошибка синтеза: {e}")
            raise
    
    def _play_audio(self, audio_data: bytes) -> bool:
        """
        Воспроизведение аудиоданных
        
        Args:
            audio_data: Байты аудио в формате MP3
            
        Returns:
            bool: Успешность воспроизведения
        """
        try:
            # Создание временного файла
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
                tmp_path = tmp_file.name
                tmp_file.write(audio_data)
            
            # Загрузка и воспроизведение
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.set_volume(self.base_volume)
            pygame.mixer.music.play()
            
            # Ожидание окончания воспроизведения
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
                # Обновление визуальной обратной связи
                if self.visual_callback:
                    self.visual_callback(True, 0.7)
            
            # Остановка и очистка
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            
            # Удаление временного файла
            os.unlink(tmp_path)
            
            # Сброс визуальной обратной связи
            if self.visual_callback:
                self.visual_callback(False, 0.0)
            
            return True
            
        except Exception as e:
            print(f"[TTS] Ошибка воспроизведения: {e}")
            if self.visual_callback:
                self.visual_callback(False, 0.0)
            return False
    
    def _process_queue(self):
        """Основной цикл обработки очереди сообщений"""
        print("[TTS] Запуск обработчика очереди...")
        
        while self.is_running:
            try:
                # Получение сообщения из очереди (приоритет, счетчик, данные)
                priority, count, (text, emotion) = self.message_queue.get(timeout=0.1)
                
                # Установка флага речи
                self.currently_speaking = True
                
                try:
                    # Синтез речи (в отдельном потоке для asyncio)
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    audio_data = loop.run_until_complete(
                        self._synthesize_speech(text, emotion)
                    )
                    loop.close()
                    
                    # Воспроизведение
                    if audio_data:
                        success = self._play_audio(audio_data)
                        if not success:
                            print(f"[TTS] Ошибка воспроизведения сообщения: {text[:30]}")
                
                except Exception as e:
                    print(f"[TTS] Ошибка обработки сообщения: {e}")
                
                finally:
                    self.currently_speaking = False
                    self.message_queue.task_done()
                    
            except queue.Empty:
                # Очередь пуста, продолжаем ожидание
                continue
            except Exception as e:
                print(f"[TTS] Ошибка в цикле обработки: {e}")
                self.currently_speaking = False
    
    def speak(self, text: str, emotion: str = 'neutral', priority: bool = False):
        """
        Добавление сообщения в очередь на озвучивание
        
        Args:
            text: Текст для озвучивания
            emotion: Эмоциональная окраска
            priority: Приоритетное сообщение (ставится в начало очереди)
        """
        if not text or not isinstance(text, str):
            print("[TTS] Пустой текст для озвучивания")
            return
        
        # Подготовка сообщения
        emotion = emotion if emotion in self.EMOTION_SETTINGS else 'neutral'
        
        # Приоритет: 0 - высокий, 1 - нормальный, 2 - низкий
        message_priority = 0 if priority else 1
        
        # Счетчик для сохранения порядка при одинаковом приоритете
        counter = time.time() * 1000
        
        try:
            # Добавление в очередь
            self.message_queue.put((message_priority, counter, (text, emotion)))
            
            if priority:
                print(f"[TTS] Приоритетное сообщение добавлено: '{text[:50]}...'")
            else:
                print(f"[TTS] Сообщение добавлено в очередь: '{text[:50]}...'")
                
        except Exception as e:
            print(f"[TTS] Ошибка добавления в очередь: {e}")
    
    def is_busy(self) -> bool:
        """
        Проверка, занят ли движок
        
        Returns:
            bool: True если идет синтез или воспроизведение
        """
        return self.currently_speaking or not self.message_queue.empty()
    
    def start(self):
        """Запуск движка TTS"""
        if self.is_running:
            print("[TTS] Движок уже запущен")
            return
        
        self.is_running = True
        
        # Запуск потока обработки очереди
        self.processing_thread = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="TTS-Processor"
        )
        self.processing_thread.start()
        
        print("[TTS] Движок запущен")
    
    def stop(self):
        """Остановка движка TTS"""
        if not self.is_running:
            return
        
        print("[TTS] Остановка движка...")
        self.is_running = False
        
        # Очистка очереди
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
                self.message_queue.task_done()
            except queue.Empty:
                break
        
        # Ожидание завершения потока
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)
        
        # Остановка pygame
        pygame.mixer.music.stop()
        pygame.mixer.quit()
        
        print("[TTS] Движок остановлен")
    
    def change_voice(self, voice_name: str):
        """
        Смена голоса
        
        Args:
            voice_name: Имя голоса из пресетов
        """
        if voice_name in self.VOICE_PRESETS:
            self.voice_preset = voice_name
            print(f"[TTS] Голос изменен на: {voice_name}")
        else:
            print(f"[TTS] Голос '{voice_name}' не найден. Доступные: {', '.join(self.VOICE_PRESETS.keys())}")
    
    def change_volume(self, volume: float):
        """
        Изменение громкости
        
        Args:
            volume: Громкость от 0.0 до 1.0
        """
        if 0.0 <= volume <= 1.0:
            self.base_volume = volume
            print(f"[TTS] Громкость изменена на: {volume}")
        else:
            print(f"[TTS] Некорректная громкость: {volume}. Должна быть от 0.0 до 1.0")
    
    def clear_queue(self):
        """Очистка очереди сообщений"""
        queue_size = self.message_queue.qsize()
        
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
                self.message_queue.task_done()
            except queue.Empty:
                break
        
        print(f"[TTS] Очередь очищена. Удалено сообщений: {queue_size}")


# Простой тест модуля
if __name__ == "__main__":
    print("=== Тест TTS движка ===")
    
    def test_visual_callback(speaking: bool, intensity: float):
        print(f"[VISUAL] Speaking: {speaking}, Intensity: {intensity}")
    
    try:
        tts = TTSEngine(
            voice='ru_female_soft',
            volume=0.8,
            visual_callback=test_visual_callback
        )
        
        tts.start()
        
        # Тестовые фразы
        print("\n1. Тестовая фраза (нейтральная):")
        tts.speak("Привет! Это тестовая фраза для проверки работы TTS движка.", emotion='neutral')
        
        time.sleep(3)
        
        print("\n2. Тестовая фраза (радостная):")
        tts.speak("Отлично! Система работает прекрасно! Это очень здорово!", emotion='happy')
        
        time.sleep(3)
        
        print("\n3. Тестовая фраза (приоритетная):")
        tts.speak("Внимание! Это приоритетное сообщение!", emotion='excited', priority=True)
        
        # Ожидание завершения
        print("\nОжидание завершения воспроизведения...")
        while tts.is_busy():
            time.sleep(0.5)
        
        print("\nВсе тесты завершены!")
        tts.stop()
        
    except Exception as e:
        print(f"Ошибка теста: {e}")
        import traceback
        traceback.print_exc()