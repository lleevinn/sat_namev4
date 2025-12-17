"""
IRIS - AI Stream Companion
Голосовой ассистент для стримов с CS2 интеграцией
Полностью бесплатные технологии (Edge TTS, Vosk, Groq)
"""
import os
import sys
import time
import threading
import signal
from dotenv import load_dotenv

load_dotenv()

from src.tts_engine import TTSEngine
from src.voice_input import VoiceInput
from src.cs2_gsi import CS2GameStateIntegration, GameEvent
from src.streamelements_client import StreamElementsClient, StreamEvent
from src.iris_brain import IrisBrain
from src.windows_audio import WindowsAudioController
from src.achievements import AchievementSystem, Achievement
from src.iris_visual import IrisVisual


class IrisAssistant:
    """
    Главный класс Ирис - AI компаньона для стримов
    """
    
    def __init__(self):
        print("=" * 60)
        print("🌸 Запуск Ирис - AI Stream Companion")
        print("=" * 60)
        print()

        self.CONFIG = {
            "cs2_gsi_port": 3000,
            "voice_wake_word": "ирис",
            "voice_sensitivity": 0.8,
            "tts_voice": "ru_female_soft",
            "tts_rate": 0,
            "tts_volume": 0.9,
        }
        
        self.is_running = False

        print("[IRIS] Инициализация визуального интерфейса (IO-style)...")
        self.visual = IrisVisual(width=400, height=400)
        
        print("[IRIS] Инициализация TTS (нежный женский голос)...")
        self.tts = TTSEngine(
            voice=self.CONFIG["tts_voice"],
            rate=self.CONFIG["tts_rate"],
            volume=self.CONFIG["tts_volume"],
            visual_callback=self._on_visual_update
        )

        print("[IRIS] Инициализация AI мозга...")
        self.iris_brain = IrisBrain()
        
        print("[IRIS] Инициализация CS2 Game State Integration...")
        self.cs2_gsi = CS2GameStateIntegration(
            port=self.CONFIG["cs2_gsi_port"],
            event_callback=self._on_cs2_event
        )
        
        print("[IRIS] Инициализация аудио контроллера...")
        self.audio_controller = WindowsAudioController()
        
        print("[IRIS] Инициализация голосового ввода...")
        self.voice_input = VoiceInput(
            wake_word=self.CONFIG["voice_wake_word"],
            sensitivity=self.CONFIG["voice_sensitivity"]
        )
        self.voice_input.set_command_callback(self.process_voice_command)
        
        print("[IRIS] Инициализация системы достижений...")
        self.achievements = AchievementSystem(
            achievement_callback=self._on_achievement
        )
        
        print("[IRIS] Инициализация StreamElements клиента...")
        self.stream_elements = StreamElementsClient(
            event_callback=self._on_stream_event
        )
        
        print()
        print("[IRIS] ✅ Все компоненты инициализированы")
    
    def _on_visual_update(self, speaking: bool, intensity: float):
        """Обновление визуального интерфейса при разговоре"""
        if hasattr(self, 'visual') and self.visual:
            self.visual.set_speaking(speaking, intensity)
        
    def _on_wake_word(self):
        """Обработка обнаружения wake word"""
        print("[IRIS] Wake word обнаружен!")
        self.tts.speak("Да?", emotion='neutral', priority=True)
        
    def process_voice_command(self, command: str):
        """Обработка голосовых команд"""
        print(f"[IRIS] 💬 Получена команда: '{command}'")
        
        if not command or command.strip() == "":
            response = "Да, я здесь! Чем могу помочь?"
            self.tts.speak(response, emotion='gentle')
            return
        
        command_lower = command.lower().strip()
        
        audio_keywords = ['громкость', 'тише', 'громче', 'выключи', 'включи', 'музык', 'звук', 'mute']
        if any(kw in command_lower for kw in audio_keywords):
            response = self.audio_controller.execute_voice_command(command)
            self.tts.speak(response, emotion='neutral')
            return
        
        if 'привет' in command_lower:
            response = "Привет! Я Ирис, твоя AI-подруга на стриме!"
            self.tts.speak(response, emotion='happy')
            return
            
        if 'как дела' in command_lower or 'как ты' in command_lower:
            response = "Отлично! Готова следить за игрой и поддерживать тебя!"
            self.tts.speak(response, emotion='happy')
            return
            
        if 'тест' in command_lower:
            response = "Тест пройден! Голосовой помощник работает отлично."
            self.tts.speak(response, emotion='neutral')
            return
            
        if 'статистика' in command_lower or 'стата' in command_lower:
            stats = self.achievements.get_stats_summary()
            self.tts.speak(f"Вот твоя статистика: {stats[:200]}", emotion='neutral')
            return
            
        if 'достижения' in command_lower:
            progress = self.achievements.get_progress_summary()
            self.tts.speak(progress, emotion='neutral')
            return
            
        if command_lower in ['стоп', 'остановись', 'выход', 'пока']:
            response = "До встречи! Было весело!"
            self.tts.speak(response, emotion='gentle')
            time.sleep(2)
            self.stop()
            return
        
        try:
            response = self.iris_brain.chat_with_user(command)
            if response:
                self.tts.speak(response, emotion='neutral')
            else:
                self.tts.speak(f"Интересно! Ты сказал: {command}", emotion='neutral')
        except Exception as e:
            print(f"[IRIS] Ошибка AI: {e}")
            self.tts.speak("Хм, дай мне секунду подумать...", emotion='neutral')
            
    def _on_cs2_event(self, event: GameEvent):
        """Обработка событий CS2"""
        print(f"[CS2] Событие: {event.event_type}")
        
        self.iris_brain.update_context(
            map_name=self.cs2_gsi.map.name,
            ct_score=self.cs2_gsi.map.ct_score,
            t_score=self.cs2_gsi.map.t_score,
            player_stats=self.cs2_gsi.get_player_stats(),
            event={'type': event.event_type, 'data': event.data}
        )
        
        response = None
        emotion = 'neutral'
        
        if event.event_type == 'ace':
            self.achievements.record_kill(round_kills=5)
            response = self.iris_brain.react_to_kill(event.data)
            emotion = 'excited'
            
        elif event.event_type in ['kill', 'double_kill', 'triple_kill', 'quadra_kill']:
            is_headshot = event.data.get('headshot', False)
            round_kills = event.data.get('round_kills', 1)
            self.achievements.record_kill(headshot=is_headshot, round_kills=round_kills)
            response = self.iris_brain.react_to_kill(event.data)
            emotion = 'excited' if round_kills >= 3 else 'happy'
            
        elif event.event_type == 'death':
            self.achievements.record_death()
            response = self.iris_brain.react_to_death(event.data)
            emotion = 'supportive'
            
        elif event.event_type == 'round_end':
            won = event.data.get('won', False)
            clutch = event.data.get('clutch_win', False)
            if won:
                self.achievements.record_round_win(clutch=clutch)
            else:
                self.achievements.record_round_loss()
            response = self.iris_brain.react_to_round_end(event.data)
            emotion = 'excited' if won else 'supportive'
            
        elif event.event_type == 'low_health':
            health = event.data.get('current_health', 100)
            self.achievements.record_low_health_survive(health)
            
        elif event.event_type in ['bomb_planted', 'bomb_defused', 'bomb_exploded']:
            if event.event_type == 'bomb_defused' and event.data.get('ninja_defuse'):
                self.achievements.record_ninja_defuse()
            response = self.iris_brain.react_to_bomb_event(event.event_type, event.data)
            emotion = 'tense' if event.event_type == 'bomb_planted' else 'excited'
            
        elif event.event_type == 'match_end':
            won = event.data.get('won', False)
            self.achievements.record_match_end(won=won)
            
        if response:
            self.tts.speak(response, emotion=emotion)
            
    def _on_stream_event(self, event: StreamEvent):
        """Обработка событий стрима"""
        print(f"[STREAM] Событие: {event.event_type}")
        
        response = None
        emotion = 'neutral'
        
        if event.event_type == 'donation':
            amount = event.data.get('amount', 0)
            currency = event.data.get('currency', 'RUB')
            self.achievements.record_donation(amount, currency)
            response = self.iris_brain.react_to_donation(event.data)
            emotion = 'excited'
            
        elif event.event_type == 'subscription':
            self.achievements.record_subscription()
            response = self.iris_brain.react_to_subscription(event.data)
            emotion = 'excited'
            
        elif event.event_type == 'raid':
            viewers = event.data.get('viewers', 0)
            self.achievements.record_raid(viewers)
            response = self.iris_brain.react_to_raid(event.data)
            emotion = 'excited'
            
        elif event.event_type == 'chat_message':
            self.achievements.record_chat_message()
            response = self.iris_brain.react_to_chat_message(event.data)
            
        elif event.event_type == 'follow':
            pass
            
        if response:
            self.tts.speak(response, emotion=emotion)
            
    def _on_achievement(self, achievement: Achievement):
        """Обработка разблокировки достижений"""
        message = f"Достижение разблокировано! {achievement.icon} {achievement.name}!"
        self.tts.speak(message, emotion='excited', priority=True)
        
    def _random_comment_loop(self):
        """Цикл случайных комментариев"""
        while self.is_running:
            time.sleep(120)
            
            if not self.is_running:
                break
                
            self.achievements.check_time_achievements()
            
            if not self.tts.is_busy():
                comment = self.iris_brain.generate_random_comment()
                if comment:
                    self.tts.speak(comment, emotion='neutral')
                    
    def _run_startup_sequence(self):
        """Последовательность запуска в стиле Iron Man"""
        import random
        
        startup_phrases = [
            ("Инициализация системы... Проверяю ядро.", 'scan', 1.5),
            ("Загрузка нейронных модулей... Всё в норме.", 'loading', 1.8),
            ("Сканирование аудио устройств...", 'scan', 1.2),
            ("Подключение к игровым серверам...", 'connect', 1.5),
            ("Калибровка голосового модуля... Тестирую.", 'check', 1.3),
            ("Проверка соединений завершена.", 'confirm', 1.0),
        ]
        
        greeting_variants = [
            "Все системы активны! Привет, я Ирис. Готова зажигать на стриме!",
            "Инициализация завершена! Ирис на связи. Давай устроим шоу!",
            "Протоколы загружены! Я Ирис, твоя AI-напарница. Поехали!",
            "Системы в норме! Привет! Я готова комментировать твои эпичные моменты!",
            "Ядро стабильно! Ирис активирована. Сегодня будет жарко!",
        ]
        
        time.sleep(2.5)
        
        for phrase, phase, duration in startup_phrases:
            self.visual.animate_phase(phase, duration)
            self.tts.speak(phrase, emotion='neutral')
            
            while self.tts.is_busy():
                time.sleep(0.1)
            
            time.sleep(0.3)
        
        self.visual.play_sound('ready', 0.8)
        time.sleep(0.3)
        
        greeting = random.choice(greeting_variants)
        self.tts.speak(greeting, emotion='excited')
        
        print("[IRIS] ✨ Последовательность запуска завершена!")
    
    def start(self):
        """Запуск Ирис"""
        self.is_running = True
        
        print("\n[IRIS] 🚀 Запуск визуального интерфейса (Iron Man startup)...")
        
        def on_power_up_complete():
            print("[IRIS] ⚡ Power-up завершён, запуск диагностики...")
            startup_thread = threading.Thread(target=self._run_startup_sequence, daemon=True)
            startup_thread.start()
        
        self.visual_thread = self.visual.run_async(on_power_up_complete)
        
        time.sleep(0.5)
        
        print("\n[IRIS] Запуск CS2 Game State Integration...")
        self.cs2_gsi.start()
        self.cs2_gsi.save_config_file()
        
        jwt_token = os.getenv('STREAMELEMENTS_JWT_TOKEN', '')
        if jwt_token:
            print("\n[IRIS] Подключение к StreamElements...")
            self.stream_elements.connect()
        else:
            print("\n[IRIS] ⚠️ STREAMELEMENTS_JWT_TOKEN не настроен - чат недоступен")
            
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
        
        print("\n" + "=" * 60)
        print("🌸 Ирис успешно запущена!")
        print("=" * 60)
        print()
        print("📋 Доступные функции:")
        print("   🎮 CS2 Game State Integration (порт 3000)")
        print("   💬 StreamElements чат и донаты")
        print("   🎤 Голосовое управление (скажите 'Ирис')")
        print("   🔊 Управление громкостью приложений")
        print("   🏆 Система достижений")
        print("   ✨ Визуальный интерфейс IO-style")
        print()
        print("🎤 Голос: Нежный женский (Edge TTS)")
        print("🧠 AI: Groq LLM (бесплатно)")
        print("👁️ Визуал: IO-style пульсирующий шар")
        print()
        print("Нажмите Ctrl+C или ESC в окне для остановки")
        print("=" * 60)
        
    def stop(self):
        """Остановка Ирис"""
        print("\n[IRIS] Остановка...")
        self.is_running = False
        
        self.achievements.save_stats()
        
        if hasattr(self, 'visual') and self.visual:
            self.visual.stop()
        
        self.voice_input.stop()
        self.stream_elements.disconnect()
        self.cs2_gsi.stop()
        self.tts.stop()
        
        print("[IRIS] До встречи на следующем стриме! 🌸")
        
    def run(self):
        """Основной цикл"""
        def signal_handler(sig, frame):
            self.stop()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        self.start()
        
        try:
            while self.is_running:
                if hasattr(self, 'visual') and self.visual and not self.visual.running:
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def main():
    """Точка входа"""
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                                                            ║")
    print("║   🌸 IRIS - AI Stream Companion                            ║")
    print("║   Голосовой ассистент для стримов                         ║")
    print("║                                                            ║")
    print("║   💜 Полностью бесплатные технологии:                      ║")
    print("║      • Edge TTS - нежный женский голос                    ║")
    print("║      • Vosk - офлайн распознавание речи                   ║")
    print("║      • Groq LLM - бесплатный AI                           ║")
    print("║                                                            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    iris = IrisAssistant()
    iris.run()


if __name__ == "__main__":
    main()
