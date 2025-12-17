"""
IRIS Visual Interface - IO-style pulsating orb
Визуальный интерфейс Ирис с эффектом расширения/сужения при разговоре
"""
import pygame
import math
import threading
import time
import os
import numpy as np
from typing import Optional, Callable

class IrisVisual:
    """
    Визуальный интерфейс Ирис в стиле IO из Dota 2
    Пульсирующий шар, расширяющийся при разговоре
    """
    
    def __init__(self, width: int = 400, height: int = 400):
        self.width = width
        self.height = height
        self.center_x = width // 2
        self.center_y = height // 2
        
        self.base_radius = 80
        self.current_radius = self.base_radius
        self.target_radius = self.base_radius
        self.max_expand = 40
        
        self.is_speaking = False
        self.speech_intensity = 0.0
        self.pulse_phase = 0.0
        self.glow_phase = 0.0
        
        self.running = False
        self.initialized = False
        
        self.core_color = (100, 180, 255)
        self.glow_color = (50, 150, 255)
        self.particle_color = (150, 200, 255)
        
        self.particles = []
        self.energy_rings = []
        
        self.startup_sound_path = None
        self.startup_complete = False
        self.startup_animation_progress = 0.0
        
        self.screen = None
        self.clock = None
        
    def _init_pygame(self):
        """Инициализация pygame display"""
        if self.initialized:
            return True
            
        try:
            pygame.init()
            
            os.environ['SDL_VIDEO_WINDOW_POS'] = '100,100'
            
            self.screen = pygame.display.set_mode((self.width, self.height))
            pygame.display.set_caption("🌸 IRIS - AI Companion")
            
            self.clock = pygame.time.Clock()
            self.initialized = True
            
            for _ in range(20):
                self.particles.append(self._create_particle())
                
            return True
            
        except Exception as e:
            print(f"[VISUAL] Ошибка инициализации pygame display: {e}")
            return False
    
    def _create_particle(self) -> dict:
        """Создать частицу для эффекта энергии"""
        angle = np.random.uniform(0, 2 * math.pi)
        distance = np.random.uniform(self.base_radius * 0.5, self.base_radius * 2)
        speed = np.random.uniform(0.5, 2.0)
        size = np.random.uniform(2, 6)
        
        return {
            'angle': angle,
            'distance': distance,
            'speed': speed,
            'size': size,
            'alpha': np.random.uniform(100, 255),
            'orbit_speed': np.random.uniform(-0.02, 0.02)
        }
    
    def _draw_glow(self, surface, center, radius, color, intensity=1.0):
        """Рисовать свечение"""
        for i in range(10, 0, -1):
            glow_radius = int(radius + i * 8)
            alpha = int(30 * intensity * (i / 10))
            glow_surface = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
            glow_color_alpha = (*color, alpha)
            pygame.draw.circle(glow_surface, glow_color_alpha, (glow_radius, glow_radius), glow_radius)
            surface.blit(glow_surface, (center[0] - glow_radius, center[1] - glow_radius))
    
    def _draw_core(self, surface, center, radius):
        """Рисовать ядро с градиентом"""
        for i in range(int(radius), 0, -2):
            ratio = i / radius
            r = int(self.core_color[0] * ratio + 255 * (1 - ratio))
            g = int(self.core_color[1] * ratio + 255 * (1 - ratio))
            b = int(self.core_color[2] * ratio + 255 * (1 - ratio))
            pygame.draw.circle(surface, (r, g, b), center, i)
    
    def _draw_energy_rings(self, surface, center, base_radius):
        """Рисовать энергетические кольца"""
        ring_count = 3
        for i in range(ring_count):
            offset = (self.glow_phase + i * 0.3) % 1.0
            ring_radius = int(base_radius * (1.2 + offset * 0.8))
            alpha = int(150 * (1 - offset))
            
            ring_surface = pygame.Surface((ring_radius * 2 + 10, ring_radius * 2 + 10), pygame.SRCALPHA)
            ring_color = (*self.glow_color, alpha)
            pygame.draw.circle(ring_surface, ring_color, (ring_radius + 5, ring_radius + 5), ring_radius, 2)
            surface.blit(ring_surface, (center[0] - ring_radius - 5, center[1] - ring_radius - 5))
    
    def _draw_particles(self, surface, center, speaking_intensity):
        """Рисовать орбитальные частицы"""
        for p in self.particles:
            p['angle'] += p['orbit_speed'] * (1 + speaking_intensity * 2)
            
            if self.is_speaking:
                p['distance'] += math.sin(self.pulse_phase * 3 + p['angle']) * 2
            
            x = center[0] + math.cos(p['angle']) * p['distance']
            y = center[1] + math.sin(p['angle']) * p['distance']
            
            size = int(p['size'] * (1 + speaking_intensity * 0.5))
            alpha = int(p['alpha'] * (0.5 + speaking_intensity * 0.5))
            
            particle_surface = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            particle_color = (*self.particle_color, alpha)
            pygame.draw.circle(particle_surface, particle_color, (size, size), size)
            surface.blit(particle_surface, (int(x) - size, int(y) - size))
    
    def _draw_speech_waves(self, surface, center, radius, intensity):
        """Рисовать волны речи когда Ирис говорит"""
        if intensity < 0.1:
            return
            
        wave_count = 5
        for i in range(wave_count):
            wave_offset = (self.pulse_phase * 2 + i * 0.2) % 1.0
            wave_radius = int(radius + wave_offset * 60 * intensity)
            alpha = int(100 * intensity * (1 - wave_offset))
            
            wave_surface = pygame.Surface((wave_radius * 2 + 10, wave_radius * 2 + 10), pygame.SRCALPHA)
            wave_color = (200, 230, 255, alpha)
            pygame.draw.circle(wave_surface, wave_color, (wave_radius + 5, wave_radius + 5), wave_radius, 3)
            surface.blit(wave_surface, (center[0] - wave_radius - 5, center[1] - wave_radius - 5))
    
    def _update_animation(self, dt):
        """Обновить анимацию"""
        self.pulse_phase += dt * 2
        self.glow_phase += dt * 0.5
        
        if self.glow_phase > 1.0:
            self.glow_phase -= 1.0
        
        if self.is_speaking:
            self.target_radius = self.base_radius + self.max_expand * self.speech_intensity
            
            wave_expansion = math.sin(self.pulse_phase * 8) * self.max_expand * 0.3 * self.speech_intensity
            self.target_radius += wave_expansion
        else:
            idle_pulse = math.sin(self.pulse_phase) * 5
            self.target_radius = self.base_radius + idle_pulse
        
        self.current_radius += (self.target_radius - self.current_radius) * 0.15
    
    def _render_frame(self):
        """Отрисовка одного кадра"""
        if not self.screen:
            return
            
        self.screen.fill((10, 15, 25))
        
        center = (self.center_x, self.center_y)
        
        glow_intensity = 0.6 + self.speech_intensity * 0.4
        self._draw_glow(self.screen, center, self.current_radius, self.glow_color, glow_intensity)
        
        self._draw_energy_rings(self.screen, center, self.current_radius)
        
        self._draw_particles(self.screen, center, self.speech_intensity)
        
        if self.is_speaking:
            self._draw_speech_waves(self.screen, center, self.current_radius, self.speech_intensity)
        
        self._draw_core(self.screen, center, int(self.current_radius))
        
        inner_radius = int(self.current_radius * 0.3)
        pygame.draw.circle(self.screen, (255, 255, 255), center, inner_radius)
        
        pygame.display.flip()
    
    def set_speaking(self, speaking: bool, intensity: float = 1.0):
        """Установить состояние разговора"""
        self.is_speaking = speaking
        self.speech_intensity = max(0.0, min(1.0, intensity))
    
    def pulse(self, intensity: float = 0.8, duration: float = 0.3):
        """Создать пульсацию"""
        self.speech_intensity = intensity
        threading.Thread(target=self._pulse_fade, args=(duration,), daemon=True).start()
    
    def _pulse_fade(self, duration: float):
        """Плавное затухание пульса"""
        steps = int(duration * 60)
        for i in range(steps):
            self.speech_intensity = self.speech_intensity * 0.95
            time.sleep(1/60)
        self.speech_intensity = 0
    
    def generate_startup_sound(self, sound_type: str = 'power_up') -> Optional[str]:
        """Генерация звуков запуска в стиле Iron Man"""
        try:
            sample_rate = 44100
            
            if sound_type == 'power_up':
                duration = 2.0
                t = np.linspace(0, duration, int(sample_rate * duration))
                power_up = np.sin(2 * np.pi * 80 * t) * np.exp(-t * 0.3)
                power_up += np.sin(2 * np.pi * 160 * t) * np.exp(-t * 0.5) * 0.5
                sweep_freq = 100 + 400 * (t / duration)
                sweep = np.sin(2 * np.pi * sweep_freq * t) * 0.3
                sweep *= np.exp(-np.abs(t - 1.0) * 2)
                harmonics = np.sin(2 * np.pi * 440 * t) * 0.2
                harmonics += np.sin(2 * np.pi * 880 * t) * 0.1
                harmonics *= np.exp(-t * 0.8)
                hum = np.sin(2 * np.pi * 60 * t) * 0.1 * (1 - np.exp(-t * 2))
                sound = power_up + sweep + harmonics + hum
                
            elif sound_type == 'scan':
                duration = 1.0
                t = np.linspace(0, duration, int(sample_rate * duration))
                sweep_freq = 200 + 1000 * np.sin(t / duration * np.pi)
                sound = np.sin(2 * np.pi * sweep_freq * t) * 0.4
                sound += np.sin(2 * np.pi * 880 * t) * 0.1 * np.sin(t * 30)
                sound *= (1 - np.exp(-t * 10)) * np.exp(-(t - duration) * 3)
                
            elif sound_type == 'confirm':
                duration = 0.5
                t = np.linspace(0, duration, int(sample_rate * duration))
                sound = np.sin(2 * np.pi * 880 * t) * 0.3
                sound += np.sin(2 * np.pi * 1320 * t) * 0.2
                sound *= np.exp(-t * 4)
                
            elif sound_type == 'loading':
                duration = 1.5
                t = np.linspace(0, duration, int(sample_rate * duration))
                base_freq = 150 + 100 * (t / duration)
                sound = np.sin(2 * np.pi * base_freq * t) * 0.3
                pulse = (np.sin(t * 15) > 0).astype(float) * 0.3
                sound += pulse * np.sin(2 * np.pi * 600 * t) * 0.2
                hum = np.sin(2 * np.pi * 60 * t) * 0.15
                sound += hum
                
            elif sound_type == 'connect':
                duration = 0.8
                t = np.linspace(0, duration, int(sample_rate * duration))
                beep1 = np.sin(2 * np.pi * 1000 * t) * (t < 0.15).astype(float)
                beep2 = np.sin(2 * np.pi * 1200 * t) * ((t > 0.2) & (t < 0.35)).astype(float)
                beep3 = np.sin(2 * np.pi * 1500 * t) * ((t > 0.4) & (t < 0.55)).astype(float)
                sound = (beep1 + beep2 + beep3) * 0.4
                sound *= np.exp(-np.abs(t - 0.4) * 2)
                
            elif sound_type == 'ready':
                duration = 1.2
                t = np.linspace(0, duration, int(sample_rate * duration))
                chord = np.sin(2 * np.pi * 523 * t) * 0.3
                chord += np.sin(2 * np.pi * 659 * t) * 0.25
                chord += np.sin(2 * np.pi * 784 * t) * 0.2
                chord += np.sin(2 * np.pi * 1047 * t) * 0.15
                sound = chord * (1 - np.exp(-t * 5)) * np.exp(-(t - 0.3) * 1.5)
                shimmer = np.sin(2 * np.pi * 2000 * t) * 0.05 * np.sin(t * 20)
                sound += shimmer
            else:
                return None
            
            envelope = np.ones_like(t)
            attack = int(0.05 * sample_rate)
            release = int(0.1 * sample_rate)
            if len(envelope) > attack:
                envelope[:attack] = np.linspace(0, 1, attack)
            if len(envelope) > release:
                envelope[-release:] = np.linspace(1, 0, release)
            sound *= envelope
            
            if np.max(np.abs(sound)) > 0:
                sound = sound / np.max(np.abs(sound)) * 0.7
            
            sound_int = np.int16(sound * 32767)
            
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False, prefix=f'iris_{sound_type}_')
            
            import wave
            with wave.open(temp_file.name, 'w') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(sound_int.tobytes())
            
            return temp_file.name
            
        except Exception as e:
            print(f"[VISUAL] Ошибка генерации звука {sound_type}: {e}")
            return None
    
    def play_sound(self, sound_type: str, volume: float = 0.7):
        """Воспроизвести звуковой эффект"""
        sound_path = self.generate_startup_sound(sound_type)
        if sound_path and pygame.mixer.get_init():
            try:
                sound = pygame.mixer.Sound(sound_path)
                sound.set_volume(volume)
                sound.play()
                return sound_path
            except Exception as e:
                print(f"[VISUAL] Ошибка воспроизведения {sound_type}: {e}")
        return None
    
    def play_startup_sequence(self, callback: Optional[Callable] = None, phase_callback: Optional[Callable] = None):
        """Воспроизвести полную анимацию запуска с фазами"""
        def startup_thread():
            temp_files = []
            
            sound_path = self.generate_startup_sound('power_up')
            if sound_path:
                temp_files.append(sound_path)
                if pygame.mixer.get_init():
                    try:
                        startup_sound = pygame.mixer.Sound(sound_path)
                        startup_sound.set_volume(0.7)
                        startup_sound.play()
                    except:
                        pass
            
            start_time = time.time()
            duration = 2.0
            
            while time.time() - start_time < duration:
                progress = (time.time() - start_time) / duration
                self.startup_animation_progress = progress
                if progress < 0.3:
                    self.speech_intensity = progress / 0.3 * 0.6
                elif progress < 0.7:
                    self.speech_intensity = 0.6 + math.sin((progress - 0.3) / 0.4 * math.pi * 4) * 0.3
                else:
                    self.speech_intensity = max(0.2, (1 - progress) / 0.3 * 0.6)
                time.sleep(0.016)
            
            if phase_callback:
                phase_callback('power_up_complete')
            
            time.sleep(0.5)
            
            self.startup_complete = True
            self.speech_intensity = 0
            
            for f in temp_files:
                try:
                    os.unlink(f)
                except:
                    pass
            
            if callback:
                callback()
        
        threading.Thread(target=startup_thread, daemon=True).start()
    
    def animate_phase(self, phase_name: str, duration: float = 1.0):
        """Анимировать определённую фазу запуска"""
        def phase_thread():
            sound_map = {
                'scan': 'scan',
                'check': 'scan', 
                'connect': 'connect',
                'loading': 'loading',
                'confirm': 'confirm',
                'ready': 'ready'
            }
            
            sound_type = sound_map.get(phase_name, 'confirm')
            sound_path = self.play_sound(sound_type, 0.5)
            
            start_time = time.time()
            while time.time() - start_time < duration:
                progress = (time.time() - start_time) / duration
                wave = math.sin(progress * math.pi * 6) * 0.3
                self.speech_intensity = 0.4 + wave
                time.sleep(0.016)
            
            self.speech_intensity = 0.2
            
            if sound_path:
                try:
                    time.sleep(0.3)
                    os.unlink(sound_path)
                except:
                    pass
        
        threading.Thread(target=phase_thread, daemon=True).start()
    
    def run(self, startup_callback: Optional[Callable] = None):
        """Запустить визуальный интерфейс"""
        if not self._init_pygame():
            print("[VISUAL] Не удалось запустить визуальный интерфейс")
            return
        
        self.running = True
        
        self.play_startup_sequence(startup_callback)
        
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                        break
                    elif event.key == pygame.K_SPACE:
                        self.is_speaking = not self.is_speaking
                        self.speech_intensity = 0.8 if self.is_speaking else 0
            
            self._update_animation(dt)
            self._render_frame()
        
        pygame.quit()
    
    def run_async(self, startup_callback: Optional[Callable] = None):
        """Запустить визуальный интерфейс в отдельном потоке"""
        thread = threading.Thread(target=self.run, args=(startup_callback,), daemon=True)
        thread.start()
        return thread
    
    def stop(self):
        """Остановить визуальный интерфейс"""
        self.running = False


if __name__ == "__main__":
    print("=== Тест визуального интерфейса IRIS ===")
    
    visual = IrisVisual()
    
    def on_startup_complete():
        print("[VISUAL] Анимация запуска завершена!")
    
    visual.run(on_startup_complete)
