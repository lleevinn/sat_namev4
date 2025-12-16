import os
import sys
import subprocess
from typing import Optional, List, Dict

class WindowsAudioController:
    def __init__(self):
        self.is_windows = sys.platform == 'win32'
        self.pycaw_available = False
        
        if self.is_windows:
            try:
                from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import IAudioEndpointVolume
                self.pycaw_available = True
            except ImportError:
                print("[AUDIO] pycaw не установлен - управление громкостью недоступно на Windows")
                print("[AUDIO] Установите: pip install pycaw")
                
    def get_running_apps(self) -> List[Dict]:
        if not self.is_windows or not self.pycaw_available:
            return self._get_mock_apps()
            
        try:
            from pycaw.pycaw import AudioUtilities
            
            sessions = AudioUtilities.GetAllSessions()
            apps = []
            
            for session in sessions:
                if session.Process:
                    apps.append({
                        'name': session.Process.name(),
                        'pid': session.Process.pid,
                        'session': session
                    })
                    
            return apps
            
        except Exception as e:
            print(f"[AUDIO] Ошибка получения приложений: {e}")
            return []
            
    def _get_mock_apps(self) -> List[Dict]:
        return [
            {'name': 'Yandex Music (mock)', 'pid': 0, 'volume': 1.0},
            {'name': 'Spotify (mock)', 'pid': 0, 'volume': 1.0},
            {'name': 'Discord (mock)', 'pid': 0, 'volume': 1.0},
            {'name': 'Chrome (mock)', 'pid': 0, 'volume': 1.0}
        ]
        
    def set_app_volume(self, app_name: str, volume: float) -> bool:
        volume = max(0.0, min(1.0, volume))
        
        if not self.is_windows or not self.pycaw_available:
            print(f"[AUDIO] (Mock) Установлена громкость {app_name}: {int(volume * 100)}%")
            return True
            
        try:
            from pycaw.pycaw import AudioUtilities
            
            sessions = AudioUtilities.GetAllSessions()
            
            for session in sessions:
                if session.Process and app_name.lower() in session.Process.name().lower():
                    volume_interface = session._ctl.QueryInterface(
                        __import__('pycaw.pycaw', fromlist=['ISimpleAudioVolume']).ISimpleAudioVolume
                    )
                    volume_interface.SetMasterVolume(volume, None)
                    print(f"[AUDIO] Громкость {session.Process.name()}: {int(volume * 100)}%")
                    return True
                    
            print(f"[AUDIO] Приложение '{app_name}' не найдено")
            return False
            
        except Exception as e:
            print(f"[AUDIO] Ошибка установки громкости: {e}")
            return False
            
    def get_app_volume(self, app_name: str) -> Optional[float]:
        if not self.is_windows or not self.pycaw_available:
            return 1.0
            
        try:
            from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
            
            sessions = AudioUtilities.GetAllSessions()
            
            for session in sessions:
                if session.Process and app_name.lower() in session.Process.name().lower():
                    volume_interface = session._ctl.QueryInterface(ISimpleAudioVolume)
                    return volume_interface.GetMasterVolume()
                    
            return None
            
        except Exception as e:
            print(f"[AUDIO] Ошибка получения громкости: {e}")
            return None
            
    def mute_app(self, app_name: str) -> bool:
        return self.set_app_volume(app_name, 0.0)
        
    def unmute_app(self, app_name: str, volume: float = 1.0) -> bool:
        return self.set_app_volume(app_name, volume)
        
    def set_master_volume(self, volume: float) -> bool:
        volume = max(0.0, min(1.0, volume))
        
        if not self.is_windows:
            print(f"[AUDIO] (Mock) Системная громкость: {int(volume * 100)}%")
            return True
            
        if not self.pycaw_available:
            try:
                nircmd_volume = int(volume * 65535)
                subprocess.run(['nircmd', 'setsysvolume', str(nircmd_volume)], check=True)
                return True
            except:
                pass
                
        try:
            from pycaw.pycaw import AudioUtilities
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import IAudioEndpointVolume
            
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume_interface = interface.QueryInterface(IAudioEndpointVolume)
            volume_interface.SetMasterVolumeLevelScalar(volume, None)
            
            print(f"[AUDIO] Системная громкость: {int(volume * 100)}%")
            return True
            
        except Exception as e:
            print(f"[AUDIO] Ошибка установки системной громкости: {e}")
            return False
            
    def get_master_volume(self) -> Optional[float]:
        if not self.is_windows or not self.pycaw_available:
            return 1.0
            
        try:
            from pycaw.pycaw import AudioUtilities
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import IAudioEndpointVolume
            
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume_interface = interface.QueryInterface(IAudioEndpointVolume)
            
            return volume_interface.GetMasterVolumeLevelScalar()
            
        except Exception as e:
            print(f"[AUDIO] Ошибка получения системной громкости: {e}")
            return None

    def parse_volume_command(self, command: str) -> Dict:
        command = command.lower()
        
        result = {
            'action': None,
            'app': None,
            'volume': None
        }
        
        app_keywords = {
            'музык': ['yandex', 'spotify', 'музык'],
            'яндекс': ['yandex'],
            'spotify': ['spotify'],
            'дискорд': ['discord'],
            'discord': ['discord'],
            'браузер': ['chrome', 'firefox', 'browser', 'edge'],
            'хром': ['chrome'],
            'chrome': ['chrome']
        }
        
        for keyword, apps in app_keywords.items():
            if keyword in command:
                result['app'] = apps[0]
                break
                
        if 'тише' in command or 'убав' in command or 'понизь' in command:
            result['action'] = 'decrease'
            result['volume'] = 0.3
        elif 'громче' in command or 'прибав' in command or 'повысь' in command:
            result['action'] = 'increase'
            result['volume'] = 0.7
        elif 'выключ' in command or 'замут' in command or 'mute' in command:
            result['action'] = 'mute'
            result['volume'] = 0.0
        elif 'включ' in command or 'размут' in command or 'unmute' in command:
            result['action'] = 'unmute'
            result['volume'] = 1.0
        elif any(word in command for word in ['50%', 'половин', 'средн']):
            result['action'] = 'set'
            result['volume'] = 0.5
        elif any(word in command for word in ['100%', 'максим', 'полн']):
            result['action'] = 'set'
            result['volume'] = 1.0
        elif any(word in command for word in ['25%', 'четверть']):
            result['action'] = 'set'
            result['volume'] = 0.25
            
        return result
        
    def execute_voice_command(self, command: str) -> str:
        parsed = self.parse_volume_command(command)
        
        if not parsed['action']:
            return "Не понял команду. Скажи например: 'сделай музыку тише' или 'выключи дискорд'"
            
        if parsed['app']:
            if parsed['action'] == 'mute':
                success = self.mute_app(parsed['app'])
                return f"{'Выключила' if success else 'Не смогла выключить'} {parsed['app']}"
            elif parsed['action'] == 'unmute':
                success = self.unmute_app(parsed['app'])
                return f"{'Включила' if success else 'Не смогла включить'} {parsed['app']}"
            else:
                success = self.set_app_volume(parsed['app'], parsed['volume'])
                percent = int(parsed['volume'] * 100)
                return f"{'Установила' if success else 'Не смогла установить'} громкость {parsed['app']} на {percent}%"
        else:
            if parsed['action'] == 'mute':
                success = self.set_master_volume(0.0)
                return "Выключила звук" if success else "Не смогла выключить звук"
            elif parsed['action'] == 'unmute':
                success = self.set_master_volume(1.0)
                return "Включила звук" if success else "Не смогла включить звук"
            else:
                success = self.set_master_volume(parsed['volume'])
                percent = int(parsed['volume'] * 100)
                return f"{'Установила' if success else 'Не смогла установить'} системную громкость на {percent}%"
