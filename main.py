import os
import sys
import time
import threading
import signal
from dotenv import load_dotenv

load_dotenv()

from src.utils.tts_utils import synthesize_and_play
from src.tts_engine import TTSEngine
from src.voice_input import VoiceInput  # Импорт правильного класса
from src.cs2_gsi import CS2GameStateIntegration, GameEvent  # Этот класс мы импортируем
from src.streamelements_client import StreamElementsClient, StreamEvent
from src.iris_brain import IrisBrain
from src.windows_audio import WindowsAudioController
from src.achievements import AchievementSystem, Achievement
# Импортируем дополнительные компоненты, если они есть
try:
    from src.audio_mixer import AudioMixer
    from src.voice_input import VoiceInput  # На случай, если старый модуль ещё нужен
except ImportError:
    pass

class IrisAssistant:
    def __init__(self):
        print("=" * 50)
        print("🌸 Запуск Ирис - AI Stream Companion")
        print("=" * 50)

        self.CONFIG = {
            "cs2_gsi_port": 3000,
            "voice_wake_word": "ирис",  # Исправлено: нормальные русские буквы
            "voice_sensitivity": 0.8,
            "tts_voice": "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices\\Tokens\\TTS_MS_RU-RU_IRINA_11.0",  # Прямой ID голоса Ирины
            "tts_rate": 200,
            "tts_volume": 0.9,
        }

        # Инициализация компонентов в правильном порядке
        self.tts = TTSEngine(
            voice=self.CONFIG["tts_voice"],
            rate=self.CONFIG["tts_rate"],
            volume=self.CONFIG["tts_volume"]
        )

        self.iris_brain = IrisBrain()
        
        # ИСПРАВЛЕНО: используем импортированный класс CS2GameStateIntegration
        self.cs2_gsi = CS2GameStateIntegration(port=self.CONFIG["cs2_gsi_port"])
        
        self.audio_controller = WindowsAudioController()
        
        # Используем VoiceRecognition, так как он импортируется
        self.voice_input = VoiceInput(
            wake_word=self.CONFIG["voice_wake_word"],
            sensitivity=self.CONFIG["voice_sensitivity"]
        )
        
        self.achievements = AchievementSystem()
        self.stream_elements = StreamElementsClient()
        
        # Настройка обработки голосовых команд
        self.voice_input.set_command_callback(self.process_voice_command)
        
           
    def _on_wake_word(self):
        print("[IRIS] Wake word обнаружен!")
        self.tts.speak("Да?", emotion='neutral', priority=True)
        
    def _on_voice_command(self, command: str, is_conversation: bool = False):
        if not command:
            return
            
        print(f"[IRIS] Команда: {command}")
        
        audio_keywords = ['громкость', 'тише', 'громче', 'выключи', 'включи', 'музык', 'звук', 'mute']
        if any(kw in command.lower() for kw in audio_keywords):
            response = self.audio_controller.execute_voice_command(command)
            self.tts.speak(response)
            return
            
        response = self.brain.chat_with_user(command)
        if response:
            self.tts.speak(response)
            
    def _on_cs2_event(self, event: GameEvent):
        print(f"[CS2] Событие: {event.event_type}")
        
        self.brain.update_context(
            map_name=self.cs2_gsi.map.name,
            ct_score=self.cs2_gsi.map.ct_score,
            t_score=self.cs2_gsi.map.t_score,
            player_stats=self.cs2_gsi.get_player_stats(),
            event={'type': event.event_type, 'data': event.data}
        )
        
        response = None
        emotion = 'neutral'
        
        if event.event_type in ['kill', 'double_kill', 'triple_kill', 'quadra_kill', 'ace']:
            is_headshot = event.data.get('headshot', False)
            round_kills = event.data.get('round_kills', 1)
            self.achievements.record_kill(headshot=is_headshot, round_kills=round_kills)
            response = self.brain.react_to_kill(event.data)
            emotion = 'excited' if round_kills >= 3 else 'neutral'
            
        elif event.event_type == 'death':
            self.achievements.record_death()
            response = self.brain.react_to_death(event.data)
            emotion = 'sad'
            
        elif event.event_type == 'round_end':
            won = event.data.get('won', False)
            clutch = event.data.get('clutch_win', False)
            if won:
                self.achievements.record_round_win(clutch=clutch)
            else:
                self.achievements.record_round_loss()
            response = self.brain.react_to_round_end(event.data)
            emotion = 'excited' if won else 'supportive'
            
        elif event.event_type == 'low_health':
            health = event.data.get('current_health', 100)
            self.achievements.record_low_health_survive(health)
            
        elif event.event_type in ['bomb_planted', 'bomb_defused', 'bomb_exploded']:
            if event.event_type == 'bomb_defused' and event.data.get('ninja_defuse'):
                self.achievements.record_ninja_defuse()
            response = self.brain.react_to_bomb_event(event.event_type, event.data)
            emotion = 'excited'
            
        elif event.event_type == 'match_end':
            won = event.data.get('won', False)
            self.achievements.record_match_end(won=won)
            
        if response:
            self.tts.speak(response, emotion=emotion)
            
    def _on_stream_event(self, event: StreamEvent):
        print(f"[STREAM] Событие: {event.event_type}")
        
        response = None
        emotion = 'neutral'
        
        if event.event_type == 'donation':
            amount = event.data.get('amount', 0)
            currency = event.data.get('currency', 'RUB')
            self.achievements.record_donation(amount, currency)
            response = self.brain.react_to_donation(event.data)
            emotion = 'excited'
            
        elif event.event_type == 'subscription':
            self.achievements.record_subscription()
            response = self.brain.react_to_subscription(event.data)
            emotion = 'excited'
            
        elif event.event_type == 'raid':
            viewers = event.data.get('viewers', 0)
            self.achievements.record_raid(viewers)
            response = self.brain.react_to_raid(event.data)
            emotion = 'excited'
            
        elif event.event_type == 'chat_message':
            self.achievements.record_chat_message()
            response = self.brain.react_to_chat_message(event.data)
            if response:
                emotion = 'neutral'
                
        elif event.event_type == 'follow':
            pass
            
        if response:
            self.tts.speak(response, emotion=emotion)
            
    def _on_achievement(self, achievement: Achievement):
        message = f"Достижение разблокировано! {achievement.icon} {achievement.name}!"
        self.tts.speak(message, emotion='excited', priority=True)
        
    def _random_comment_loop(self):
        while self.is_running:
            time.sleep(120)
            
            if not self.is_running:
                break
                
            self.achievements.check_time_achievements()
            
            if not self.tts.is_busy():
                comment = self.brain.generate_random_comment()
                if comment:
                    self.tts.speak(comment, emotion='neutral')
                    
    def start(self):
        self.is_running = True
        
        print("\n[IRIS] Запуск CS2 Game State Integration...")
        self.cs2_gsi.start()
        self.cs2_gsi.save_config_file()
        
        jwt_token = os.getenv('STREAMELEMENTS_JWT_TOKEN', '')
        if jwt_token:
            print("\n[IRIS] Подключение к StreamElements...")
            self.stream_elements.connect()
        else:
            print("\n[IRIS] STREAMELEMENTS_JWT_TOKEN не настроен - чат недоступен")
            
        groq_key = os.getenv('GROQ_API_KEY', '')
        if not groq_key:
            print("\n[IRIS] ⚠️ GROQ_API_KEY не настроен - AI будет использовать fallback ответы")
            
        print("\n[IRIS] Запуск голосового ввода...")
        self.voice_input.start()
        
        self.random_comment_thread = threading.Thread(
            target=self._random_comment_loop, 
            daemon=True
        )
        self.random_comment_thread.start()
        
        response = "Система Ирис успешно запущена и готова к работе!"  # Определяем переменную
        self.tts.speak(response)
        
        print("\n" + "=" * 50)
        print("🌸 Ирис запущена и готова к работе!")
        print("=" * 50)
        print("\nДоступные функции:")
        print("- CS2 Game State Integration (порт 3000)")
        print("- StreamElements чат и донаты")
        print("- Голосовое управление (скажите 'Ирис')")
        print("- Управление громкостью приложений")
        print("- Система достижений")
        print("\nНажмите Ctrl+C для остановки")
        print("=" * 50)
        
    def stop(self):
        print("\n[IRIS] Остановка...")
        self.is_running = False
        
        self.achievements.save_stats()
        
        self.voice.stop_listening()
        self.stream_elements.disconnect()
        self.cs2_gsi.stop()
        self.tts.stop()
        
        print("[IRIS] До встречи на следующем стриме! 🌸")
        
    def process_voice_command(self, command: str):
        """Обработка голосовых команд"""
        print(f"[IRIS] 💬 Команда: '{command}'")
        
        if not command or command.strip() == "":
            response = "Да, я здесь! Говорите команду."
        elif "привет" in command.lower():
            response = "Привет! Я Ирис, теперь с женским голосом!"
        elif "тест" in command.lower():
            response = "Тест пройден. Голосовой помощник работает."
        elif "стоп" in command.lower():
            response = "Завершаю работу."
            self.tts.speak(response)
            self.stop()
            return
        else:
            # Используем мозг Ирис для ответа
            response = self.iris_brain.chat_with_user(command)
            if not response:
                response = f"Я услышала: '{command}'."
        
        print(f"[IRIS] 🤖 Ответ: {response}")
        self.tts.speak(response)

    def run(self):
        def signal_handler(sig, frame):
            self.stop()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        self.start()
        
        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
            

def main():
    iris = IrisAssistant()
    iris.run()
    

if __name__ == "__main__":
    main()
