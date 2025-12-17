"""
Iris TTS Engine - Нежный женский голос с Edge TTS
Полностью бесплатный синтез речи с эмоциональными интонациями
"""
import asyncio
import tempfile
import os
import sys
import threading
import queue
import time
from pathlib import Path
from typing import Optional, Dict, Callable

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    print("[TTS] edge-tts не установлен. Установите: pip install edge-tts")

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("[TTS] pygame не установлен. Установите: pip install pygame")


class TTSEngine:
    """
    Движок синтеза речи с нежным женским голосом
    Использует Edge TTS (бесплатный, высокое качество)
    """
    
    VOICES = {
        'ru_female_soft': 'ru-RU-SvetlanaNeural',
        'ru_female_warm': 'ru-RU-DariyaNeural', 
        'ru_male': 'ru-RU-DmitryNeural',
        'en_female_soft': 'en-US-JennyNeural',
        'en_female_warm': 'en-US-AriaNeural',
        'en_male': 'en-US-GuyNeural',
    }
    
    EMOTION_STYLES = {
        'neutral': {'rate': '+0%', 'pitch': '+0Hz', 'volume': '+0%'},
        'excited': {'rate': '+15%', 'pitch': '+3Hz', 'volume': '+10%'},
        'happy': {'rate': '+10%', 'pitch': '+2Hz', 'volume': '+5%'},
        'sad': {'rate': '-10%', 'pitch': '-2Hz', 'volume': '-5%'},
        'supportive': {'rate': '-5%', 'pitch': '+1Hz', 'volume': '+0%'},
        'sarcastic': {'rate': '-5%', 'pitch': '-1Hz', 'volume': '+0%'},
        'tense': {'rate': '+20%', 'pitch': '+4Hz', 'volume': '+15%'},
        'gentle': {'rate': '-15%', 'pitch': '+2Hz', 'volume': '-10%'},
    }
    
    EMOTION_INTENSITY = {
        'neutral': 0.5,
        'excited': 1.0,
        'happy': 0.8,
        'sad': 0.3,
        'supportive': 0.6,
        'sarcastic': 0.4,
        'tense': 0.9,
        'gentle': 0.4,
    }
    
    def __init__(self, 
                 voice: str = 'ru_female_soft',
                 rate: int = 0,
                 volume: float = 1.0,
                 lang: str = 'ru',
                 visual_callback: Optional[Callable] = None):
        """
        Инициализация TTS движка
        
        Args:
            voice: Имя голоса из VOICES или прямое имя Edge TTS
            rate: Скорость речи в процентах (-50 до +50)
            volume: Громкость (0.0-1.0)
            lang: Язык по умолчанию
        """
        self.voice_name = self.VOICES.get(voice, voice)
        self.base_rate = rate
        self.base_volume = volume
        self.lang = lang
        self.visual_callback = visual_callback
        
        self.speech_queue = queue.Queue()
        self.is_speaking = False
        self.stop_flag = False
        self.current_emotion = 'neutral'
        self.playback_available = False
        
        self._init_pygame()
        
        self.worker_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.worker_thread.start()
        
        print(f"[TTS] Инициализирован с голосом: {self.voice_name}")
        print(f"[TTS] Edge TTS доступен: {EDGE_TTS_AVAILABLE}")
        print(f"[TTS] Воспроизведение доступно: {self.playback_available}")
    
    def _init_pygame(self):
        """Инициализация pygame mixer"""
        if not PYGAME_AVAILABLE:
            self.playback_available = False
            return
            
        try:
            pygame.mixer.pre_init(frequency=24000, size=-16, channels=1, buffer=512)
            pygame.mixer.init()
            self.playback_available = True
            print("[TTS] Pygame mixer инициализирован")
        except Exception as e:
            self.playback_available = False
            print(f"[TTS] Воспроизведение недоступно (нет аудио устройств): {e}")
            print("[TTS] Синтез речи будет работать, но воспроизведение отключено")
    
    def _get_rate_string(self, emotion: str = 'neutral') -> str:
        """Получить строку скорости для SSML"""
        emotion_rate = self.EMOTION_STYLES.get(emotion, {}).get('rate', '+0%')
        base = int(emotion_rate.replace('%', '').replace('+', ''))
        total = self.base_rate + base
        sign = '+' if total >= 0 else ''
        return f"{sign}{total}%"
    
    def _get_pitch_string(self, emotion: str = 'neutral') -> str:
        """Получить строку тона для SSML"""
        return self.EMOTION_STYLES.get(emotion, {}).get('pitch', '+0Hz')
    
    def _get_volume_string(self, emotion: str = 'neutral') -> str:
        """Получить строку громкости для SSML"""
        return self.EMOTION_STYLES.get(emotion, {}).get('volume', '+0%')
    
    async def _synthesize_async(self, text: str, emotion: str = 'neutral') -> Optional[str]:
        """
        Асинхронный синтез речи
        
        Returns:
            str: Путь к временному аудио файлу
        """
        if not EDGE_TTS_AVAILABLE:
            print("[TTS] Edge TTS недоступен")
            return None
        
        try:
            rate = self._get_rate_string(emotion)
            pitch = self._get_pitch_string(emotion)
            volume = self._get_volume_string(emotion)
            
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice_name,
                rate=rate,
                pitch=pitch,
                volume=volume
            )
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False, prefix='iris_tts_') as tmp:
                output_path = tmp.name
            
            await communicate.save(output_path)
            
            return output_path
            
        except Exception as e:
            print(f"[TTS] Ошибка синтеза: {e}")
            return None
    
    def _play_audio(self, file_path: str, emotion: str = 'neutral') -> bool:
        """Воспроизведение аудио файла с визуальной обратной связью"""
        if not self.playback_available:
            print(f"[TTS] Воспроизведение пропущено (нет аудио): {os.path.basename(file_path)}")
            return False
        
        if not os.path.exists(file_path):
            print(f"[TTS] Файл не найден: {file_path}")
            return False
        
        try:
            if not pygame.mixer.get_init():
                self._init_pygame()
                if not self.playback_available:
                    return False
            
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.set_volume(self.base_volume)
            pygame.mixer.music.play()
            
            intensity = self.EMOTION_INTENSITY.get(emotion, 0.5)
            if self.visual_callback:
                self.visual_callback(True, intensity)
            
            pulse_phase = 0
            while pygame.mixer.music.get_busy() and not self.stop_flag:
                if self.visual_callback:
                    import math
                    pulse_intensity = intensity * (0.7 + 0.3 * math.sin(pulse_phase * 8))
                    self.visual_callback(True, pulse_intensity)
                    pulse_phase += 0.05
                time.sleep(0.05)
            
            if self.visual_callback:
                self.visual_callback(False, 0)
            
            pygame.mixer.music.stop()
            return True
            
        except Exception as e:
            print(f"[TTS] Ошибка воспроизведения: {e}")
            if self.visual_callback:
                self.visual_callback(False, 0)
            return False
        finally:
            try:
                os.unlink(file_path)
            except:
                pass
    
    def _speech_worker(self):
        """Рабочий поток для обработки очереди речи"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while not self.stop_flag:
            try:
                item = self.speech_queue.get(timeout=0.5)
                if item is None:
                    continue
                
                text, emotion, priority, callback = item
                
                self.is_speaking = True
                self.current_emotion = emotion
                
                print(f"[TTS] Синтезирую: '{text[:50]}...' эмоция: {emotion}")
                
                audio_file = loop.run_until_complete(
                    self._synthesize_async(text, emotion)
                )
                
                if audio_file:
                    success = self._play_audio(audio_file, emotion)
                    if callback:
                        callback(success)
                
                self.is_speaking = False
                self.speech_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[TTS] Ошибка в рабочем потоке: {e}")
                self.is_speaking = False
        
        loop.close()
    
    def speak(self, 
              text: str, 
              emotion: str = 'neutral',
              priority: bool = False,
              callback: Optional[Callable] = None):
        """
        Озвучить текст с указанной эмоцией
        
        Args:
            text: Текст для озвучивания
            emotion: Эмоция (neutral, excited, happy, sad, supportive, sarcastic, tense, gentle)
            priority: Если True, прерывает текущую речь
            callback: Функция обратного вызова после озвучивания
        """
        if not text or not text.strip():
            return
        
        text = text.strip()
        
        if priority and self.is_speaking:
            self.interrupt()
        
        self.speech_queue.put((text, emotion, priority, callback))
        print(f"[TTS] В очередь: '{text[:30]}...' (эмоция: {emotion})")
    
    def speak_with_pauses(self, text: str, emotion: str = 'neutral'):
        """Озвучить текст с естественными паузами между предложениями"""
        sentences = text.replace('!', '.').replace('?', '.').split('.')
        sentences = [s.strip() for s in sentences if s.strip()]
        
        for sentence in sentences:
            self.speak(sentence, emotion)
    
    def interrupt(self):
        """Прервать текущую речь"""
        if PYGAME_AVAILABLE and pygame.mixer.get_init():
            pygame.mixer.music.stop()
        
        while not self.speech_queue.empty():
            try:
                self.speech_queue.get_nowait()
                self.speech_queue.task_done()
            except:
                break
    
    def is_busy(self) -> bool:
        """Проверка, говорит ли сейчас"""
        return self.is_speaking or not self.speech_queue.empty()
    
    def set_voice(self, voice: str):
        """Сменить голос"""
        self.voice_name = self.VOICES.get(voice, voice)
        print(f"[TTS] Голос изменён на: {self.voice_name}")
    
    def set_rate(self, rate: int):
        """Установить скорость речи (-50 до +50)"""
        self.base_rate = max(-50, min(50, rate))
    
    def set_volume(self, volume: float):
        """Установить громкость (0.0-1.0)"""
        self.base_volume = max(0.0, min(1.0, volume))
    
    def set_visual_callback(self, callback: Optional[Callable]):
        """Установить callback для визуальной обратной связи"""
        self.visual_callback = callback
    
    def stop(self):
        """Остановить движок"""
        self.stop_flag = True
        self.interrupt()
        
        if PYGAME_AVAILABLE and pygame.mixer.get_init():
            pygame.mixer.quit()
        
        print("[TTS] Движок остановлен")
    
    @staticmethod
    async def list_voices(lang_filter: str = 'ru') -> list:
        """Получить список доступных голосов"""
        if not EDGE_TTS_AVAILABLE:
            return []
        
        try:
            voices = await edge_tts.list_voices()
            if lang_filter:
                voices = [v for v in voices if lang_filter.lower() in v['Locale'].lower()]
            return voices
        except Exception as e:
            print(f"[TTS] Ошибка получения голосов: {e}")
            return []


def synthesize_and_play(text: str, lang: str = 'ru', cleanup: bool = True) -> bool:
    """
    Быстрая функция для синтеза и воспроизведения
    Совместимость со старым API
    """
    engine = TTSEngine(voice='ru_female_soft')
    engine.speak(text, emotion='neutral')
    
    while engine.is_busy():
        time.sleep(0.1)
    
    engine.stop()
    return True


if __name__ == "__main__":
    print("=== Тест TTS Engine ===")
    
    tts = TTSEngine(voice='ru_female_soft')
    
    print("\nТест 1: Нейтральный голос")
    tts.speak("Привет! Я Ирис, твой голосовой ассистент.", emotion='neutral')
    
    while tts.is_busy():
        time.sleep(0.1)
    
    print("\nТест 2: Взволнованный голос")
    tts.speak("Ух ты! Отличный выстрел! Красавчик!", emotion='excited')
    
    while tts.is_busy():
        time.sleep(0.1)
    
    print("\nТест 3: Нежный голос")
    tts.speak("Не переживай, в следующий раз обязательно получится.", emotion='gentle')
    
    while tts.is_busy():
        time.sleep(0.1)
    
    tts.stop()
    print("\n=== Тест завершён ===")
