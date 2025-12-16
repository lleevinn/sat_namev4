import json
import time
import threading
from flask import Flask, request, jsonify
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, List, Any
from collections import deque

@dataclass
class PlayerState:
    name: str = ""
    team: str = ""
    health: int = 100
    armor: int = 0
    helmet: bool = False
    money: int = 0
    round_kills: int = 0
    round_killhs: int = 0
    equip_value: int = 0
    kills: int = 0
    assists: int = 0
    deaths: int = 0
    mvps: int = 0
    score: int = 0
    weapon: str = ""
    
@dataclass 
class RoundState:
    phase: str = ""
    bomb: str = ""
    win_team: str = ""
    
@dataclass
class MapState:
    name: str = ""
    mode: str = ""
    phase: str = ""
    round: int = 0
    ct_score: int = 0
    t_score: int = 0
    
@dataclass
class GameEvent:
    event_type: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

class CS2GameStateIntegration:
    def __init__(self, 
                 port: int = 3000,
                 event_callback: Optional[Callable[[GameEvent], None]] = None):
        
        self.port = port
        self.event_callback = event_callback
        
        self.player = PlayerState()
        self.round = RoundState()
        self.map = MapState()
        self.previous_state: Dict = {}
        
        self.events_history: deque = deque(maxlen=100)
        self.kill_streak = 0
        self.round_start_kills = 0
        self.clutch_situation = False
        self.clutch_enemies = 0
        
        self.app = Flask(__name__)
        self._setup_routes()
        
        self.server_thread = None
        self.is_running = False
        
    def _setup_routes(self):
        @self.app.route('/', methods=['POST'])
        def gsi_handler():
            try:
                data = request.get_json()
                if data:
                    self._process_game_state(data)
                return jsonify({"status": "ok"})
            except Exception as e:
                print(f"[CS2 GSI] Ошибка обработки: {e}")
                return jsonify({"status": "error"}), 500
                
        @self.app.route('/health', methods=['GET'])
        def health_check():
            return jsonify({
                "status": "running",
                "player": self.player.name,
                "map": self.map.name,
                "round": self.map.round
            })
            
    def _process_game_state(self, data: Dict):
        player_data = data.get('player', {})
        if player_data:
            state = player_data.get('state', {})
            match_stats = player_data.get('match_stats', {})
            weapons = player_data.get('weapons', {})
            
            old_health = self.player.health
            old_kills = self.player.kills
            old_deaths = self.player.deaths
            old_round_kills = self.player.round_kills
            
            self.player.name = player_data.get('name', self.player.name)
            self.player.team = player_data.get('team', self.player.team)
            self.player.health = state.get('health', self.player.health)
            self.player.armor = state.get('armor', self.player.armor)
            self.player.helmet = state.get('helmet', self.player.helmet)
            self.player.money = state.get('money', self.player.money)
            self.player.round_kills = state.get('round_kills', self.player.round_kills)
            self.player.round_killhs = state.get('round_killhs', self.player.round_killhs)
            self.player.equip_value = state.get('equip_value', self.player.equip_value)
            
            self.player.kills = match_stats.get('kills', self.player.kills)
            self.player.assists = match_stats.get('assists', self.player.assists)
            self.player.deaths = match_stats.get('deaths', self.player.deaths)
            self.player.mvps = match_stats.get('mvps', self.player.mvps)
            self.player.score = match_stats.get('score', self.player.score)
            
            for weapon_key, weapon_data in weapons.items():
                if weapon_data.get('state') == 'active':
                    self.player.weapon = weapon_data.get('name', '')
                    break
                    
            if self.player.kills > old_kills:
                self._emit_kill_event(self.player.kills - old_kills)
                
            if self.player.deaths > old_deaths:
                self._emit_death_event()
                
            if self.player.health < old_health and self.player.health > 0:
                self._emit_damage_event(old_health - self.player.health)
                
        round_data = data.get('round', {})
        if round_data:
            old_phase = self.round.phase
            old_bomb = self.round.bomb
            
            self.round.phase = round_data.get('phase', self.round.phase)
            self.round.bomb = round_data.get('bomb', self.round.bomb)
            self.round.win_team = round_data.get('win_team', self.round.win_team)
            
            if self.round.phase == 'freezetime' and old_phase != 'freezetime':
                self._emit_round_start_event()
                
            if self.round.phase == 'over' and old_phase != 'over':
                self._emit_round_end_event()
                
            if self.round.bomb == 'planted' and old_bomb != 'planted':
                self._emit_bomb_planted_event()
                
            if self.round.bomb == 'defused' and old_bomb != 'defused':
                self._emit_bomb_defused_event()
                
            if self.round.bomb == 'exploded' and old_bomb != 'exploded':
                self._emit_bomb_exploded_event()
                
        map_data = data.get('map', {})
        if map_data:
            old_round = self.map.round
            
            self.map.name = map_data.get('name', self.map.name)
            self.map.mode = map_data.get('mode', self.map.mode)
            self.map.phase = map_data.get('phase', self.map.phase)
            self.map.round = map_data.get('round', self.map.round)
            
            team_ct = map_data.get('team_ct', {})
            team_t = map_data.get('team_t', {})
            self.map.ct_score = team_ct.get('score', self.map.ct_score)
            self.map.t_score = team_t.get('score', self.map.t_score)
            
            if self.map.phase == 'gameover':
                self._emit_match_end_event()
                
        self.previous_state = data
        
    def _emit_event(self, event_type: str, data: Dict = None):
        event = GameEvent(event_type=event_type, data=data or {})
        self.events_history.append(event)
        
        if self.event_callback:
            try:
                self.event_callback(event)
            except Exception as e:
                print(f"[CS2 GSI] Ошибка callback: {e}")
                
    def _emit_kill_event(self, kill_count: int):
        self.kill_streak += kill_count
        
        event_data = {
            'kills_this_action': kill_count,
            'round_kills': self.player.round_kills,
            'total_kills': self.player.kills,
            'kill_streak': self.kill_streak,
            'headshot': self.player.round_killhs > 0,
            'weapon': self.player.weapon,
            'clutch': self.clutch_situation,
            'clutch_enemies': self.clutch_enemies
        }
        
        if self.player.round_kills >= 5:
            event_data['ace'] = True
            self._emit_event('ace', event_data)
        elif self.player.round_kills >= 4:
            self._emit_event('quadra_kill', event_data)
        elif self.player.round_kills >= 3:
            self._emit_event('triple_kill', event_data)
        elif self.player.round_kills >= 2:
            self._emit_event('double_kill', event_data)
        else:
            self._emit_event('kill', event_data)
            
    def _emit_death_event(self):
        self.kill_streak = 0
        
        event_data = {
            'total_deaths': self.player.deaths,
            'kd_ratio': self.player.kills / max(1, self.player.deaths),
            'round': self.map.round
        }
        self._emit_event('death', event_data)
        
    def _emit_damage_event(self, damage: int):
        event_data = {
            'damage': damage,
            'current_health': self.player.health,
            'armor': self.player.armor
        }
        
        if self.player.health <= 25:
            self._emit_event('low_health', event_data)
        elif damage >= 50:
            self._emit_event('heavy_damage', event_data)
            
    def _emit_round_start_event(self):
        self.kill_streak = 0
        self.round_start_kills = self.player.kills
        self.clutch_situation = False
        
        event_data = {
            'round': self.map.round,
            'ct_score': self.map.ct_score,
            't_score': self.map.t_score,
            'money': self.player.money,
            'equip_value': self.player.equip_value
        }
        
        if self.player.money < 2000:
            event_data['eco_round'] = True
            
        self._emit_event('round_start', event_data)
        
    def _emit_round_end_event(self):
        round_kills = self.player.kills - self.round_start_kills
        
        event_data = {
            'round': self.map.round,
            'win_team': self.round.win_team,
            'player_team': self.player.team,
            'won': self.round.win_team.lower() == self.player.team.lower() if self.round.win_team else False,
            'round_kills': round_kills,
            'clutch_win': self.clutch_situation and round_kills > 0
        }
        
        if round_kills >= 3:
            event_data['mvp_candidate'] = True
            
        self._emit_event('round_end', event_data)
        
    def _emit_bomb_planted_event(self):
        event_data = {
            'round': self.map.round,
            'player_team': self.player.team
        }
        self._emit_event('bomb_planted', event_data)
        
    def _emit_bomb_defused_event(self):
        event_data = {
            'round': self.map.round,
            'player_team': self.player.team,
            'ninja_defuse': self.player.health <= 10
        }
        self._emit_event('bomb_defused', event_data)
        
    def _emit_bomb_exploded_event(self):
        event_data = {
            'round': self.map.round,
            'player_team': self.player.team
        }
        self._emit_event('bomb_exploded', event_data)
        
    def _emit_match_end_event(self):
        event_data = {
            'ct_score': self.map.ct_score,
            't_score': self.map.t_score,
            'player_team': self.player.team,
            'won': (self.player.team == 'CT' and self.map.ct_score > self.map.t_score) or
                   (self.player.team == 'T' and self.map.t_score > self.map.ct_score),
            'kills': self.player.kills,
            'deaths': self.player.deaths,
            'assists': self.player.assists,
            'mvps': self.player.mvps,
            'map': self.map.name
        }
        self._emit_event('match_end', event_data)
        
    def start(self):
        if self.is_running:
            return
            
        self.is_running = True
        self.server_thread = threading.Thread(
            target=lambda: self.app.run(host='0.0.0.0', port=self.port, debug=False, use_reloader=False),
            daemon=True
        )
        self.server_thread.start()
        print(f"[CS2 GSI] Сервер запущен на порту {self.port}")
        
    def stop(self):
        self.is_running = False
        
    def get_player_stats(self) -> Dict:
        return {
            'name': self.player.name,
            'team': self.player.team,
            'health': self.player.health,
            'armor': self.player.armor,
            'money': self.player.money,
            'kills': self.player.kills,
            'deaths': self.player.deaths,
            'assists': self.player.assists,
            'kd_ratio': round(self.player.kills / max(1, self.player.deaths), 2),
            'mvps': self.player.mvps,
            'score': self.player.score
        }
        
    def get_match_info(self) -> Dict:
        return {
            'map': self.map.name,
            'mode': self.map.mode,
            'round': self.map.round,
            'ct_score': self.map.ct_score,
            't_score': self.map.t_score,
            'phase': self.map.phase
        }
        
    def generate_config_file(self) -> str:
        config = f'''"Iris Stream Assistant"
{{
    "uri" "http://localhost:{self.port}/"
    "timeout" "5.0"
    "buffer" "0.1"
    "throttle" "0.1"
    "heartbeat" "10.0"
    "auth"
    {{
        "token" "iris_stream_assistant"
    }}
    "data"
    {{
        "provider"            "1"
        "map"                 "1"
        "round"               "1"
        "player_id"           "1"
        "player_state"        "1"
        "player_weapons"      "1"
        "player_match_stats"  "1"
        "allplayers_id"       "1"
        "allplayers_state"    "1"
        "bomb"                "1"
        "phase_countdowns"    "1"
    }}
}}'''
        return config
        
    def save_config_file(self, path: str = "gamestate_integration_iris.cfg"):
        config = self.generate_config_file()
        with open(path, 'w') as f:
            f.write(config)
        print(f"[CS2 GSI] Конфиг сохранён: {path}")
        print(f"[CS2 GSI] Скопируйте его в: <Steam>/steamapps/common/Counter-Strike Global Offensive/game/csgo/cfg/")
        return path
