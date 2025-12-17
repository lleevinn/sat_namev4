import os
import time
import threading
import queue

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False
    print("[VOICE] SpeechRecognition не установлен")

PYAUDIO_AVAILABLE = False
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    print("[VOICE] PyAudio не установлен - голосовое управление через микрофон недоступно")

class VoiceRecognition:
    WAKE_WORDS = ['ирис', 'iris', 'ирисик', 'эй ирис', 'hey iris', 'ириска']
    
    def __init__(self, 
                 wake_word_callback=None,
                 command_callback=None,
                 language: str = "ru-RU"):
        
        self.wake_word_callback = wake_word_callback
        self.command_callback = command_callback
        self.language = language
        
        self.is_listening = False
        self.conversation_mode = False
        self.conversation_timeout = 30.0
        self.last_interaction_time = 0
        
        if SR_AVAILABLE and PYAUDIO_AVAILABLE:
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.8
        else:
            self.recognizer = None
            
        self.listen_thread = None
            
    def start_listening(self):
        if not SR_AVAILABLE or not PYAUDIO_AVAILABLE:
            print("[VOICE] Микрофон недоступен - используйте текстовый ввод")
            return False
            
        self.is_listening = True
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        
        print("[VOICE] Слушаю... Скажите 'Ирис' для активации")
        return True
        
    def stop_listening(self):
        self.is_listening = False
        self.conversation_mode = False
        
    def _listen_loop(self):
        try:
            with sr.Microphone() as source:
                print("[VOICE] Калибровка микрофона...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                print("[VOICE] Готов к прослушиванию!")
                
                while self.is_listening:
                    try:
                        audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                        
                        threading.Thread(
                            target=self._process_audio, 
                            args=(audio,),
                            daemon=True
                        ).start()
                        
                    except sr.WaitTimeoutError:
                        if self.conversation_mode:
                            if time.time() - self.last_interaction_time > self.conversation_timeout:
                                self.conversation_mode = False
                                print("[VOICE] Режим разговора завершён по таймауту")
                        continue
                    except Exception as e:
                        print(f"[VOICE] Ошибка прослушивания: {e}")
                        continue
                        
        except Exception as e:
            print(f"[VOICE] Критическая ошибка: {e}")
            
    def _process_audio(self, audio):
        try:
            text = self.recognizer.recognize_google(audio, language=self.language)
            text = text.lower().strip()
            
            if not text:
                return
                
            print(f"[VOICE] Распознано: {text}")
            self._handle_transcription(text)
            
        except sr.UnknownValueError:
            pass
        except sr.RequestError as e:
            print(f"[VOICE] Ошибка сервиса распознавания: {e}")
        except Exception as e:
            print(f"[VOICE] Ошибка обработки: {e}")
            
    def _handle_transcription(self, text: str):
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
                time.sleep(1)
