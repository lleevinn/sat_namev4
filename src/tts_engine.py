import os
import io
import tempfile
from openai import OpenAI
import pygame
import threading
import queue
import time

class TTSEngine:
    VOICES = {
        'alloy': 'нейтральный',
        'echo': 'мужской глубокий', 
        'fable': 'британский акцент',
        'onyx': 'мужской авторитетный',
        'nova': 'женский энергичный',
        'shimmer': 'женский мягкий'
    }
    
    EMOTIONS = {
        'neutral': '',
        'excited': '! ',
        'sad': '... ',
        'sarcastic': '~ ',
        'supportive': ', ',
        'angry': '! '
    }
    
    def __init__(self, voice: str = 'nova', speed: float = 1.0):
        self.client = OpenAI()
        self.voice = voice if voice in self.VOICES else 'nova'
        self.speed = max(0.25, min(4.0, speed))
        self.audio_queue = queue.Queue()
        self.is_speaking = False
        self._init_pygame()
        self._start_audio_thread()
        
    def _init_pygame(self):
        pygame.mixer.init(frequency=24000, size=-16, channels=1, buffer=2048)
        
    def _start_audio_thread(self):
        self.audio_thread = threading.Thread(target=self._audio_worker, daemon=True)
        self.audio_thread.start()
        
    def _audio_worker(self):
        while True:
            try:
                audio_data, callback = self.audio_queue.get()
                if audio_data is None:
                    break
                self._play_audio(audio_data)
                if callback:
                    callback()
            except Exception as e:
                print(f"[TTS] Ошибка воспроизведения: {e}")
                
    def _play_audio(self, audio_data: bytes):
        self.is_speaking = True
        try:
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                f.write(audio_data)
                temp_path = f.name
            
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
                
            os.unlink(temp_path)
        except Exception as e:
            print(f"[TTS] Ошибка воспроизведения аудио: {e}")
        finally:
            self.is_speaking = False
            
    def speak(self, text: str, emotion: str = 'neutral', callback=None, priority: bool = False):
        if not text or not text.strip():
            return
            
        text = self._apply_emotion(text, emotion)
        
        try:
            response = self.client.audio.speech.create(
                model="tts-1-hd",
                voice=self.voice,
                input=text,
                speed=self.speed,
                response_format="mp3"
            )
            
            audio_data = response.content
            
            if priority:
                self.stop()
                
            self.audio_queue.put((audio_data, callback))
            
        except Exception as e:
            print(f"[TTS] Ошибка генерации речи: {e}")
            
    def _apply_emotion(self, text: str, emotion: str) -> str:
        prefix = self.EMOTIONS.get(emotion, '')
        
        emotion_hints = {
            'excited': '*с воодушевлением* ',
            'sad': '*грустно* ',
            'sarcastic': '*саркастично* ',
            'supportive': '*поддерживающе* ',
            'angry': '*раздражённо* '
        }
        
        if emotion in emotion_hints and emotion != 'neutral':
            text = emotion_hints[emotion] + text
            
        return text
        
    def speak_async(self, text: str, emotion: str = 'neutral'):
        thread = threading.Thread(target=self.speak, args=(text, emotion))
        thread.start()
        return thread
        
    def stop(self):
        pygame.mixer.music.stop()
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
                
    def set_voice(self, voice: str):
        if voice in self.VOICES:
            self.voice = voice
            return True
        return False
        
    def set_speed(self, speed: float):
        self.speed = max(0.25, min(4.0, speed))
        
    def get_available_voices(self) -> dict:
        return self.VOICES.copy()
        
    def is_busy(self) -> bool:
        return self.is_speaking or not self.audio_queue.empty()
        

if __name__ == "__main__":
    tts = TTSEngine(voice='nova')
    tts.speak("Привет! Я Ирис, твой AI-компаньон для стримов!", emotion='excited')
    while tts.is_busy():
        time.sleep(0.1)
