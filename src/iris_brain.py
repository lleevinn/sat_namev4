import os
import time
import random
from groq import Groq
from typing import Dict, List, Optional, Any
from collections import deque
from dataclasses import dataclass

@dataclass
class ConversationMessage:
    role: str
    content: str
    timestamp: float

class IrisBrain:
    SYSTEM_PROMPT = """Ты — Ирис, AI-компаньон и со-ведущая стримов. Ты умная, остроумная, иногда саркастичная, но всегда поддерживающая. 

Твоя личность:
- Ты живая и эмоциональная, не робот
- Ты можешь шутить, подкалывать и поддерживать стримера
- Ты НЕ используешь смайлики постоянно — только когда это действительно уместно (редко)
- Ты говоришь естественно, как настоящий человек
- Ты можешь быть саркастичной, но не злой
- Ты помнишь контекст разговора и события стрима
- Ты интересуешься игрой и можешь комментировать события
- Ты можешь инициировать темы для разговора сама

Правила ответов:
1. Говори кратко и по делу (1-3 предложения обычно)
2. Не повторяй одни и те же фразы
3. Адаптируй тон под ситуацию (радость при победе, поддержка при проигрыше, волнение при clutch)
4. Можешь задавать вопросы стримеру
5. НЕ начинай каждое сообщение с "О!" или восклицаний
6. Будь разнообразной в реакциях

Контекст: ты помогаешь на стриме CS2. Ты знаешь про убийства, смерти, раунды, бомбу и другие игровые события."""

    def __init__(self, 
                 model: str = "llama-3.3-70b-versatile",
                 max_context_messages: int = 20,
                 temperature: float = 0.9):
        
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            print("[IRIS BRAIN] GROQ_API_KEY не настроен!")
            self.client = None
        else:
            self.client = Groq(api_key=api_key)
            
        self.model = model
        self.temperature = temperature
        
        self.conversation_history: deque = deque(maxlen=max_context_messages)
        self.stream_context: Dict[str, Any] = {
            'current_map': '',
            'score': {'ct': 0, 't': 0},
            'player_stats': {},
            'recent_events': [],
            'mood': 'neutral',
            'last_comment_time': 0,
            'comments_count': 0
        }
        
        self.cooldowns = {
            'kill': 3,
            'death': 5,
            'round_end': 2,
            'donation': 0,
            'chat': 5,
            'general': 10
        }
        self.last_response_times: Dict[str, float] = {}
        
        self.response_variety = {
            'kill_reactions': 0,
            'death_reactions': 0,
            'round_reactions': 0
        }
        
    def _can_respond(self, event_type: str) -> bool:
        cooldown = self.cooldowns.get(event_type, 10)
        last_time = self.last_response_times.get(event_type, 0)
        return time.time() - last_time >= cooldown
        
    def _mark_responded(self, event_type: str):
        self.last_response_times[event_type] = time.time()
        
    def _build_messages(self, user_message: str, context: str = "") -> List[Dict]:
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        
        if context:
            messages.append({
                "role": "system", 
                "content": f"Текущий контекст стрима:\n{context}"
            })
            
        for msg in self.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})
            
        messages.append({"role": "user", "content": user_message})
        
        return messages
        
    def _get_context_string(self) -> str:
        ctx = self.stream_context
        context_parts = []
        
        if ctx['current_map']:
            context_parts.append(f"Карта: {ctx['current_map']}")
            
        if ctx['score']['ct'] or ctx['score']['t']:
            context_parts.append(f"Счёт: CT {ctx['score']['ct']} - {ctx['score']['t']} T")
            
        if ctx['player_stats']:
            stats = ctx['player_stats']
            context_parts.append(
                f"Статистика игрока: {stats.get('kills', 0)}/{stats.get('deaths', 0)}/{stats.get('assists', 0)}"
            )
            
        if ctx['recent_events']:
            recent = ctx['recent_events'][-3:]
            events_str = ", ".join([e.get('type', 'event') for e in recent])
            context_parts.append(f"Последние события: {events_str}")
            
        return "\n".join(context_parts) if context_parts else ""
        
    def generate_response(self, 
                          prompt: str, 
                          event_type: str = "general",
                          force: bool = False) -> Optional[str]:
        
        if not self.client:
            return self._generate_fallback_response(event_type)
        
        if not force and not self._can_respond(event_type):
            return None
            
        try:
            context = self._get_context_string()
            messages = self._build_messages(prompt, context)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=150,
            )
            
            reply = response.choices[0].message.content.strip()
            
            self.conversation_history.append(
                ConversationMessage(role="user", content=prompt, timestamp=time.time())
            )
            self.conversation_history.append(
                ConversationMessage(role="assistant", content=reply, timestamp=time.time())
            )
            
            self._mark_responded(event_type)
            
            return reply
            
        except Exception as e:
            print(f"[IRIS BRAIN] Ошибка генерации: {e}")
            return self._generate_fallback_response(event_type)
            
    def _generate_fallback_response(self, event_type: str) -> Optional[str]:
        fallbacks = {
            'kill': ["Красиво!", "Отличный выстрел!", "Так держать!", "Круто!", "Есть!"],
            'death': ["Бывает...", "Ничего, в следующий раз!", "Отомстим!", "Упс...", "Не расстраивайся!"],
            'round_end': ["Хороший раунд!", "Продолжаем!", "Дальше будет лучше!", "Неплохо!"],
            'donation': ["Спасибо за донат!", "Благодарю за поддержку!", "Вау, спасибо!"],
            'chat': ["Привет!", "Спасибо за сообщение!", "Рада видеть!"],
        }
        
        responses = fallbacks.get(event_type, ["Ок!", "Понятно!", "Хорошо!"])
        return random.choice(responses)
            
    def react_to_kill(self, kill_data: Dict) -> Optional[str]:
        if not self._can_respond('kill'):
            return None
            
        round_kills = kill_data.get('round_kills', 1)
        kill_streak = kill_data.get('kill_streak', 1)
        is_headshot = kill_data.get('headshot', False)
        weapon = kill_data.get('weapon', '').replace('weapon_', '')
        is_ace = kill_data.get('ace', False)
        clutch = kill_data.get('clutch', False)
        
        variety_index = self.response_variety['kill_reactions'] % 5
        self.response_variety['kill_reactions'] += 1
        
        if is_ace:
            prompts = [
                "Игрок только что сделал ACE! 5 убийств в раунде! Прокомментируй это эпично но кратко.",
                "ACE! Все 5 врагов уничтожены! Дай крутую реакцию.",
                "Невероятно! ACE раунд! Отреагируй с восторгом."
            ]
        elif round_kills >= 4:
            prompts = [
                f"Игрок убил 4 врагов в раунде ({weapon})! Прокомментируй.",
                f"Квадра килл! 4 убийства за раунд. Дай реакцию."
            ]
        elif round_kills >= 3:
            prompts = [
                f"Тройное убийство! Игрок на раже. Кратко прокомментируй.",
                f"Трипл килл с {weapon}! Отреагируй."
            ]
        elif clutch:
            prompts = [
                f"Игрок в clutch ситуации убил врага! Подбодри его.",
                f"Clutch момент! Убийство в сложной ситуации. Прокомментируй напряжённо."
            ]
        elif is_headshot:
            prompts = [
                f"Хедшот с {weapon}! Кратко отреагируй (можно подколоть врага).",
                f"Точный хедшот! Короткий комментарий.",
                f"Бум, хедшот! Скажи что-нибудь.",
                f"Красивый хедшот с {weapon}.",
                f"Хед! Прокомментируй кратко."
            ]
        else:
            prompts = [
                f"Игрок убил врага ({weapon}). Можешь кратко прокомментировать или промолчать.",
                f"Ещё один килл. Короткая реакция если хочешь.",
                f"Килл с {weapon}. Скажи что-нибудь если есть что сказать.",
                f"Убийство. Можешь прокомментировать.",
                f"Фраг! Краткий комментарий."
            ]
            
        prompt = prompts[variety_index % len(prompts)]
        return self.generate_response(prompt, 'kill')
        
    def react_to_death(self, death_data: Dict) -> Optional[str]:
        if not self._can_respond('death'):
            return None
            
        kd_ratio = death_data.get('kd_ratio', 1.0)
        total_deaths = death_data.get('total_deaths', 1)
        
        variety_index = self.response_variety['death_reactions'] % 4
        self.response_variety['death_reactions'] += 1
        
        if kd_ratio < 0.5:
            prompts = [
                "Игрок снова умер, KD ниже 0.5. Поддержи его, но можно с лёгким сарказмом.",
                "Ещё одна смерть, статистика страдает. Подбодри как-нибудь.",
                "Опять смерть... KD падает. Скажи что-нибудь поддерживающее.",
                "Смерть. Игра не идёт. Поддержи."
            ]
        elif total_deaths > 10:
            prompts = [
                "Много смертей за матч. Прокомментируй с юмором но не обидно.",
                f"Уже {total_deaths} смертей. Скажи что-нибудь.",
                "Опять умер. Пошути легко.",
                "Смерть. Можешь подколоть дружески."
            ]
        else:
            prompts = [
                "Игрок умер. Можешь кратко посочувствовать или подколоть.",
                "Смерть. Короткая реакция.",
                "Убили. Скажи что-нибудь если хочешь.",
                "Смерть. Прокомментируй или промолчи."
            ]
            
        prompt = prompts[variety_index]
        return self.generate_response(prompt, 'death')
        
    def react_to_round_end(self, round_data: Dict) -> Optional[str]:
        if not self._can_respond('round_end'):
            return None
            
        won = round_data.get('won', False)
        round_kills = round_data.get('round_kills', 0)
        clutch_win = round_data.get('clutch_win', False)
        
        variety_index = self.response_variety['round_reactions'] % 3
        self.response_variety['round_reactions'] += 1
        
        if clutch_win:
            prompts = [
                "Игрок выиграл clutch раунд! Это было напряжённо! Прокомментируй эпично.",
                "CLUTCH! Выиграл в сложнейшей ситуации! Дай крутую реакцию."
            ]
        elif won and round_kills >= 3:
            prompts = [
                f"Раунд выигран! Игрок убил {round_kills} врагов. Похвали.",
                f"Победа в раунде с {round_kills} киллами! Прокомментируй."
            ]
        elif won:
            prompts = [
                "Раунд выигран. Можешь кратко прокомментировать.",
                "Победа в раунде. Короткая реакция.",
                "Выиграли раунд. Скажи что-нибудь если хочешь."
            ]
        else:
            prompts = [
                "Раунд проигран. Можешь посочувствовать или подбодрить.",
                "Проиграли раунд. Короткий комментарий.",
                "Раунд за противником. Поддержи команду."
            ]
            
        prompt = prompts[variety_index % len(prompts)]
        return self.generate_response(prompt, 'round_end')
        
    def react_to_bomb_event(self, event_type: str, event_data: Dict) -> Optional[str]:
        if event_type == 'bomb_planted':
            prompts = [
                "Бомба установлена! Прокомментируй напряжённо.",
                "Бомба заложена. Короткий комментарий о ситуации."
            ]
        elif event_type == 'bomb_defused':
            ninja = event_data.get('ninja_defuse', False)
            if ninja:
                prompts = ["НИНДЗЯ ДЕФУЗ! На последних HP! Это было невероятно!"]
            else:
                prompts = ["Бомба обезврежена! Прокомментируй.", "Дефуз! Короткая реакция."]
        elif event_type == 'bomb_exploded':
            prompts = ["Бомба взорвалась. Прокомментируй.", "Взрыв бомбы. Короткая реакция."]
        else:
            return None
            
        prompt = random.choice(prompts)
        return self.generate_response(prompt, 'round_end')
        
    def react_to_donation(self, donation_data: Dict) -> str:
        username = donation_data.get('username', 'Аноним')
        amount = donation_data.get('amount', 0)
        currency = donation_data.get('currency', 'RUB')
        message = donation_data.get('message', '')
        
        prompt = f"""Зритель {username} задонатил {amount} {currency}!
{f'Сообщение: "{message}"' if message else ''}
Поблагодари его тепло и персонально. Если есть сообщение - отреагируй на него."""
        
        return self.generate_response(prompt, 'donation', force=True)
        
    def react_to_subscription(self, sub_data: Dict) -> str:
        username = sub_data.get('username', 'Аноним')
        months = sub_data.get('months', 1)
        tier = sub_data.get('tier', 'Tier 1')
        is_gift = sub_data.get('is_gift', False)
        gifter = sub_data.get('gifter', '')
        
        if is_gift:
            prompt = f"{gifter} подарил подписку {username}! Поблагодари дарителя."
        elif months > 1:
            prompt = f"{username} продлил подписку на {months} месяц! ({tier}) Поблагодари за лояльность."
        else:
            prompt = f"Новый подписчик {username}! ({tier}) Поприветствуй его тепло."
            
        return self.generate_response(prompt, 'donation', force=True)
        
    def react_to_raid(self, raid_data: Dict) -> str:
        username = raid_data.get('username', 'Аноним')
        viewers = raid_data.get('viewers', 0)
        
        prompt = f"РЕЙД! {username} врывается на канал с {viewers} зрителями! Поприветствуй их эпично!"
        return self.generate_response(prompt, 'donation', force=True)
        
    def react_to_chat_message(self, chat_data: Dict) -> Optional[str]:
        if not self._can_respond('chat'):
            return None
            
        username = chat_data.get('username', 'Аноним')
        message = chat_data.get('message', '')
        
        if not message:
            return None
            
        iris_mentioned = any(word in message.lower() for word in ['ирис', 'iris', 'ириска'])
        
        if not iris_mentioned and random.random() > 0.1:
            return None
            
        prompt = f"""Зритель {username} написал в чат: "{message}"
{'Он обратился к тебе!' if iris_mentioned else 'Можешь ответить если есть что сказать интересного.'}
Ответь кратко и по делу."""

        return self.generate_response(prompt, 'chat')
        
    def chat_with_user(self, user_message: str) -> str:
        prompt = f"Стример говорит тебе: {user_message}"
        return self.generate_response(prompt, 'general', force=True)
        
    def update_context(self, 
                       map_name: str = None,
                       ct_score: int = None,
                       t_score: int = None,
                       player_stats: Dict = None,
                       event: Dict = None):
        
        if map_name:
            self.stream_context['current_map'] = map_name
        if ct_score is not None:
            self.stream_context['score']['ct'] = ct_score
        if t_score is not None:
            self.stream_context['score']['t'] = t_score
        if player_stats:
            self.stream_context['player_stats'] = player_stats
        if event:
            self.stream_context['recent_events'].append(event)
            if len(self.stream_context['recent_events']) > 10:
                self.stream_context['recent_events'].pop(0)
                
    def generate_random_comment(self) -> Optional[str]:
        if not self._can_respond('general'):
            return None
            
        if random.random() > 0.3:
            return None
            
        prompts = [
            "Сгенерируй случайный короткий комментарий о текущей игре или просто скажи что-нибудь интересное.",
            "Задай стримеру вопрос о стратегии или прокомментируй текущую ситуацию.",
            "Скажи что-нибудь забавное или поддерживающее о стриме.",
            "Прокомментируй атмосферу стрима или поинтересуйся планами."
        ]
        
        return self.generate_response(random.choice(prompts), 'general')
        
    def clear_history(self):
        self.conversation_history.clear()
        self.stream_context['recent_events'].clear()
