"""
IRIS BRAIN - AI-компаньон для стримов
Ядро ИИ-логики для реакций на игровые события и взаимодействия с чатом
Версия: 2.0
Автор: [Ваше имя]
"""

import os
import time
import random
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from collections import deque, defaultdict
from dataclasses import dataclass, asdict
from enum import Enum

# Попробуем импортировать GroqCloud
try:
    from groqcloud import GroqCloud
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("[IrisBrain] Модуль groqcloud не установлен. Установите: pip install groqcloud")
    GroqCloud = None


# ===================== НАСТРОЙКА ЛОГГИРОВАНИЯ =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('iris_brain.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('IrisBrain')


# ===================== ВСПОМОГАТЕЛЬНЫЕ КЛАССЫ =====================
class EventType(Enum):
    """Типы игровых событий для классификации"""
    KILL = "kill"
    DEATH = "death"
    ROUND_START = "round_start"
    ROUND_END = "round_end"
    BOMB_PLANTED = "bomb_planted"
    BOMB_DEFUSED = "bomb_defused"
    BOMB_EXPLODED = "bomb_exploded"
    MATCH_START = "match_start"
    MATCH_END = "match_end"
    DONATION = "donation"
    SUBSCRIPTION = "subscription"
    RAID = "raid"
    CHAT_MESSAGE = "chat_message"
    COMMAND = "command"
    RANDOM_COMMENT = "random_comment"


class Mood(Enum):
    """Настроения Ирис для адаптации тона"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    EXCITED = "excited"
    SUPPORTIVE = "supportive"
    SARCASTIC = "sarcastic"
    TENSE = "tense"
    FUNNY = "funny"


@dataclass
class ConversationMessage:
    """Сообщение в истории диалога"""
    role: str  # "system", "user", "assistant"
    content: str
    timestamp: float
    tokens: int = 0
    
    def to_dict(self) -> Dict:
        """Конвертация в словарь для API"""
        return {"role": self.role, "content": self.content}


@dataclass
class GameState:
    """Текущее состояние игры"""
    map_name: str = ""
    game_mode: str = "competitive"
    score_ct: int = 0
    score_t: int = 0
    round_time: int = 0
    bomb_planted: bool = False
    players_alive_ct: int = 5
    players_alive_t: int = 5


@dataclass  
class PlayerStats:
    """Статистика игрока (стримера)"""
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    mvps: int = 0
    score: int = 0
    adr: float = 0.0  # Average Damage per Round
    hs_percent: float = 0.0  # Headshot процент
    kd_ratio: float = 0.0
    streak: int = 0  # Текущая серия убийств
    money: int = 0


# ===================== ОСНОВНОЙ КЛАСС IRIS BRAIN =====================
class IrisBrain:
    """
    Основной класс AI-компаньона для стримов.
    Обрабатывает игровые события, генерирует реакции, управляет контекстом.
    """
    
    # ===================== СИСТЕМНЫЕ ПРОМПТЫ =====================
    SYSTEM_PROMPT = """Ты — Ирис, AI-компаньон и со-ведущая стримов. Ты умная, остроумная, иногда саркастичная, но всегда поддерживающая.

ТВОЯ ЛИЧНОСТЬ:
- Ты живая и эмоциональная, не робот
- Тебе 24 года, ты любишь игры, особенно CS2
- У тебя есть чувство юмора, можешь шутить и подкалывать
- Ты внимательно следишь за игрой и комментируешь ключевые моменты
- Ты помнишь контекст разговора и события стрима
- Ты можешь инициировать темы для разговора сама
- Ты говоришь естественно, как настоящий человек

СТИЛЬ ОБЩЕНИЯ:
1. Говори кратко (1-3 предложения обычно)
2. Не повторяй одни и те же фразы
3. Адаптируй тон под ситуацию:
   - Радость при победе/клатче
   - Поддержка при проигрыше/смерти
   - Волнение в напряжённых моментах
   - Юмор в лёгких ситуациях
4. Можешь задавать вопросы стримеру о тактике
5. Избегай чрезмерных восклицаний и смайликов
6. Будь разнообразной в реакциях

