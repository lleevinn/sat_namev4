"""
IRIS - AI Stream Companion
Голосовой ассистент для стримов с CS2 интеграцией
Полностью бесплатные технологии (Edge TTS, Vosk, Groq)
Версия: 2.0.0 (Stable Build)
"""

import os
import sys
import time
import threading
import signal
import random
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Импорт основных модулей системы
from src.tts_engine import TTSEngine
from src.voice_input import VoiceInput
from src.cs2_gsi import CS2GameStateIntegration, GameEvent
from src.streamelements_client import StreamElementsClient, StreamEvent
from src.iris_brain import IrisBrain
from src.windows_audio import WindowsAudioController
from src.achievements import AchievementSystem, Achievement

# Попытка импорта визуального модуля (опционально)
try:
    from src.iris_visual import IrisVisual
    VISUAL_AVAILABLE = True
except ImportError:
    VISUAL_AVAILABLE = False
    print("[IRIS] Визуальный модуль не найден, работаем без интерфейса")

class IrisAssistant:
    """
    Главный класс Ирис - AI компаньона для стримов
    Отвечает за координацию всех компонентов системы:
    - Голосовой ввод/вывод
    - Интеграция с CS2
    - Обработка событий стрима
    - Система достижений
    - Визуализация (если доступна)
    """
    
    def __init__(self):
        """
        Инициализация всех компонентов системы Iris
        Выполняется в строгом порядке для избежания зависимостей
        """
        print("=" * 60)
        print("🌸 Запуск Ирис - AI Stream Companion v2.0.0")
        print("=" * 60)
        print()
        
        # Конфигурация системы (можно вынести в отдельный файл)
        self.CONFIG = {
            "cs2_gsi_port": 3000,
            "voice_wake_word": "ирис",
            "voice_sensitivity": 0.8,
            "tts_voice": "ru_female_soft",
            "tts_rate": 0,
            "tts_volume": 0.9,
            "visual_enabled": True,
            "random_comments_interval": 120,  # секунды
            "achievements_enabled": True,
            "cs2_integration": True,
            "streamelements_enabled": True,
        }
        
        # Флаг работы системы
        self.is_running = False
        
        # Инициализация компонентов
        self._initialize_visual()
        self._initialize_tts()
        self._initialize_ai_brain()
        self._initialize_game_integration()
        self._initialize_audio_controller()
        self._initialize_voice_input()
        self._initialize_achievements()
        self._initialize_streamelements()
        
        print()
        print("[IRIS] ✅ Все компоненты успешно инициализированы")
        print("[IRIS] 📊 Статус системы:")
        print(f"       • Визуализация: {'ВКЛ' if VISUAL_AVAILABLE and self.CONFIG['visual_enabled'] else 'ВЫКЛ'}")
        print(f"       • CS2 интеграция: {'ВКЛ' if self.CONFIG['cs2_integration'] else 'ВЫКЛ'}")
        print(f"       • StreamElements: {'ВКЛ' if self.CONFIG['streamelements_enabled'] else 'ВЫКЛ'}")
        print(f"       • Достижения: {'ВКЛ' if self.CONFIG['achievements_enabled'] else 'ВЫКЛ'}")
    
    def _initialize_visual(self):
        """Инициализация визуального интерфейса (IO-style)"""
        if VISUAL_AVAILABLE and self.CONFIG['visual_enabled']:
            print("[IRIS] Инициализация визуального интерфейса (IO-style)...")
            try:
                self.visual = IrisVisual(width=400, height=400)
                self.visual.set_status("Инициализация...")
            except Exception as e:
                print(f"[IRIS] Ошибка инициализации визуального интерфейса: {e}")
                VISUAL_AVAILABLE = False
        else:
            print("[IRIS] Визуальный интерфейс отключен в конфигурации")
            self.visual = None
    
    def _initialize_tts(self):
        """Инициализация системы преобразования текста в речь"""
        print("[IRIS] Инициализация TTS (нежный женский голос)...")
        try:
            self.tts = TTSEngine(
                voice=self.CONFIG["tts_voice"],
                rate=self.CONFIG["tts_rate"],
                volume=self.CONFIG["tts_volume"],
                visual_callback=self._on_visual_update if VISUAL_AVAILABLE else None
            )
        except Exception as e:
            print(f"[IRIS] Критическая ошибка TTS: {e}")
            print("[IRIS] Продолжаем без голосового вывода...")
            self.tts = None
    
    def _initialize_ai_brain(self):
        """Инициализация AI-мозга системы"""
        print("[IRIS] Инициализация AI мозга...")
        self.iris_brain = IrisBrain()
        
        # Проверка доступности AI-сервисов
        groq_key = os.getenv('GROQ_API_KEY', '')
        if not groq_key:
            print("[IRIS] ⚠️ GROQ_API_KEY не настроен - AI будет использовать fallback ответы")
    
    def _initialize_game_integration(self):
        """Инициализация интеграции с CS2"""
        if self.CONFIG['cs2_integration']:
            print("[IRIS] Инициализация CS2 Game State Integration...")
            try:
                self.cs2_gsi = CS2GameStateIntegration(
                    port=self.CONFIG["cs2_gsi_port"],
                    event_callback=self._on_cs2_event
                )
            except Exception as e:
                print(f"[IRIS] Ошибка инициализации CS2 GSI: {e}")
                self.CONFIG['cs2_integration'] = False
                self.cs2_gsi = None
        else:
            self.cs2_gsi = None
    
    def _initialize_audio_controller(self):
        """Инициализация контроллера аудио Windows"""
        print("[IRIS] Инициализация аудио контроллера...")
        try:
            self.audio_controller = WindowsAudioController()
        except Exception as e:
            print(f"[IRIS] Ошибка инициализации аудио контроллера: {e}")
            self.audio_controller = None
    
    def _initialize_voice_input(self):
        """Инициализация системы голосового ввода"""
        print("[IRIS] Инициализация голосового ввода...")
        try:
            self.voice_input = VoiceInput(
                wake_word=self.CONFIG["voice_wake_word"],
                sensitivity=self.CONFIG["voice_sensitivity"]
            )
            self.voice_input.set_command_callback(self.process_voice_command)
            self.voice_input.set_wake_callback(self._on_wake_word)
        except Exception as e:
            print(f"[IRIS] Ошибка инициализации голосового ввода: {e}")
            self.voice_input = None
    
    def _initialize_achievements(self):
        """Инициализация системы достижений"""
        if self.CONFIG['achievements_enabled']:
            print("[IRIS] Инициализация системы достижений...")
            try:
                self.achievements = AchievementSystem(
                    achievement_callback=self._on_achievement
                )
            except Exception as e:
                print(f"[IRIS] Ошибка инициализации системы достижений: {e}")
                self.achievements = None
        else:
            self.achievements = None
    
    def _initialize_streamelements(self):
        """Инициализация клиента StreamElements"""
        if self.CONFIG['streamelements_enabled']:
            print("[IRIS] Инициализация StreamElements клиента...")
            jwt_token = os.getenv('STREAMELEMENTS_JWT_TOKEN', '')
            if jwt_token:
                try:
                    self.stream_elements = StreamElementsClient(
                        event_callback=self._on_stream_event
                    )
                except Exception as e:
                    print(f"[IRIS] Ошибка инициализации StreamElements: {e}")
                    self.stream_elements = None
            else:
                print("[IRIS] ⚠️ STREAMELEMENTS_JWT_TOKEN не настроен - чат недоступен")
                self.stream_elements = None
        else:
            self.stream_elements = None
    
    def _on_visual_update(self, speaking: bool, intensity: float):
        """
        Обновление визуального интерфейса при разговоре
        
        Args:
            speaking: Флаг активности речи
            intensity: Интенсивность анимации (0.0-1.0)
        """
        if VISUAL_AVAILABLE and self.visual:
            self.visual.set_speaking(speaking, intensity)
    
    def _on_wake_word(self):
        """Обработка обнаружения wake word"""
        print("[IRIS] Wake word обнаружен!")
        if self.tts:
            self.tts.speak("Да?", emotion='neutral', priority=True)
        
        if VISUAL_AVAILABLE and self.visual:
            self.visual.pulse_animation(1.5, 0.8)
    
    def process_voice_command(self, command: str):
        """
        Основной обработчик голосовых команд
        
        Args:
            command: Распознанная текстовая команда
        """
        print(f"[IRIS] 💬 Получена команда: '{command}'")
        
        # Проверка на пустую команду
        if not command or command.strip() == "":
            response = "Да, я здесь! Чем могу помочь?"
            if self.tts:
                self.tts.speak(response, emotion='gentle')
            return
        
        command_lower = command.lower().strip()
        
        # Обработка аудио команд
        audio_keywords = ['громкость', 'тише', 'громче', 'выключи', 'включи', 'музык', 'звук', 'mute']
        if self.audio_controller and any(kw in command_lower for kw in audio_keywords):
            response = self.audio_controller.execute_voice_command(command)
            if self.tts:
                self.tts.speak(response, emotion='neutral')
            return
        
        # Базовые команды
        if 'привет' in command_lower:
            response = "Привет! Я Ирис, твоя AI-подруга на стриме!"
            emotion = 'happy'
            
        elif 'как дела' in command_lower or 'как ты' in command_lower:
            response = "Отлично! Готова следить за игрой и поддерживать тебя!"
            emotion = 'happy'
            
        elif 'тест' in command_lower:
            response = "Тест пройден! Голосовой помощник работает отлично."
            emotion = 'neutral'
            
        elif 'статистика' in command_lower or 'стата' in command_lower:
            if self.achievements:
                stats = self.achievements.get_stats_summary()
                response = f"Вот твоя статистика: {stats[:200]}"
            else:
                response = "Система достижений отключена."
            emotion = 'neutral'
            
        elif 'достижения' in command_lower:
            if self.achievements:
                progress = self.achievements.get_progress_summary()
                response = progress
            else:
                response = "Система достижений отключена."
            emotion = 'neutral'
            
        elif command_lower in ['стоп', 'остановись', 'выход', 'пока']:
            response = "До встречи! Было весело!"
            emotion = 'gentle'
            if self.tts:
                self.tts.speak(response, emotion=emotion)
            time.sleep(2)
            self.stop()
            return
        
        else:
            # Использование AI для обработки сложных команд
            try:
                response = self.iris_brain.chat_with_user(command)
                if response:
                    emotion = 'neutral'
                else:
                    response = f"Интересно! Ты сказал: {command}"
                    emotion = 'neutral'
            except Exception as e:
                print(f"[IRIS] Ошибка AI: {e}")
                response = "Хм, дай мне секунду подумать..."
                emotion = 'neutral'
        
        # Озвучивание ответа
        if self.tts:
            self.tts.speak(response, emotion=emotion)
        
        # Визуальная обратная связь
        if VISUAL_AVAILABLE and self.visual:
            self.visual.show_message(response[:50])
    
    def _on_cs2_event(self, event: GameEvent):
        """
        Обработка событий из CS2
        
        Args:
            event: Объект игрового события
        """
        if not self.CONFIG['cs2_integration'] or not self.cs2_gsi:
            return
            
        print(f"[CS2] Событие: {event.event_type}")
        
        # Обновление контекста AI
        try:
            self.iris_brain.update_context(
                map_name=self.cs2_gsi.map.name,
                ct_score=self.cs2_gsi.map.ct_score,
                t_score=self.cs2_gsi.map.t_score,
                player_stats=self.cs2_gsi.get_player_stats(),
                event={'type': event.event_type, 'data': event.data}
            )
        except Exception as e:
            print(f"[CS2] Ошибка обновления контекста: {e}")
        
        response = None
        emotion = 'neutral'
        
        # Обработка конкретных типов событий
        if event.event_type == 'ace':
            if self.achievements:
                self.achievements.record_kill(round_kills=5)
            response = self.iris_brain.react_to_kill(event.data)
            emotion = 'excited'
            
        elif event.event_type in ['kill', 'double_kill', 'triple_kill', 'quadra_kill']:
            is_headshot = event.data.get('headshot', False)
            round_kills = event.data.get('round_kills', 1)
            if self.achievements:
                self.achievements.record_kill(headshot=is_headshot, round_kills=round_kills)
            response = self.iris_brain.react_to_kill(event.data)
            emotion = 'excited' if round_kills >= 3 else 'happy'
            
        elif event.event_type == 'death':
            if self.achievements:
                self.achievements.record_death()
            response = self.iris_brain.react_to_death(event.data)
            emotion = 'supportive'
            
        elif event.event_type == 'round_end':
            won = event.data.get('won', False)
            clutch = event.data.get('clutch_win', False)
            if self.achievements:
                if won:
                    self.achievements.record_round_win(clutch=clutch)
                else:
                    self.achievements.record_round_loss()
            response = self.iris_brain.react_to_round_end(event.data)
            emotion = 'excited' if won else 'supportive'
            
        elif event.event_type == 'low_health':
            health = event.data.get('current_health', 100)
            if self.achievements:
                self.achievements.record_low_health_survive(health)
            response = f"Внимание! У тебя осталось {health} HP"
            emotion = 'tense'
            
        elif event.event_type in ['bomb_planted', 'bomb_defused', 'bomb_exploded']:
            if event.event_type == 'bomb_defused' and event.data.get('ninja_defuse'):
                if self.achievements:
                    self.achievements.record_ninja_defuse()
            response = self.iris_brain.react_to_bomb_event(event.event_type, event.data)
            emotion = 'tense' if event.event_type == 'bomb_planted' else 'excited'
            
        elif event.event_type == 'match_end':
            won = event.data.get('won', False)
            if self.achievements:
                self.achievements.record_match_end(won=won)
            response = "Матч завершен! Отличная игра!"
            emotion = 'excited' if won else 'supportive'
        
        # Озвучивание реакции
        if response and self.tts:
            self.tts.speak(response, emotion=emotion)
        
        # Визуальная реакция
        if VISUAL_AVAILABLE and self.visual:
            if emotion == 'excited':
                self.visual.pulse_animation(2.0, 1.0)
            elif emotion == 'supportive':
                self.visual.pulse_animation(1.5, 0.5)
    
    def _on_stream_event(self, event: StreamEvent):
        """
        Обработка событий стрима
        
        Args:
            event: Объект события стрима
        """
        if not self.CONFIG['streamelements_enabled'] or not self.stream_elements:
            return
            
        print(f"[STREAM] Событие: {event.event_type}")
        
        response = None
        emotion = 'neutral'
        
        # Обработка типов событий стрима
        if event.event_type == 'donation':
            amount = event.data.get('amount', 0)
            currency = event.data.get('currency', 'RUB')
            if self.achievements:
                self.achievements.record_donation(amount, currency)
            response = self.iris_brain.react_to_donation(event.data)
            emotion = 'excited'
            
        elif event.event_type == 'subscription':
            if self.achievements:
                self.achievements.record_subscription()
            response = self.iris_brain.react_to_subscription(event.data)
            emotion = 'excited'
            
        elif event.event_type == 'raid':
            viewers = event.data.get('viewers', 0)
            if self.achievements:
                self.achievements.record_raid(viewers)
            response = self.iris_brain.react_to_raid(event.data)
            emotion = 'excited'
            
        elif event.event_type == 'chat_message':
            if self.achievements:
                self.achievements.record_chat_message()
            response = self.iris_brain.react_to_chat_message(event.data)
            emotion = 'neutral'
            
        elif event.event_type == 'follow':
            if self.achievements:
                self.achievements.record_follow()
            response = "Спасибо за фолов! Рада тебя видеть!"
            emotion = 'happy'
        
        # Озвучивание реакции
        if response and self.tts:
            self.tts.speak(response, emotion=emotion)
    
    def _on_achievement(self, achievement: Achievement):
        """
        Обработка разблокировки достижений
        
        Args:
            achievement: Объект достижения
        """
        print(f"[ACHIEVEMENT] Разблокировано: {achievement.name}")
        message = f"Достижение разблокировано! {achievement.icon} {achievement.name}!"
        
        if self.tts:
            self.tts.speak(message, emotion='excited', priority=True)
        
        if VISUAL_AVAILABLE and self.visual:
            self.visual.show_achievement(achievement.name, achievement.description)
    
    def _random_comment_loop(self):
        """
        Цикл случайных комментариев
        Генерирует периодические комментарии для поддержания интерактивности
        """
        while self.is_running:
            try:
                time.sleep(self.CONFIG['random_comments_interval'])
                
                if not self.is_running:
                    break
                
                # Проверка временных достижений
                if self.achievements:
                    self.achievements.check_time_achievements()
                
                # Генерация случайного комментария, если система не занята
                if self.tts and not self.tts.is_busy():
                    comment = self.iris_brain.generate_random_comment()
                    if comment:
                        self.tts.speak(comment, emotion='neutral')
                        
                        if VISUAL_AVAILABLE and self.visual:
                            self.visual.show_message(comment[:40])
                            
            except Exception as e:
                print(f"[IRIS] Ошибка в цикле комментариев: {e}")
    
    def _run_startup_sequence(self):
        """
        Последовательность запуска в стиле Iron Man
        Создает эпичную атмосферу запуска системы
        """
        if not self.tts:
            return
            
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
        
        # Проход по этапам запуска
        for phrase, phase, duration in startup_phrases:
            if VISUAL_AVAILABLE and self.visual:
                self.visual.animate_phase(phase, duration)
            
            self.tts.speak(phrase, emotion='neutral')
            
            # Ожидание завершения речи
            while self.tts.is_busy():
                time.sleep(0.1)
            
            time.sleep(0.3)
        
        # Финальное приветствие
        if VISUAL_AVAILABLE and self.visual:
            self.visual.play_sound('ready', 0.8)
            time.sleep(0.3)
        
        greeting = random.choice(greeting_variants)
        self.tts.speak(greeting, emotion='excited')
        
        print("[IRIS] ✨ Последовательность запуска завершена!")
    
    def start(self):
        """
        Основной запуск системы Iris
        Активирует все компоненты в правильном порядке
        """
        self.is_running = True
        
        print("\n[IRIS] 🚀 Запуск основных систем...")
        
        # Запуск визуального интерфейса (если доступен)
        if VISUAL_AVAILABLE and self.CONFIG['visual_enabled'] and self.visual:
            print("[IRIS] Запуск визуального интерфейса...")
            
            def on_power_up_complete():
                print("[IRIS] ⚡ Power-up завершён, запуск диагностики...")
                startup_thread = threading.Thread(target=self._run_startup_sequence, daemon=True)
                startup_thread.start()
            
            self.visual_thread = threading.Thread(
                target=self.visual.run_async,
                args=(on_power_up_complete,),
                daemon=True
            )
            self.visual_thread.start()
            time.sleep(0.5)
        
        # Запуск интеграции с CS2
        if self.CONFIG['cs2_integration'] and self.cs2_gsi:
            print("\n[IRIS] Запуск CS2 Game State Integration...")
            try:
                self.cs2_gsi.start()
                self.cs2_gsi.save_config_file()
                print(f"[IRIS] CS2 GSI запущен на порту {self.CONFIG['cs2_gsi_port']}")
            except Exception as e:
                print(f"[IRIS] Ошибка запуска CS2 GSI: {e}")
        
        # Подключение к StreamElements
        if self.CONFIG['streamelements_enabled'] and self.stream_elements:
            print("\n[IRIS] Подключение к StreamElements...")
            try:
                self.stream_elements.connect()
                print("[IRIS] StreamElements подключен успешно")
            except Exception as e:
                print(f"[IRIS] Ошибка подключения к StreamElements: {e}")
        
        # Запуск голосового ввода
        if self.voice_input:
            print("\n[IRIS] Запуск голосового ввода...")
            try:
                self.voice_input.start()
                print(f"[IRIS] Голосовой ввод активирован. Wake word: '{self.CONFIG['voice_wake_word']}'")
            except Exception as e:
                print(f"[IRIS] Ошибка запуска голосового ввода: {e}")
        
        # Запуск цикла случайных комментариев
        print("\n[IRIS] Запуск цикла случайных комментариев...")
        self.random_comment_thread = threading.Thread(
            target=self._random_comment_loop,
            daemon=True
        )
        self.random_comment_thread.start()
        
        # Вывод итоговой информации
        self._print_startup_summary()
    
    def _print_startup_summary(self):
        """Вывод сводной информации о запущенной системе"""
        print("\n" + "=" * 60)
        print("🌸 Ирис успешно запущена!")
        print("=" * 60)
        print()
        print("📋 Доступные функции:")
        
        if self.CONFIG['cs2_integration'] and self.cs2_gsi:
            print("   🎮 CS2 Game State Integration (активен)")
        else:
            print("   🎮 CS2 Game State Integration (отключен)")
        
        if self.CONFIG['streamelements_enabled'] and self.stream_elements:
            print("   💬 StreamElements чат и донаты (активен)")
        else:
            print("   💬 StreamElements (отключен)")
        
        if self.voice_input:
            print("   🎤 Голосовое управление (активно)")
            print(f"      Wake word: '{self.CONFIG['voice_wake_word']}'")
        else:
            print("   🎤 Голосовое управление (отключено)")
        
        if self.audio_controller:
            print("   🔊 Управление громкостью приложений (активно)")
        else:
            print("   🔊 Управление громкостью (отключено)")
        
        if self.achievements:
            print("   🏆 Система достижений (активна)")
        else:
            print("   🏆 Система достижений (отключена)")
        
        if VISUAL_AVAILABLE and self.CONFIG['visual_enabled'] and self.visual:
            print("   ✨ Визуальный интерфейс IO-style (активен)")
        else:
            print("   ✨ Визуальный интерфейс (отключен)")
        
        print()
        print("⚙️ Технологический стек:")
        print("   🎤 Голос: Нежный женский (Edge TTS)")
        print("   🧠 AI: Groq LLM + локальные модели")
        print("   👂 Распознавание: Vosk (офлайн)")
        
        if VISUAL_AVAILABLE and self.CONFIG['visual_enabled']:
            print("   👁️ Визуал: IO-style пульсирующий шар")
        
        print()
        print("🔧 Управление:")
        print("   • Скажите 'Ирис' для активации голосового управления")
        print("   • Нажмите Ctrl+C в консоли для остановки")
        
        if VISUAL_AVAILABLE and self.CONFIG['visual_enabled']:
            print("   • Нажмите ESC в окне визуализации для остановки")
        
        print()
        print("=" * 60)
    
    def stop(self):
        """
        Корректная остановка системы
        Сохраняет состояние и освобождает ресурсы
        """
        print("\n[IRIS] Остановка системы...")
        self.is_running = False
        
        # Сохранение статистики достижений
        if self.achievements:
            print("[IRIS] Сохранение статистики достижений...")
            self.achievements.save_stats()
        
        # Остановка визуального интерфейса
        if VISUAL_AVAILABLE and self.visual:
            print("[IRIS] Остановка визуального интерфейса...")
            try:
                self.visual.stop()
            except Exception as e:
                print(f"[IRIS] Ошибка остановки визуального интерфейса: {e}")
        
        # Остановка голосового ввода
        if self.voice_input:
            print("[IRIS] Остановка голосового ввода...")
            try:
                self.voice_input.stop()
            except Exception as e:
                print(f"[IRIS] Ошибка остановки голосового ввода: {e}")
        
        # Отключение от StreamElements
        if self.stream_elements:
            print("[IRIS] Отключение от StreamElements...")
            try:
                self.stream_elements.disconnect()
            except Exception as e:
                print(f"[IRIS] Ошибка отключения от StreamElements: {e}")
        
        # Остановка CS2 интеграции
        if self.cs2_gsi:
            print("[IRIS] Остановка CS2 Game State Integration...")
            try:
                self.cs2_gsi.stop()
            except Exception as e:
                print(f"[IRIS] Ошибка остановки CS2 GSI: {e}")
        
        # Остановка TTS
        if self.tts:
            print("[IRIS] Остановка TTS системы...")
            try:
                self.tts.stop()
            except Exception as e:
                print(f"[IRIS] Ошибка остановки TTS: {e}")
        
        # Короткая пауза для завершения операций
        time.sleep(1)
        
        print("[IRIS] ✅ Все системы остановлены")
        print("[IRIS] До встречи на следующем стриме! 🌸")
        print("=" * 60)
    
    def run(self):
        """
        Основной цикл работы системы
        Ожидает сигналов завершения и управляет жизненным циклом
        """
        def signal_handler(sig, frame):
            """Обработчик сигналов завершения"""
            print(f"\n[IRIS] Получен сигнал {sig}, остановка...")
            self.stop()
            sys.exit(0)
        
        # Настройка обработчиков сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Запуск системы
        self.start()
        
        try:
            # Основной цикл ожидания
            while self.is_running:
                # Проверка состояния визуального интерфейса
                if VISUAL_AVAILABLE and self.visual and not self.visual.running:
                    print("[IRIS] Визуальный интерфейс закрыт, остановка...")
                    break
                
                # Короткая пауза
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n[IRIS] Прервано пользователем")
        except Exception as e:
            print(f"\n[IRIS] Неожиданная ошибка: {e}")
        finally:
            # Гарантированная остановка
            self.stop()


