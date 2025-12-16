import os
import asyncio
import tempfile
import threading
import queue
import time
import edge_tts
import pygame

class TTSEngine:
    VOICES = {
        'ru_female_1': 'ru-RU-SvetlanaNeural',
        'ru_female_2': 'ru-RU-DariyaNeural', 
        'ru_male_1': 'ru-RU-DmitryNeural',
        'en_female_1': 'en-US-JennyNeural',
        'en_female_2': 'en-US-AriaNeural',
        'en_male_1': 'en-US-GuyNeural',
    }
    
    EMOTIONS = {
        'neutral': '',
        'excited': 'cheerful',
        'sad': 'sad',
        'sarcastic': 'disgruntled',
        'supportive': 'friendly',
        'angry': 'angry'
    }
    
    def __init__(self, voice="ru-RU-DmitryNeural", rate=1.0, pitch=1.0):
        """Инициализация TTS движка"""
        self.enabled = True  # Этот атрибут у тебя уже есть
        
        try:
            import pyttsx3
            self.engine = pyttsx3.init()  # ← ВАЖНО! Создаём движок
        
            # Настройки голоса
            voices = self.engine.getProperty('voices')
            if voice in [v.id for v in voices]:
                self.engine.setProperty('voice', voice)
            self.engine.setProperty('rate', int(rate * 150))
            self.engine.setProperty('volume', 1.0)
        
            print(f"[TTS] Инициализирован с голосом: {voice}")
        except Exception as e:
            print(f"[TTS] Ошибка инициализации: {e}")
            self.enabled = False
            self.engine = None
        
    def _init_pygame(self):
        try:
            pygame.mixer.init(frequency=24000, size=-16, channels=1, buffer=2048)
        except Exception as e:
            print(f"[TTS] Ошибка инициализации pygame: {e}")
        
    def _start_audio_thread(self):
        self.audio_thread = threading.Thread(target=self._audio_worker, daemon=True)
        self.audio_thread.start()
        
    def _audio_worker(self):
        while True:
            try:
                audio_path, callback = self.audio_queue.get()
                if audio_path is None:
                    break
                self._play_audio(audio_path)
                if callback:
                    callback()
            except Exception as e:
                print(f"[TTS] Ошибка воспроизведения: {e}")
                
    def _play_audio(self, audio_path: str):
        self.is_speaking = True
        try:
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
                
            try:
                os.unlink(audio_path)
            except:
                pass
        except Exception as e:
            print(f"[TTS] Ошибка воспроизведения аудио: {e}")
        finally:
            self.is_speaking = False
            
    async def _generate_speech_async(self, text: str, emotion: str = 'neutral') -> str:
        style = self.EMOTIONS.get(emotion, '')
        
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume
        )
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = f.name
            
        await communicate.save(temp_path)
        return temp_path
        
    def speak(self, text: str, emotion: str = "neutral"):
        """Озвучивание текста с эмоцией"""
        if not text:
            return
            
        print(f"[TTS] Озвучивание ({emotion}): {text}")
        
        try:
            # Реализация озвучки (оставь свою)
            
            # Если используешь pyttsx3 - эмоции не поддерживаются напрямую
            self.engine.say(text)
            self.engine.runAndWait()
            
            # Или если другой движок - оставляй как есть
            
        except Exception as e:
            print(f"[TTS] Ошибка: {e}")
            print(f"[IRIS] >> {text}")
            
    def speak_async(self, text: str, emotion: str = 'neutral'):
        thread = threading.Thread(target=self.speak, args=(text, emotion))
        thread.start()
        return thread
        
    def stop(self):
        pygame.mixer.music.stop()
        while not self.audio_queue.empty():
            try:
                path, _ = self.audio_queue.get_nowait()
                if path:
                    try:
                        os.unlink(path)
                    except:
                        pass
            except queue.Empty:
                break
                
    def set_voice(self, voice: str):
        if voice in self.VOICES:
            self.voice = self.VOICES[voice]
            return True
        return False
        
    def set_rate(self, rate: str):
        self.rate = rate
        
    def get_available_voices(self) -> dict:
        return self.VOICES.copy()
        
    def is_busy(self) -> bool:
        return self.is_speaking or not self.audio_queue.empty()
        

if __name__ == "__main__":
    tts = TTSEngine(voice='ru_female_1')
    tts.speak("Привет! Я Ирис, твой AI-компаньон для стримов!", emotion='excited')
    while tts.is_busy():
        time.sleep(0.1)