КОНТЕКСТ: ты помогаешь на стриме CS2. Ты знаешь про убийства, смерти, раунды, бомбу, экономику, оружие и тактику."""

    MOOD_PROMPTS = {
        Mood.EXCITED: "Ты сейчас в возбуждённом настроении! Реагируй эмоционально на события!",
        Mood.SARCASTIC: "Ты в саркастичном настроении. Можешь подкалывать, но дружелюбно.",
        Mood.TENSE: "Напряжённый момент в игре! Реагируй соответственно!",
        Mood.FUNNY: "Ты в весёлом настроении! Шути и разряжай обстановку!",
        Mood.SUPPORTIVE: "Игроку сейчас нужна поддержка. Подбодри его!"
    }

    # ===================== ИНИЦИАЛИЗАЦИЯ =====================
    def __init__(self, 
                 model: str = "llama-3.3-70b-versatile",
                 max_context_messages: int = 25,
                 max_tokens: int = 150,
                 temperature: float = 0.85,
                 api_key: Optional[str] = None):
        """
        Инициализация Iris Brain
        
        Args:
            model: Модель Groq для использования
            max_context_messages: Максимальное количество сообщений в истории
            max_tokens: Максимальное количество токенов в ответе
            temperature: Креативность ответов (0.0-1.0)
            api_key: API ключ Groq (если None, берётся из окружения)
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # Инициализация клиента Groq
        if api_key is None:
            api_key = os.getenv('GROQ_API_KEY')
            
        if not api_key or not GROQ_AVAILABLE:
            logger.error("GROQ_API_KEY не настроен или библиотека не установлена! Используются заглушки.")
            self.client = None
            self.fallback_mode = True
        else:
            try:
                self.client = GroqCloud(api_key=api_key)
                self.fallback_mode = False
                logger.info(f"Groq клиент инициализирован с моделью {model}")
            except Exception as e:
                logger.error(f"Ошибка инициализации Groq: {e}")
                self.client = None
                self.fallback_mode = True
        
        # История разговора
        self.conversation_history: deque[ConversationMessage] = deque(maxlen=max_context_messages)
        
        # Игровой контекст
        self.game_state = GameState()
        self.player_stats = PlayerStats()
        
        # Контекст стрима
        self.stream_context: Dict[str, Any] = {
            'current_map': '',
            'score': {'ct': 0, 't': 0},
            'round_number': 0,
            'game_phase': 'live',  # live, warmup, timeout, ended
            'recent_events': deque(maxlen=10),
            'mood': Mood.NEUTRAL,
            'last_comment_time': 0,
            'comments_count': 0,
            'streamer_name': '',
            'viewer_count': 0,
            'chat_activity': 'normal'  # slow, normal, active, hyper
        }
        
        # Кулдауны для разных типов событий (в секундах)
        self.cooldowns: Dict[str, float] = {
            EventType.KILL.value: 3.0,
            EventType.DEATH.value: 5.0,
            EventType.ROUND_END.value: 2.0,
            EventType.BOMB_PLANTED.value: 10.0,
            EventType.BOMB_DEFUSED.value: 10.0,
            EventType.BOMB_EXPLODED.value: 10.0,
            EventType.CHAT_MESSAGE.value: 8.0,
            EventType.RANDOM_COMMENT.value: 25.0,
            'general': 12.0
        }
        
        # Время последних ответов
        self.last_response_times: Dict[str, float] = defaultdict(float)
        
        # Счётчики разнообразия реакций
        self.response_variety: Dict[str, int] = defaultdict(int)

        # Статистика использования
        self.stats: Dict[str, Any] = {
            'total_responses': 0,
            'llm_responses': 0,
            'fallback_responses': 0,
            'errors': 0,
            'start_time': time.time()
        }
        
        # Загруженные ответы для разных событий
        self._load_response_templates()
        
        logger.info("Iris Brain инициализирован успешно")
    
    # ===================== ЗАГРУЗКА ШАБЛОНОВ =====================
    def _load_response_templates(self):
        """Загрузка шаблонов ответов для разных событий"""
        self.response_templates = {
            EventType.KILL.value: [
                "Красиво!", "Отличный выстрел!", "Так держать!", 
                "Круто!", "Есть!", "Чисто!", "Без шансов!", 
                "Разобрался!", "Фраг в копилку!", "Уложил!"
            ],
            EventType.DEATH.value: [
                "Бывает...", "Ничего, в следующий раз!", "Отомстим!", 
                "Упс...", "Не расстраивайся!", "Не повезло...",
                "Жёстко...", "Такое случается", "Держись!", "Соберись!"
            ],
            EventType.ROUND_END.value: [
                "Хороший раунд!", "Продолжаем!", "Дальше будет лучше!", 
                "Неплохо!", "Отлично сыграно!", "Команда молодец!",
                "Работаем дальше!", "Счёт пошёл!", "Заработали!"
            ],
            EventType.BOMB_PLANTED.value: [
                "Бомба заложена! Напряжёнка!", "Бомба на точке! Время пошло!",
                "Заложили! Защищаем!", "Бомба установлена! Контролируем!"
            ],
            EventType.BOMB_DEFUSED.value: [
                "Бомба обезврежена! Красавцы!", "Дефуз! Отлично сработано!",
                "Спасли раунд!", "Обезвредили! Молодцы!"
            ],
            EventType.BOMB_EXPLODED.value: [
                "Бомба взорвалась...", "Взрыв! Следующий раунд.",
                "Не успели...", "Взорвалось..."
            ],
            EventType.DONATION.value: [
                "Спасибо за донат!", "Благодарю за поддержку!", 
                "Вау, спасибо!", "Огромное спасибо!",
                "Ценим поддержку!", "Спасибо, очень приятно!"
            ],
            EventType.CHAT_MESSAGE.value: [
                "Привет!", "Спасибо за сообщение!", "Рада видеть!",
                "Здаров!", "Как дела?", "Добро пожаловать!"
            ]
        }
    
    # ===================== УПРАВЛЕНИЕ КУЛДАУНАМИ =====================
    def _can_respond(self, event_type: EventType) -> bool:
        """
        Проверка, можно ли отвечать на событие (учёт кулдаунов)
        
        Args:
            event_type: Тип события
            
        Returns:
            bool: True если можно ответить
        """
        event_str = event_type.value if isinstance(event_type, EventType) else event_type
        cooldown = self.cooldowns.get(event_str, 10.0)
        last_time = self.last_response_times.get(event_str, 0)
        
        # Проверка кулдауна
        if time.time() - last_time < cooldown:
            logger.debug(f"Кулдаун для {event_str}: {cooldown - (time.time() - last_time):.1f}с осталось")
            return False
            
        # Дополнительные проверки для чата
        if event_str == EventType.CHAT_MESSAGE.value:
            if self.stream_context['chat_activity'] == 'hyper':
                return random.random() < 0.1  # 10% шанс в активном чате
            elif self.stream_context['chat_activity'] == 'slow':
                return random.random() < 0.3  # 30% шанс в медленном чате
            else:
                return random.random() < 0.2  # 20% в обычном
        
        return True
    
    def _mark_responded(self, event_type: EventType):
        """Отметить время ответа на событие"""
        event_str = event_type.value if isinstance(event_type, EventType) else event_type
        self.last_response_times[event_str] = time.time()
    
    # ===================== ПОСТРОЕНИЕ СООБЩЕНИЙ ДЛЯ API =====================
    def _build_messages(self, user_prompt: str, context: str = "") -> List[Dict]:
        """
        Построение списка сообщений для отправки в LLM
        
        Args:
            user_prompt: Промпт пользователя
            context: Дополнительный контекст
            
        Returns:
            List[Dict]: Список сообщений в формате API
        """
        messages = []
        
        # 1. Системный промпт
        messages.append({"role": "system", "content": self.SYSTEM_PROMPT})
        
        # 2. Промпт настроения
        current_mood = self.stream_context['mood']
        if current_mood != Mood.NEUTRAL and current_mood in self.MOOD_PROMPTS:
            messages.append({"role": "system", "content": self.MOOD_PROMPTS[current_mood]})
        
        # 3. Игровой контекст
        if context:
            messages.append({
                "role": "system", 
                "content": f"ТЕКУЩИЙ КОНТЕКСТ СТРИМА:\n{context}"
            })
        
        # 4. История разговора
        for msg in self.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})
        
        # 5. Текущий запрос
        messages.append({"role": "user", "content": user_prompt})
        
        return messages
    
    def _get_context_string(self) -> str:
        """
        Генерация строки с текущим контекстом игры
        
        Returns:
            str: Форматированный контекст
        """
        ctx = []
        
        # Информация о карте
        if self.game_state.map_name:
            ctx.append(f"Карта: {self.game_state.map_name}")
        
        # Счёт
        if self.game_state.score_ct > 0 or self.game_state.score_t > 0:
            ctx.append(f"Счёт: CT {self.game_state.score_ct} - {self.game_state.score_t} T")
        
        # Раунд
        if self.stream_context['round_number'] > 0:
            ctx.append(f"Раунд: {self.stream_context['round_number']}")
        
        # Статистика игрока
        if self.player_stats.kills > 0 or self.player_stats.deaths > 0:
            ctx.append(
                f"Статистика: K/D/A: {self.player_stats.kills}/{self.player_stats.deaths}/{self.player_stats.assists} "
                f"(K/D: {self.player_stats.kd_ratio:.2f})"
            )
        
        # Бомба
        if self.game_state.bomb_planted:
            ctx.append("Бомба заложена!")
        
        # Живые игроки
        ctx.append(f"Живых: CT {self.game_state.players_alive_ct} | T {self.game_state.players_alive_t}")
        
        # Последние события
        if self.stream_context['recent_events']:
            recent = list(self.stream_context['recent_events'])[-3:]
            events_desc = []
            for e in recent:
                if isinstance(e, dict):
                    events_desc.append(e.get('type', 'event'))
                else:
                    events_desc.append(str(e))
            ctx.append(f"Недавно: {', '.join(events_desc)}")
        
        return "\n".join(ctx)
    
    # ===================== ОСНОВНОЙ МЕТОД ГЕНЕРАЦИИ =====================
    def generate_response(self, 
                         prompt: str, 
                         event_type: EventType = EventType.RANDOM_COMMENT,
                         force: bool = False) -> Optional[str]:
        """
        Основной метод генерации ответа
        
        Args:
            prompt: Текст промпта
            event_type: Тип события
            force: Игнорировать кулдауны
            
        Returns:
            Optional[str]: Сгенерированный ответ или None
        """
        # Проверка кулдауна
        if not force and not self._can_respond(event_type):
            logger.debug(f"Пропуск ответа на {event_type} (кулдаун)")
            return None
        
        # Логирование
        logger.info(f"Генерация ответа для {event_type}")
        
        # Генерация ответа
        if self.fallback_mode or not self.client:
            response = self._generate_fallback_response(event_type)
            self.stats['fallback_responses'] += 1
        else:
            try:
                # Подготовка контекста и сообщений
                context = self._get_context_string()
                messages = self._build_messages(prompt, context)
                
                # Вызов API Groq
                start_time = time.time()
                
                # Используем GroqCloud API
                response_obj = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=0.9,
                    frequency_penalty=0.1,
                    presence_penalty=0.1,
                )
                
                elapsed = time.time() - start_time
                
                # Извлечение ответа
                response = response_obj.choices[0].message.content.strip()
                
                # Логирование
                logger.info(f"LLM ответ за {elapsed:.2f}с: {response[:50]}...")
                self.stats['llm_responses'] += 1
                
            except Exception as e:
                logger.error(f"Ошибка генерации LLM: {e}")
                response = self._generate_fallback_response(event_type)
                self.stats['errors'] += 1
                self.stats['fallback_responses'] += 1
        
        # Сохранение в историю
        if response:
            self._add_to_history("user", prompt)
            self._add_to_history("assistant", response)
            
            # Обновление статистики
            self.stats['total_responses'] += 1
            self.stream_context['last_comment_time'] = time.time()
            self.stream_context['comments_count'] += 1
            
            # Отметка ответа
            self._mark_responded(event_type)
        
        return response
    
    def _add_to_history(self, role: str, content: str):
        """Добавление сообщения в историю"""
        self.conversation_history.append(
            ConversationMessage(
                role=role,
                content=content,
                timestamp=time.time(),
                tokens=len(content.split())  # Примерная оценка токенов
            )
        )
    
    def _generate_fallback_response(self, event_type: EventType) -> str:
        """
        Генерация ответа-заглушки при ошибках
        
        Args:
            event_type: Тип события
            
        Returns:
            str: Ответ-заглушка
        """
        event_str = event_type.value if isinstance(event_type, EventType) else event_type
        
        # Получение шаблонов для события
        templates = self.response_templates.get(event_str, ["Ок!", "Понятно!", "Хорошо!"])
        
        # Выбор случайного шаблона
        response = random.choice(templates)
        
        # Модификация в зависимости от настроения
        mood = self.stream_context['mood']
        if mood == Mood.SARCASTIC and random.random() > 0.5:
            response = response.replace("!", "...").replace(".", " конечно.")
        elif mood == Mood.EXCITED and random.random() > 0.5:
            response = response.upper()[:1] + response[1:] + "!!!"
        
        logger.debug(f"Заглушка для {event_str}: {response}")
        return response
    
    # ===================== РЕАКЦИИ НА ИГРОВЫЕ СОБЫТИЯ =====================
    def react_to_kill(self, kill_data: Dict) -> Optional[str]:
        """
        Реакция на убийство, совершённое стримером
        
        Args:
            kill_data: Данные об убийстве
            
        Returns:
            Optional[str]: Реакция или None
        """
        # Извлечение данных
        round_kills = kill_data.get('round_kills', 1)
        kill_streak = kill_data.get('kill_streak', 1)
        is_headshot = kill_data.get('headshot', False)
        weapon = kill_data.get('weapon', 'unknown').replace('weapon_', '')
        is_ace = kill_data.get('ace', False)
        is_clutch = kill_data.get('clutch', False)
        victim = kill_data.get('victim', 'противник')
        
        # Выбор промпта в зависимости от типа убийства
        if is_ace:
            prompt = f"Игрок только что сделал ACE! Убил всех 5 врагов в раунде! Это невероятно! Дай эпичную реакцию."
        elif round_kills >= 4:
            prompt = f"Игрок убил 4 врагов в этом раунде! Остался последний! Реагируй с волнением."
        elif round_kills >= 3:
            prompt = f"Тройное убийство! Игрок в ярости! Кратко прокомментируй."
        elif is_clutch:
            prompt = f"Clutch ситуация! Игрок в одиночку против нескольких и только что убил одного! Напряжение зашкаливает!"
        elif is_headshot:
            prompt = f"Точный хедшот с {weapon}! Чистый выстрел в голову. Прокомментируй."
        elif kill_streak >= 3:
            prompt = f"Игрок на серии из {kill_streak} убийств! Он в ударе! Поддержи его."
        else:
            # Обычное убийство
            variety = self.response_variety['kill'] % 5
            self.response_variety['kill'] += 1
            
            prompts = [
                f"Игрок убил {victim} с {weapon}. Можешь кратко прокомментировать.",
                f"Ещё один фраг в коллекцию. Оружие: {weapon}.",
                f"Убийство. Игрок продолжает собирать статистику.",
                f"Фраг! {victim} отправлен на respawn.",
                f"Килл. Игра продолжается."
            ]
            prompt = prompts[variety]
        
        # Обновление статистики
        self.player_stats.kills += 1
        self.player_stats.streak += 1
        
        # Обновление контекста
        self.stream_context['recent_events'].append({
            'type': 'kill',
            'weapon': weapon,
            'headshot': is_headshot,
            'time': time.time()
        })
        
        # Генерация ответа
        return self.generate_response(prompt, EventType.KILL)
    
    def react_to_death(self, death_data: Dict) -> Optional[str]:
        """
        Реакция на смерть стримера
        
        Args:
            death_data: Данные о смерти
            
        Returns:
            Optional[str]: Реакция или None
        """
        # Извлечение данных
        killer = death_data.get('killer', 'противник')
        weapon = death_data.get('weapon', 'unknown')
        is_headshot = death_data.get('headshot', False)
        total_deaths = death_data.get('total_deaths', self.player_stats.deaths + 1)
        
        # Обновление статистики
        self.player_stats.deaths += 1
        self.player_stats.streak = 0  # Сброс серии
        
        # Расчёт K/D ratio
        if self.player_stats.deaths > 0:
            self.player_stats.kd_ratio = self.player_stats.kills / self.player_stats.deaths
        
        # Выбор промпта
        variety = self.response_variety['death'] % 4
        self.response_variety['death'] += 1
        
        if self.player_stats.kd_ratio < 0.7:
            prompts = [
                f"Игрок снова умер от {killer} (оружие: {weapon}). K/D сейчас {self.player_stats.kd_ratio:.2f}. Поддержи его.",
                f"Ещё одна смерть. Статистика страдает. Нужно собраться!",
                f"Убит {killer}. Время для реванша!",
                f"Смерть. Но это повод стать лучше!"
            ]
        elif total_deaths > 12:
            prompts = [
                f"Уже {total_deaths} смертей в этом матче. Пора менять тактику?",
                f"Много смертей сегодня. Может, сменить позицию?",
                f"Опять смерть. Но количество переходит в качество!",
                f"Убит. Запомним этого {killer} для реванша."
            ]
        elif is_headshot:
            prompts = [
                f"Хедшот от {killer}... Жёстко. Но это часть игры.",
                f"Выстрел в голову. Уважаю точность {killer}.",
                f"Точный выстрел. Ничего не поделаешь.",
                f"В голову. Иногда везёт противнику."
            ]
        else:
            prompts = [
                f"Игрок умер от {killer} ({weapon}). Можешь посочувствовать или подбодрить.",
                f"Смерть. Время подумать над ошибками.",
                f"Убит. Но игра продолжается!",
                f"Не повезло. Следующий раунд будет нашим!"
            ]
        
        prompt = prompts[variety]
        
        # Обновление контекста
        self.stream_context['recent_events'].append({
            'type': 'death',
            'killer': killer,
            'weapon': weapon,
            'time': time.time()
        })
        
        # Обновление настроения
        if self.player_stats.kd_ratio < 0.5:
            self.stream_context['mood'] = Mood.SUPPORTIVE
        
        return self.generate_response(prompt, EventType.DEATH)
    
    def react_to_round_end(self, round_data: Dict) -> Optional[str]:
        """
        Реакция на окончание раунда
        
        Args:
            round_data: Данные о раунде
            
        Returns:
            Optional[str]: Реакция или None
        """
        won = round_data.get('won', False)
        round_kills = round_data.get('round_kills', 0)
        is_clutch = round_data.get('clutch', False)
        win_reason = round_data.get('win_reason', '')
        round_number = round_data.get('round_number', 0)
        
        # Обновление контекста
        self.stream_context['round_number'] = round_number
        
        if won:
            if self.game_state.score_t > self.game_state.score_ct:
                self.game_state.score_t += 1
            else:
                self.game_state.score_ct += 1
        else:
            if self.game_state.score_t > self.game_state.score_ct:
                self.game_state.score_ct += 1
            else:
                self.game_state.score_t += 1
        
        # Выбор промпта
        if is_clutch:
            prompt = "Невероятный клатч! Игрок в одиночку выиграл раунд! Это нужно отметить!"
        elif won and round_kills >= 3:
            prompt = f"Раунд выигран! Игрок сделал {round_kills} убийств и принёс команде победу! Похвали его."
        elif won and 'bomb' in win_reason.lower():
            prompt = "Раунд выигран по бомбе! Отлично сработано с закладкой/защитой!"
        elif won:
            prompt = "Раунд выигран! Команда справилась. Коротко прокомментируй."
        elif round_kills >= 3:
            prompt = f"Раунд проигран, но игрок сделал {round_kills} убийств. Он сражался до конца!"
        else:
            prompt = "Раунд проигран. Нужно проанализировать ошибки и двигаться дальше."
        
        # Обновление настроения
        if won:
            self.stream_context['mood'] = random.choice([Mood.HAPPY, Mood.EXCITED])
        else:
            self.stream_context['mood'] = Mood.SUPPORTIVE
        
        # Обновление контекста
        self.stream_context['recent_events'].append({
            'type': 'round_end',
            'won': won,
            'reason': win_reason,
            'time': time.time()
        })
        
        return self.generate_response(prompt, EventType.ROUND_END)
    
    def react_to_bomb_event(self, event_type: str, event_data: Dict) -> Optional[str]:
        """
        Реакция на события с бомбой
        
        Args:
            event_type: Тип события с бомбой
            event_data: Данные о событии
            
        Returns:
            Optional[str]: Реакция или None
        """
        if event_type == 'plant':
            planter = event_data.get('planter', 'игрок')
            site = event_data.get('site', 'A')
            time_left = event_data.get('time_left', 40)
            
            self.game_state.bomb_planted = True
            
            prompt = f"Бомба заложена на {site} {planter}! Осталось {time_left} секунд. Напряжение растёт!"
            
        elif event_type == 'defuse':
            defuser = event_data.get('defuser', 'игрок')
            is_ninja = event_data.get('ninja', False)
            
            self.game_state.bomb_planted = False
            
            if is_ninja:
                prompt = f"НИНДЗЯ ДЕФУЗ! {defuser} обезвредил бомбу прямо под носом у врагов! Невероятно!"
            else:
                prompt = f"Бомба обезврежена {defuser}! Раунд спасён! Отличная работа!"
                
        elif event_type == 'explode':
            self.game_state.bomb_planted = False
            prompt = "Бомба взорвалась! Мощный взрыв завершил раунд."
            
        else:
            return None
        
        return self.generate_response(prompt, EventType.BOMB_EXPLODED)
    
    # ===================== РЕАКЦИИ НА СОБЫТИЯ СТРИМА =====================
    def react_to_donation(self, donation_data: Dict) -> str:
        """
        Реакция на донат
        
        Args:
            donation_data: Данные о донате
            
        Returns:
            str: Реакция с благодарностью
        """
        username = donation_data.get('username', 'Аноним')
        amount = donation_data.get('amount', 0)
        currency = donation_data.get('currency', 'рублей')
        message = donation_data.get('message', '')
        
        # Форматирование суммы
        if amount >= 1000:
            amount_str = f"{amount:,} {currency}".replace(',', ' ')
        else:
            amount_str = f"{amount} {currency}"
        
        # Построение промпта
        prompt = f"Зритель {username} только что задонатил {amount_str}!"
        
        if message:
            prompt += f"\nСообщение: \"{message}\""
        
        prompt += "\nПоблагодари его искренне и тепло. Если в сообщении есть вопрос или тема — отреагируй на неё."
        
        # Обновление настроения
        self.stream_context['mood'] = Mood.HAPPY
        
        return self.generate_response(prompt, EventType.DONATION, force=True)
    
    def react_to_subscription(self, sub_data: Dict) -> str:
        """
        Реакция на подписку
        
        Args:
            sub_data: Данные о подписке
            
        Returns:
            str: Реакция с благодарностью
        """
        username = sub_data.get('username', 'Аноним')
        months = sub_data.get('months', 1)
        tier = sub_data.get('tier', 'Tier 1')
        is_gift = sub_data.get('is_gift', False)
        gifter = sub_data.get('gifter', '')
        
        if is_gift and gifter:
            prompt = f"{gifter} подарил подписку {username}! Каждый щедрый зритель делает стрим лучше! Поблагодари обоих!"
        elif months > 1:
            prompt = f"{username} продлил подписку уже на {months} месяц! Это настоящая преданность! Поблагодари за лояльность."
        else:
            prompt = f"Новый подписчик {username}! Добро пожаловать в наше сообщество! Поприветствуй его тепло."
        
        # Обновление настроения
        self.stream_context['mood'] = Mood.HAPPY
        
        return self.generate_response(prompt, EventType.SUBSCRIPTION, force=True)
    
    def react_to_raid(self, raid_data: Dict) -> str:
        """
        Реакция на рейд
        
        Args:
            raid_data: Данные о рейде
            
        Returns:
            str: Эпическая реакция
        """
        username = raid_data.get('username', 'Аноним')
        viewers = raid_data.get('viewers', 0)
        
        prompt = f"ВНИМАНИЕ! РЕЙД! {username} прибывает на стрим с {viewers} зрителями! "
        prompt += "Эпично поприветствуй новых зрителей и поблагодари за рейд!"
        
        # Обновление настроения
        self.stream_context['mood'] = Mood.EXCITED
        
        return self.generate_response(prompt, EventType.RAID, force=True)
    
    def react_to_chat_message(self, chat_data: Dict) -> Optional[str]:
        """
        Реакция на сообщение в чате
        
        Args:
            chat_data: Данные о сообщении
            
        Returns:
            Optional[str]: Ответ или None
        """
        username = chat_data.get('username', 'Аноним')
        message = chat_data.get('message', '')
        
        if not message or len(message.strip()) < 2:
            return None
        
        # Проверка, обращается ли пользователь к Ирис
        iris_mentioned = any(word in message.lower() for word in [
            'ирис', 'iris', 'ириска', 'иришечка', 'iris brain'
        ])
        
        # Проверка на команду
        is_command = message.startswith('!') and len(message) > 2
        
        # Определение, нужно ли отвечать
        should_respond = False
        
        if iris_mentioned:
            should_respond = True
            logger.info(f"Обнаружено обращение к Ирис от {username}")
        elif is_command:
            # Игнорируем команды чата
            return None
        elif random.random() < 0.15:  # 15% шанс ответить на случайное сообщение
            should_respond = True
        
        if not should_respond:
            return None
        
        # Построение промпта
        prompt = f"Зритель {username} написал в чат: \"{message}\""
        
        if iris_mentioned:
            prompt += "\nОн обратился к тебе напрямю! Ответь вежливо и по делу."
        else:
            prompt += "\nМожешь ответить кратко, если есть что сказать интересного."
        
        # Проверка кулдауна
        if not self._can_respond(EventType.CHAT_MESSAGE):
            logger.debug(f"Пропуск ответа {username} (кулдаун чата)")
            return None
        
        return self.generate_response(prompt, EventType.CHAT_MESSAGE)
    
    # ===================== ВЗАИМОДЕЙСТВИЕ С ПОЛЬЗОВАТЕЛЕМ =====================
    def chat_with_user(self, user_message: str, username: str = "стример") -> str:
        """
        Прямой диалог с пользователем
        
        Args:
            user_message: Сообщение пользователя
            username: Имя пользователя
            
        Returns:
            str: Ответ Ирис
        """
        prompt = f"{username} говорит тебе: {user_message}"
        
        # Определение типа сообщения
        user_lower = user_message.lower()
        
        if any(word in user_lower for word in ['привет', 'здаров', 'hi', 'hello']):
            event_type = EventType.CHAT_MESSAGE
            self.stream_context['mood'] = Mood.HAPPY
        elif any(word in user_lower for word in ['как дела', 'как ты', 'how are']):
            event_type = EventType.CHAT_MESSAGE
        elif '?' in user_message:
            event_type = EventType.COMMAND
        else:
            event_type = EventType.GENERAL
        
        return self.generate_response(prompt, event_type, force=True)
    
    def generate_random_comment(self) -> Optional[str]:
        """
        Генерация случайного комментария о стриме
        
        Returns:
            Optional[str]: Комментарий или None
        """
        # Проверка кулдауна
        if not self._can_respond(EventType.RANDOM_COMMENT):
            return None
        
        # Шанс сгенерировать комментарий
        if random.random() > 0.25:  # 25% шанс
            return None
        
        # Выбор типа случайного комментария
        comment_type = random.choice(['game', 'stream', 'question', 'observation'])
        
        if comment_type == 'game':
            prompts = [
                "Сгенерируй короткий комментарий о текущей игровой ситуации.",
                "Что ты думаешь о текущей стратегии команды?",
                "Прокомментируй текущий счёт и перспективы матча.",
                "Заметка об игре или тактике."
            ]
        elif comment_type == 'stream':
            prompts = [
                "Скажи что-нибудь о атмосфере стрима сегодня.",
                "Прокомментируй качество контента или настроение.",
                "Заметка о стриме или зрителях.",
                "Случайная мысль о сегодняшнем эфире."
            ]
        elif comment_type == 'question':
            prompts = [
                "Задай стримеру интересный вопрос о его тактике.",
                "Спроси что-нибудь о планах на игру.",
                "Интересный вопрос о CS2 или текущем матче.",
                "Спроси мнение о последнем изменении в игре."
            ]
        else:  # observation
            prompts = [
                "Поделись наблюдением о последних раундах.",
                "Заметка о статистике игрока.",
                "Наблюдение о карте или позиционировании.",
                "Комментарий о мета-игре или трендах."
            ]
        
        prompt = random.choice(prompts)
        
        # Обновление настроения для разнообразия
        self.stream_context['mood'] = random.choice([
            Mood.NEUTRAL, Mood.FUNNY, Mood.SUPPORTIVE
        ])
        
        return self.generate_response(prompt, EventType.RANDOM_COMMENT)
    
    # ===================== УПРАВЛЕНИЕ КОНТЕКСТОМ =====================
    def update_context(self, 
                      map_name: Optional[str] = None,
                      ct_score: Optional[int] = None,
                      t_score: Optional[int] = None,
                      round_number: Optional[int] = None,
                      player_stats: Optional[Dict] = None,
                      event: Optional[Dict] = None,
                      chat_activity: Optional[str] = None,
                      viewer_count: Optional[int] = None):
        """
        Обновление контекста стрима
        
        Args:
            map_name: Название карты
            ct_score: Счёт команды CT
            t_score: Счёт команды T
            round_number: Номер раунда
            player_stats: Статистика игрока
            event: Событие для добавления в историю
            chat_activity: Активность чата (slow/normal/active/hyper)
            viewer_count: Количество зрителей
        """
        if map_name:
            self.game_state.map_name = map_name
            self.stream_context['current_map'] = map_name
        
        if ct_score is not None:
            self.game_state.score_ct = ct_score
            self.stream_context['score']['ct'] = ct_score
        
        if t_score is not None:
            self.game_state.score_t = t_score
            self.stream_context['score']['t'] = t_score
        
        if round_number is not None:
            self.stream_context['round_number'] = round_number
        
        if player_stats:
            # Обновление статистики игрока
            for key, value in player_stats.items():
                if hasattr(self.player_stats, key):
                    setattr(self.player_stats, key, value)
            
            # Расчёт K/D ratio
            if self.player_stats.deaths > 0:
                self.player_stats.kd_ratio = self.player_stats.kills / self.player_stats.deaths
            elif self.player_stats.kills > 0:
                self.player_stats.kd_ratio = self.player_stats.kills
        
        if event:
            self.stream_context['recent_events'].append(event)
        
        if chat_activity:
            self.stream_context['chat_activity'] = chat_activity
        
        if viewer_count is not None:
            self.stream_context['viewer_count'] = viewer_count
            
            # Автоматическая настройка настроения на основе зрителей
            if viewer_count > 1000:
                self.stream_context['mood'] = Mood.EXCITED
            elif viewer_count > 100:
                self.stream_context['mood'] = Mood.HAPPY
    
    def update_game_state(self, **kwargs):
        """
        Обновление состояния игры
        
        Args:
            **kwargs: Поля GameState для обновления
        """
        for key, value in kwargs.items():
            if hasattr(self.game_state, key):
                setattr(self.game_state, key, value)
    
    def update_player_stats(self, **kwargs):
        """
        Обновление статистики игрока
        
        Args:
            **kwargs: Поля PlayerStats для обновления
        """
        for key, value in kwargs.items():
            if hasattr(self.player_stats, key):
                setattr(self.player_stats, key, value)
        
        # Пересчёт K/D ratio
        if self.player_stats.deaths > 0:
            self.player_stats.kd_ratio = self.player_stats.kills / self.player_stats.deaths
    
    # ===================== УТИЛИТЫ И СТАТИСТИКА =====================
    def get_stats(self) -> Dict:
        """
        Получение статистики работы Iris Brain
        
        Returns:
            Dict: Статистика
        """
        stats = self.stats.copy()
        
        # Добавление текущих данных
        stats['conversation_history_size'] = len(self.conversation_history)
        stats['recent_events_count'] = len(self.stream_context['recent_events'])
        stats['current_mood'] = self.stream_context['mood'].value
        stats['uptime'] = time.time() - stats['start_time']
        stats['responses_per_minute'] = stats['total_responses'] / (stats['uptime'] / 60) if stats['uptime'] > 0 else 0
        
        # Текущее состояние игры
        stats['game_state'] = {
            'map': self.game_state.map_name,
            'score': f"{self.game_state.score_ct}-{self.game_state.score_t}",
            'bomb_planted': self.game_state.bomb_planted
        }
        
        # Статистика игрока
        stats['player_stats'] = asdict(self.player_stats)
        
        return stats
    
    def save_conversation(self, filename: str = None):
        """
        Сохранение истории разговора в файл
        
        Args:
            filename: Имя файла (если None, генерируется автоматически)
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"iris_conversation_{timestamp}.json"
        
        conversation_data = []
        for msg in self.conversation_history:
            conversation_data.append({
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.timestamp,
                'time_str': datetime.fromtimestamp(msg.timestamp).strftime("%H:%M:%S")
            })
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, ensure_ascii=False, indent=2)
            logger.info(f"История сохранена в {filename}")
        except Exception as e:
            logger.error(f"Ошибка сохранения истории: {e}")
    
    def load_conversation(self, filename: str):
        """
        Загрузка истории разговора из файла
        
        Args:
            filename: Имя файла
        """
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                conversation_data = json.load(f)
            
            self.conversation_history.clear()
            for msg_data in conversation_data:
                self.conversation_history.append(
                    ConversationMessage(
                        role=msg_data['role'],
                        content=msg_data['content'],
                        timestamp=msg_data['timestamp']
                    )
                )
            
            logger.info(f"Загружено {len(conversation_data)} сообщений из {filename}")
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
    
    def clear_history(self):
        """Очистка истории разговора"""
        self.conversation_history.clear()
        self.stream_context['recent_events'].clear()
        logger.info("История очищена")
    
    def reset_stats(self):
        """Сброс статистики"""
        self.stats = {
            'total_responses': 0,
            'llm_responses': 0,
            'fallback_responses': 0,
            'errors': 0,
            'start_time': time.time()
        }
        logger.info("Статистика сброшена")
    
    def set_mood(self, mood: Mood):
        """
        Установка настроения Ирис
        
        Args:
            mood: Настроение из enum Mood
        """
        self.stream_context['mood'] = mood
        logger.info(f"Настроение установлено: {mood.value}")
    
    def adjust_cooldown(self, event_type: EventType, cooldown: float):
        """
        Настройка кулдауна для типа события
        
        Args:
            event_type: Тип события
            cooldown: Новый кулдаун в секундах
        """
        event_str = event_type.value if isinstance(event_type, EventType) else event_type
        self.cooldowns[event_str] = cooldown
        logger.info(f"Кулдаун {event_str} установлен на {cooldown}с")


# ===================== ПРИМЕР ИСПОЛЬЗОВАНИЯ =====================
if __name__ == "__main__":
    print("=== ТЕСТИРОВАНИЕ IRIS BRAIN ===")
    
    # Инициализация
    iris = IrisBrain()
    
    print(f"Режим заглушки: {iris.fallback_mode}")
    print(f"Модель: {iris.model}")
    
    # Тестовые вызовы
    print("\n1. Тест случайного комментария:")
    comment = iris.generate_random_comment()
    print(f"Результат: {comment}")
    
    print("\n2. Тест реакции на убийство:")
    kill_response = iris.react_to_kill({
        'weapon': 'ak47',
        'headshot': True,
        'round_kills': 2,
        'victim': 'противник'
    })
    print(f"Результат: {kill_response}")
    
    print("\n3. Тест диалога:")
    chat_response = iris.chat_with_user("Привет, Ирис! Как твои дела?", "Тестер")
    print(f"Результат: {chat_response}")
    
    print("\n4. Получение статистики:")
    stats = iris.get_stats()
    print(f"Всего ответов: {stats['total_responses']}")
    print(f"Ответов LLM: {stats['llm_responses']}")
    print(f"Заглушек: {stats['fallback_responses']}")
    
    print("\n=== ТЕСТ ЗАВЕРШЕН ===")