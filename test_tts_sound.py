# test_tts_sound.py
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.tts_engine import TTSEngine
import time

print("🔊 Тест звука TTS...")

def test_callback(speaking, intensity):
    print(f"[VISUAL] Говорит: {speaking}, Интенсивность: {intensity}")

try:
    # Тест 1: Простой TTS
    print("Тест 1: Базовый TTS...")
    tts = TTSEngine(visual_callback=test_callback)
    tts.start()
    tts.speak("Привет! Тест звука один два три.", emotion='neutral')
    time.sleep(5)
    tts.stop()
    
    # Тест 2: Проверка аудиоустройств pygame
    print("\nТест 2: Проверка pygame...")
    import pygame
    pygame.mixer.init()
    print(f"PyAudio устройств: {pygame.mixer.get_num_channels()}")
    
    # Тест 3: Проверка Edge TTS
    print("\nТест 3: Проверка Edge TTS...")
    import edge_tts
    import asyncio
    
    async def test_edge_tts():
        voices = await edge_tts.VoicesManager.create()
        voice = voices.find(Gender="Female", Language="ru")
        print(f"Найден голос: {voice['Name'] if voice else 'Нет'}")
    
    asyncio.run(test_edge_tts())
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

print("\n✅ Тест завершен")