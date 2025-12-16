import os
import io
import time
import wave
import tempfile
import threading
import queue
from openai import OpenAI
import numpy as np

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("[VOICE] PyAudio не установлен - голосовое управление через микрофон недоступно")

class VoiceRecognition:
    WAKE_WORDS = ['ирис', 'iris', 'ирисик', 'эй ирис', 'hey iris']
    
    def __init__(self, 
                 wake_word_callback=None,
                 command_callback=None,
                 sample_rate: int = 16000,
                 chunk_duration: float = 3.0,
                 silence_threshold: float = 500,
                 silence_duration: float = 1.5):
        
        self.client = OpenAI()
        self.wake_word_callback = wake_word_callback
        self.command_callback = command_callback
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        
        self.is_listening = False
        self.is_wake_word_detected = False
        self.conversation_mode = False
        self.conversation_timeout = 30.0
        self.last_interaction_time = 0
        
        self.audio_queue = queue.Queue()
        self.result_queue = queue.Queue()
        
        if PYAUDIO_AVAILABLE:
            self.pyaudio = pyaudio.PyAudio()
        else:
            self.pyaudio = None
            
    def start_listening(self):
        if not PYAUDIO_AVAILABLE:
            print("[VOICE] Микрофон недоступен - используйте текстовый ввод")
            return False
            
        self.is_listening = True
        
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.process_thread = threading.Thread(target=self._process_loop, daemon=True)
        
        self.listen_thread.start()
        self.process_thread.start()
        
        print("[VOICE] Слушаю... Скажите 'Ирис' для активации")
        return True
        
    def stop_listening(self):
        self.is_listening = False
        self.conversation_mode = False
        
    def _listen_loop(self):
        try:
            stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=1024
            )
            
            while self.is_listening:
                frames = []
                silent_chunks = 0
                has_speech = False
                
                chunk_samples = int(self.sample_rate * self.chunk_duration)
                silence_samples = int(self.sample_rate * self.silence_duration)
                
                while self.is_listening:
                    data = stream.read(1024, exception_on_overflow=False)
                    frames.append(data)
                    
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    volume = np.abs(audio_data).mean()
                    
                    if volume > self.silence_threshold:
                        has_speech = True
                        silent_chunks = 0
                    else:
                        silent_chunks += 1
                        
                    total_samples = len(frames) * 1024
                    
                    if has_speech and silent_chunks * 1024 > silence_samples:
                        break
                        
                    if total_samples > chunk_samples * 3:
                        break
                        
                if frames and has_speech:
                    audio_bytes = b''.join(frames)
                    self.audio_queue.put(audio_bytes)
                    
            stream.stop_stream()
            stream.close()
            
        except Exception as e:
            print(f"[VOICE] Ошибка записи: {e}")
            
    def _process_loop(self):
        while self.is_listening:
            try:
                audio_bytes = self.audio_queue.get(timeout=1.0)
                text = self._transcribe(audio_bytes)
                
                if text:
                    self._handle_transcription(text)
                    
            except queue.Empty:
                if self.conversation_mode:
                    if time.time() - self.last_interaction_time > self.conversation_timeout:
                        self.conversation_mode = False
                        print("[VOICE] Режим разговора завершён по таймауту")
                        
            except Exception as e:
                print(f"[VOICE] Ошибка обработки: {e}")
                
    def _transcribe(self, audio_bytes: bytes) -> str:
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                with wave.open(f.name, 'wb') as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(self.sample_rate)
                    wav.writeframes(audio_bytes)
                temp_path = f.name
                
            with open(temp_path, 'rb') as audio_file:
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ru"
                )
                
            os.unlink(temp_path)
            return response.text.strip().lower()
            
        except Exception as e:
            print(f"[VOICE] Ошибка транскрипции: {e}")
            return ""
            
    def _handle_transcription(self, text: str):
        print(f"[VOICE] Распознано: {text}")
        
        if self.conversation_mode:
            self.last_interaction_time = time.time()
            if self.command_callback:
                self.command_callback(text, is_conversation=True)
            return
            
        for wake_word in self.WAKE_WORDS:
            if wake_word in text:
                self.conversation_mode = True
                self.last_interaction_time = time.time()
                
                command = text
                for ww in self.WAKE_WORDS:
                    command = command.replace(ww, '').strip()
                    
                print(f"[VOICE] Wake word обнаружен! Команда: {command}")
                
                if self.wake_word_callback:
                    self.wake_word_callback()
                    
                if command and self.command_callback:
                    self.command_callback(command, is_conversation=False)
                elif self.command_callback:
                    self.command_callback("", is_conversation=False)
                    
                return
                
    def transcribe_file(self, file_path: str) -> str:
        try:
            with open(file_path, 'rb') as audio_file:
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ru"
                )
            return response.text.strip()
        except Exception as e:
            print(f"[VOICE] Ошибка транскрипции файла: {e}")
            return ""
            
    def set_conversation_mode(self, enabled: bool):
        self.conversation_mode = enabled
        if enabled:
            self.last_interaction_time = time.time()
            
    def is_in_conversation(self) -> bool:
        return self.conversation_mode
        

class TextInputFallback:
    def __init__(self, command_callback=None):
        self.command_callback = command_callback
        self.is_listening = False
        self.input_thread = None
        
    def start_listening(self):
        self.is_listening = True
        self.input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self.input_thread.start()
        print("[TEXT] Текстовый ввод активирован. Введите команду:")
        return True
        
    def stop_listening(self):
        self.is_listening = False
        
    def _input_loop(self):
        while self.is_listening:
            try:
                user_input = input("> ").strip()
                if user_input and self.command_callback:
                    self.command_callback(user_input, is_conversation=True)
            except EOFError:
                break
            except Exception as e:
                print(f"[TEXT] Ошибка ввода: {e}")
