import os
import json
import time
import threading
import websocket
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, List, Any
from collections import deque

@dataclass
class StreamEvent:
    event_type: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

class StreamElementsClient:
    WS_URL = "wss://realtime.streamelements.com/socket.io/?EIO=4&transport=websocket"
    
    def __init__(self, 
                 jwt_token: Optional[str] = None,
                 event_callback: Optional[Callable[[StreamEvent], None]] = None):
        
        self.jwt_token = jwt_token or os.getenv('STREAMELEMENTS_JWT_TOKEN', '')
        self.event_callback = event_callback
        
        self.ws = None
        self.is_connected = False
        self.reconnect_delay = 5
        self.max_reconnect_delay = 60
        
        self.events_history: deque = deque(maxlen=500)
        self.chat_history: deque = deque(maxlen=100)
        
        self.viewer_stats = {
            'total_tips': 0,
            'total_subs': 0,
            'total_followers': 0,
            'top_donator': None,
            'recent_events': []
        }
        
        self.ws_thread = None
        self.heartbeat_thread = None
        
    def connect(self):
        """Подключение к StreamElements WebSocket"""
        try:
            print("[StreamElements] Подключение...")
            
            if not self.jwt_token or self.jwt_token == "your_jwt_token_here":
                print("[StreamElements] ⚠️ JWT токен не настроен, пропускаем подключение")
                return
            
            self.ws = websocket.WebSocketApp(
                self.WS_URL,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            self.ws_thread = threading.Thread(target=self._run_forever, daemon=True)
            self.ws_thread.start()
            
            return True
            
        except Exception as e:
            print(f"[StreamElements] Ошибка подключения: {e}")
            return False
        
    def _run_forever(self):
        """Бесконечный цикл подключения"""
        while True:
            try:
                self.ws.run_forever()
            except Exception as e:
                print(f"[StreamElements] Ошибка соединения: {e}")
                
            if not self.is_connected:
                break
                
            print(f"[StreamElements] Переподключение через {self.reconnect_delay} сек...")
            time.sleep(self.reconnect_delay)
            self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
            
    def _on_open(self, ws):
        """Обработчик открытия соединения"""
        print("[StreamElements] WebSocket соединение открыто")
        self._authenticate()
        self._start_heartbeat()
        
    def _authenticate(self):
        """Аутентификация с JWT токеном"""
        auth_message = json.dumps({
            "method": "jwt",
            "token": self.jwt_token
        })
        self.ws.send(f"42{auth_message}")
        print("[StreamElements] Отправлен запрос авторизации")
        
    def _start_heartbeat(self):
        """Запуск heartbeat для поддержания соединения"""
        def heartbeat():
            while self.is_connected:
                try:
                    self.ws.send("2")
                    time.sleep(25)
                except Exception:
                    break
                    
        self.heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        self.heartbeat_thread.start()
        
    def _on_message(self, ws, message: str):
        """Обработчик входящих сообщений"""
        try:
            if message.startswith('0'):
                self.is_connected = True
                self.reconnect_delay = 5
                print("[StreamElements] Подключено к серверу")
                return
                
            if message.startswith('40'):
                print("[StreamElements] Авторизация успешна!")
                return
                
            if message.startswith('42'):
                data_str = message[2:]
                try:
                    data = json.loads(data_str)
                    if isinstance(data, list) and len(data) >= 2:
                        event_type = data[0]
                        event_data = data[1] if len(data) > 1 else {}
                        self._handle_event(event_type, event_data)
                except json.JSONDecodeError:
                    print(f"[StreamElements] Ошибка декодирования JSON: {data_str}")
                return
                
            if message == '3':
                return  # Heartbeat response
                
        except Exception as e:
            print(f"[StreamElements] Ошибка обработки сообщения: {e}")
            
    def _handle_event(self, event_type: str, event_data: Dict):
        """Обработка события"""
        stream_event = StreamEvent(event_type=event_type, data=event_data)
        self.events_history.append(stream_event)
        
        if event_type == 'event' or event_type == 'event:test':
            self._process_stream_event(event_data)
        elif event_type == 'message':
            self._process_chat_message(event_data)
        else:
            print(f"[StreamElements] Неизвестный тип события: {event_type}")
            
    def _process_stream_event(self, data: Dict):
        """Обработка stream события"""
        listener = data.get('listener', '')
        event_data = data.get('event', data)
        
        event_type = data.get('type', '')
        
        if 'tip' in listener or 'tip' in event_type:
            self._handle_tip(event_data)
        elif 'subscriber' in listener or 'subscriber' in event_type:
            self._handle_subscriber(event_data)
        elif 'follower' in listener or 'follower' in event_type:
            self._handle_follower(event_data)
        elif 'raid' in listener or 'raid' in event_type:
            self._handle_raid(event_data)
        elif 'cheer' in listener or 'cheer' in event_type:
            self._handle_cheer(event_data)
        elif 'host' in listener or 'host' in event_type:
            self._handle_host(event_data)
        else:
            print(f"[StreamElements] Неизвестный listener: {listener}")
            
    def _process_chat_message(self, data: Dict):
        """Обработка сообщения чата"""
        username = data.get('displayName', data.get('username', 'Аноним'))
        message = data.get('message', data.get('text', ''))
        
        chat_event = {
            'username': username,
            'message': message,
            'timestamp': time.time(),
            'badges': data.get('badges', []),
            'emotes': data.get('emotes', [])
        }
        
        self.chat_history.append(chat_event)
        
        stream_event = StreamEvent(
            event_type='chat_message',
            data=chat_event
        )
        
        if self.event_callback:
            self.event_callback(stream_event)
            
        print(f"[ЧАТ] {username}: {message}")
        
    def _handle_tip(self, data: Dict):
        """Обработка доната"""
        username = data.get('username', data.get('name', 'Аноним'))
        amount = float(data.get('amount', 0))
        currency = data.get('currency', 'USD')
        tip_message = data.get('message', '')
        
        self.viewer_stats['total_tips'] += amount
        
        if not self.viewer_stats['top_donator'] or amount > self.viewer_stats['top_donator'].get('amount', 0):
            self.viewer_stats['top_donator'] = {'username': username, 'amount': amount}
            
        stream_event = StreamEvent(
            event_type='donation',
            data={
                'username': username,
                'amount': amount,
                'currency': currency,
                'message': tip_message,
                'formatted': f"{amount} {currency}"
            }
        )
        
        self.viewer_stats['recent_events'].append(stream_event)
        if len(self.viewer_stats['recent_events']) > 20:
            self.viewer_stats['recent_events'].pop(0)
            
        if self.event_callback:
            self.event_callback(stream_event)
            
        print(f"[ДОНАТ] {username}: {amount} {currency} - {tip_message}")
        
    def _handle_subscriber(self, data: Dict):
        """Обработка подписки"""
        username = data.get('username', data.get('name', 'Аноним'))
        tier = data.get('tier', '1000')
        months = data.get('amount', data.get('months', 1))
        is_gift = data.get('gifted', False)
        gifter = data.get('sender', '')
        
        self.viewer_stats['total_subs'] += 1
        
        tier_name = {'1000': 'Tier 1', '2000': 'Tier 2', '3000': 'Tier 3'}.get(str(tier), 'Tier 1')
        
        stream_event = StreamEvent(
            event_type='subscription',
            data={
                'username': username,
                'tier': tier_name,
                'months': months,
                'is_gift': is_gift,
                'gifter': gifter,
                'message': data.get('message', '')
            }
        )
        
        if self.event_callback:
            self.event_callback(stream_event)
            
        if is_gift:
            print(f"[ПОДПИСКА] {gifter} подарил подписку {username} ({tier_name})")
        else:
            print(f"[ПОДПИСКА] {username} подписался! ({tier_name}, {months} мес.)")
            
    def _handle_follower(self, data: Dict):
        """Обработка фолловера"""
        username = data.get('username', data.get('name', 'Аноним'))
        
        self.viewer_stats['total_followers'] += 1
        
        stream_event = StreamEvent(
            event_type='follow',
            data={'username': username}
        )
        
        if self.event_callback:
            self.event_callback(stream_event)
            
        print(f"[ФОЛЛОУ] {username} подписался на канал!")
        
    def _handle_raid(self, data: Dict):
        """Обработка рейда"""
        username = data.get('username', data.get('name', 'Аноним'))
        viewers = data.get('amount', data.get('viewers', 0))
        
        stream_event = StreamEvent(
            event_type='raid',
            data={
                'username': username,
                'viewers': viewers
            }
        )
        
        if self.event_callback:
            self.event_callback(stream_event)
            
        print(f"[РЕЙД] {username} ворвался с {viewers} зрителями!")
        
    def _handle_cheer(self, data: Dict):
        """Обработка битов (cheer)"""
        username = data.get('username', data.get('name', 'Аноним'))
        amount = data.get('amount', 0)
        message = data.get('message', '')
        
        stream_event = StreamEvent(
            event_type='cheer',
            data={
                'username': username,
                'bits': amount,
                'message': message
            }
        )
        
        if self.event_callback:
            self.event_callback(stream_event)
            
        print(f"[БИТЫ] {username}: {amount} битов - {message}")
        
    def _handle_host(self, data: Dict):
        """Обработка хоста"""
        username = data.get('username', data.get('name', 'Аноним'))
        viewers = data.get('amount', data.get('viewers', 0))
        
        stream_event = StreamEvent(
            event_type='host',
            data={
                'username': username,
                'viewers': viewers
            }
        )
        
        if self.event_callback:
            self.event_callback(stream_event)
            
        print(f"[ХОСТ] {username} хостит канал с {viewers} зрителями!")
        
    def _on_error(self, ws, error):
        """Обработчик ошибок"""
        print(f"[StreamElements] Ошибка: {error}")
        
    def _on_close(self, ws, close_status_code, close_msg):
        """Обработчик закрытия соединения"""
        self.is_connected = False
        print(f"[StreamElements] Соединение закрыто: {close_status_code} - {close_msg}")
        
    def disconnect(self):
        """Отключение от StreamElements"""
        self.is_connected = False
        if self.ws:
            self.ws.close()
            
    def get_chat_history(self, limit: int = 50) -> List[Dict]:
        """Получение истории чата"""
        return list(self.chat_history)[-limit:]
        
    def get_recent_events(self, limit: int = 20) -> List[StreamEvent]:
        """Получение последних событий"""
        return list(self.events_history)[-limit:]
        
    def get_viewer_stats(self) -> Dict:
        """Получение статистики зрителей"""
        return self.viewer_stats.copy()