def main():
    """
    Главная функция - точка входа в приложение
    Отвечает за инициализацию и запуск системы
    """
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                                                            ║")
    print("║   🌸 IRIS - AI Stream Companion v2.0.0                     ║")
    print("║   Голосовой ассистент для стримов                         ║")
    print("║                                                            ║")
    print("║   💜 Полностью бесплатные технологии:                      ║")
    print("║      • Edge TTS - нежный женский голос                    ║")
    print("║      • Vosk - офлайн распознавание речи                   ║")
    print("║      • Groq LLM - бесплатный AI                           ║")
    print("║                                                            ║")
    print("║   🚀 Быстрый старт:                                       ║")
    print("║      1. Запустите CS2                                     ║")
    print("║      2. Настройте Game State Integration                  ║")
    print("║      3. Скажите 'Ирис' для активации                      ║")
    print("║                                                            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    # Проверка критических зависимостей
    print("[SYSTEM] Проверка системных требований...")
    
    # Проверка Python версии
    if sys.version_info < (3, 8):
        print("[ERROR] Требуется Python 3.8 или выше")
        sys.exit(1)
    
    # Проверка наличия .env файла
    if not os.path.exists('.env'):
        print("[WARN] Файл .env не найден. Создан шаблон конфигурации.")
        with open('.env', 'w', encoding='utf-8') as f:
            f.write("# Конфигурация IRIS AI Companion\n")
            f.write("# Получите ключи на соответствующих сервисах\n\n")
            f.write("# Groq AI API (бесплатный)\n")
            f.write("# GROQ_API_KEY=your_groq_api_key_here\n\n")
            f.write("# StreamElements JWT токен\n")
            f.write("# STREAMELEMENTS_JWT_TOKEN=your_jwt_token_here\n\n")
            f.write("# Другие настройки\n")
            f.write("# LOG_LEVEL=INFO\n")
    
    # Создание экземпляра и запуск системы
    try:
        iris = IrisAssistant()
        iris.run()
    except Exception as e:
        print(f"[FATAL] Критическая ошибка при запуске: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()