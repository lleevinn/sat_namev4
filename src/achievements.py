import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from collections import defaultdict

@dataclass
class Achievement:
    id: str
    name: str
    description: str
    icon: str = "🏆"
    unlocked: bool = False
    unlocked_at: Optional[float] = None
    progress: int = 0
    target: int = 1

@dataclass
class StreamStats:
    total_kills: int = 0
    total_deaths: int = 0
    total_assists: int = 0
    rounds_won: int = 0
    rounds_lost: int = 0
    clutches_won: int = 0
    aces: int = 0
    headshots: int = 0
    donations_received: int = 0
    donations_total: float = 0.0
    new_subscribers: int = 0
    raids_received: int = 0
    chat_messages: int = 0
    stream_duration: float = 0.0
    kill_streak_max: int = 0
    death_streak_max: int = 0
    current_kill_streak: int = 0
    current_death_streak: int = 0
    matches_played: int = 0
    matches_won: int = 0

class AchievementSystem:
    def __init__(self, achievement_callback: Optional[Callable[[Achievement], None]] = None):
        self.achievement_callback = achievement_callback
        self.stats = StreamStats()
        self.session_start = time.time()
        self.achievements: Dict[str, Achievement] = {}
        self._init_achievements()
        
    def _init_achievements(self):
        achievements_data = [
            ("first_blood", "Первая кровь", "Первое убийство на стриме", "🩸", 1),
            ("killing_spree", "Серия убийств", "5 убийств подряд без смерти", "🔥", 5),
            ("unstoppable", "Неостановимый", "10 убийств подряд без смерти", "⚡", 10),
            ("ace_master", "Мастер ACE", "Сделать ACE (5 убийств в раунде)", "🎯", 1),
            ("clutch_king", "Король клатчей", "Выиграть 3 clutch ситуации", "👑", 3),
            ("headhunter", "Охотник за головами", "50 хедшотов за стрим", "💀", 50),
            ("survivor", "Выживший", "Выжить с 1 HP", "❤️", 1),
            ("comeback_kid", "Камбэк", "Выиграть матч проигрывая 5+ раундов", "🔄", 1),
            ("popular", "Популярный", "Получить 10 сообщений в чате", "💬", 10),
            ("loved", "Любимец", "Получить 5 донатов", "💝", 5),
            ("whale_friend", "Друг китов", "Получить донат 1000+ рублей", "🐋", 1),
            ("raided", "Под рейдом", "Получить рейд 50+ зрителей", "🚀", 1),
            ("marathon", "Марафонец", "Стримить 4+ часа", "⏱️", 1),
            ("consistent", "Стабильный", "Положительный KD весь матч", "📈", 1),
            ("team_player", "Командный игрок", "10 ассистов за матч", "🤝", 10),
            ("economical", "Экономный", "Выиграть эко раунд", "💰", 1),
            ("ninja", "Ниндзя", "Дефуз бомбы на последней секунде", "🥷", 1),
            ("dedication", "Преданность", "10 матчей за сессию", "🎮", 10),
            ("sub_love", "Любовь подписчиков", "10 новых подписчиков", "💜", 10),
            ("perfect_round", "Идеальный раунд", "Выиграть раунд без потери HP", "✨", 1),
        ]
        
        for ach_id, name, desc, icon, target in achievements_data:
            self.achievements[ach_id] = Achievement(
                id=ach_id,
                name=name,
                description=desc,
                icon=icon,
                target=target
            )
            
    def _unlock_achievement(self, ach_id: str):
        if ach_id not in self.achievements:
            return
            
        achievement = self.achievements[ach_id]
        if achievement.unlocked:
            return
            
        achievement.unlocked = True
        achievement.unlocked_at = time.time()
        achievement.progress = achievement.target
        
        print(f"[ACHIEVEMENT] 🏆 Разблокировано: {achievement.name} - {achievement.description}")
        
        if self.achievement_callback:
            self.achievement_callback(achievement)
            
    def _update_progress(self, ach_id: str, progress: int = 1):
        if ach_id not in self.achievements:
            return
            
        achievement = self.achievements[ach_id]
        if achievement.unlocked:
            return
            
        achievement.progress += progress
        
        if achievement.progress >= achievement.target:
            self._unlock_achievement(ach_id)
            
    def record_kill(self, headshot: bool = False, round_kills: int = 1):
        self.stats.total_kills += 1
        self.stats.current_kill_streak += 1
        self.stats.current_death_streak = 0
        
        if self.stats.current_kill_streak > self.stats.kill_streak_max:
            self.stats.kill_streak_max = self.stats.current_kill_streak
            
        if headshot:
            self.stats.headshots += 1
            self._update_progress("headhunter", 1)
            
        if self.stats.total_kills == 1:
            self._unlock_achievement("first_blood")
            
        if self.stats.current_kill_streak >= 5:
            self._unlock_achievement("killing_spree")
            
        if self.stats.current_kill_streak >= 10:
            self._unlock_achievement("unstoppable")
            
        if round_kills >= 5:
            self.stats.aces += 1
            self._unlock_achievement("ace_master")
            
    def record_death(self):
        self.stats.total_deaths += 1
        self.stats.current_death_streak += 1
        self.stats.current_kill_streak = 0
        
        if self.stats.current_death_streak > self.stats.death_streak_max:
            self.stats.death_streak_max = self.stats.current_death_streak
            
    def record_assist(self):
        self.stats.total_assists += 1
        self._update_progress("team_player", 1)
        
    def record_round_win(self, clutch: bool = False, eco: bool = False, perfect: bool = False):
        self.stats.rounds_won += 1
        
        if clutch:
            self.stats.clutches_won += 1
            self._update_progress("clutch_king", 1)
            
        if eco:
            self._unlock_achievement("economical")
            
        if perfect:
            self._unlock_achievement("perfect_round")
            
    def record_round_loss(self):
        self.stats.rounds_lost += 1
        
    def record_low_health_survive(self, health: int):
        if health <= 1:
            self._unlock_achievement("survivor")
            
    def record_ninja_defuse(self):
        self._unlock_achievement("ninja")
        
    def record_donation(self, amount: float, currency: str = "RUB"):
        self.stats.donations_received += 1
        self.stats.donations_total += amount
        
        self._update_progress("loved", 1)
        
        if currency == "RUB" and amount >= 1000:
            self._unlock_achievement("whale_friend")
        elif currency == "USD" and amount >= 15:
            self._unlock_achievement("whale_friend")
            
    def record_subscription(self):
        self.stats.new_subscribers += 1
        self._update_progress("sub_love", 1)
        
    def record_raid(self, viewers: int):
        self.stats.raids_received += 1
        
        if viewers >= 50:
            self._unlock_achievement("raided")
            
    def record_chat_message(self):
        self.stats.chat_messages += 1
        self._update_progress("popular", 1)
        
    def record_match_end(self, won: bool, came_back: bool = False):
        self.stats.matches_played += 1
        
        if won:
            self.stats.matches_won += 1
            
            if came_back:
                self._unlock_achievement("comeback_kid")
                
            if self.stats.total_kills > self.stats.total_deaths:
                self._unlock_achievement("consistent")
                
        self._update_progress("dedication", 1)
        
    def check_time_achievements(self):
        duration_hours = (time.time() - self.session_start) / 3600
        self.stats.stream_duration = duration_hours
        
        if duration_hours >= 4:
            self._unlock_achievement("marathon")
            
    def get_unlocked_achievements(self) -> List[Achievement]:
        return [a for a in self.achievements.values() if a.unlocked]
        
    def get_locked_achievements(self) -> List[Achievement]:
        return [a for a in self.achievements.values() if not a.unlocked]
        
    def get_progress_summary(self) -> str:
        unlocked = len(self.get_unlocked_achievements())
        total = len(self.achievements)
        
        return f"Достижения: {unlocked}/{total}"
        
    def get_stats_summary(self) -> str:
        s = self.stats
        kd = s.total_kills / max(1, s.total_deaths)
        
        return f"""📊 Статистика стрима:
🎯 K/D/A: {s.total_kills}/{s.total_deaths}/{s.total_assists} (KD: {kd:.2f})
🏆 Раунды: {s.rounds_won}W / {s.rounds_lost}L
🔥 Макс. серия убийств: {s.kill_streak_max}
💀 Хедшоты: {s.headshots}
👑 Clutch побед: {s.clutches_won}
⭐ ACE: {s.aces}
💰 Донаты: {s.donations_received} ({s.donations_total:.0f} руб.)
💜 Подписчики: {s.new_subscribers}
💬 Сообщений в чате: {s.chat_messages}
⏱️ Время стрима: {s.stream_duration:.1f} ч"""

    def save_stats(self, filepath: str = "stream_stats.json"):
        data = {
            'stats': self.stats.__dict__,
            'achievements': {
                k: {
                    'unlocked': v.unlocked,
                    'unlocked_at': v.unlocked_at,
                    'progress': v.progress
                }
                for k, v in self.achievements.items()
            },
            'session_start': self.session_start
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"[ACHIEVEMENTS] Статистика сохранена в {filepath}")
        
    def load_stats(self, filepath: str = "stream_stats.json") -> bool:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for key, value in data.get('stats', {}).items():
                if hasattr(self.stats, key):
                    setattr(self.stats, key, value)
                    
            for ach_id, ach_data in data.get('achievements', {}).items():
                if ach_id in self.achievements:
                    self.achievements[ach_id].unlocked = ach_data.get('unlocked', False)
                    self.achievements[ach_id].unlocked_at = ach_data.get('unlocked_at')
                    self.achievements[ach_id].progress = ach_data.get('progress', 0)
                    
            print(f"[ACHIEVEMENTS] Статистика загружена из {filepath}")
            return True
            
        except FileNotFoundError:
            return False
        except Exception as e:
            print(f"[ACHIEVEMENTS] Ошибка загрузки: {e}")
            return False
