<<<<<<< HEAD
"""
Iris Utils - Вспомогательные утилиты
"""

def synthesize_and_play(text: str, lang: str = 'ru', cleanup: bool = True) -> bool:
    """
    Быстрая функция для синтеза и воспроизведения
    Совместимость со старым API
    """
    from src.tts_engine import TTSEngine
    import time
    
    engine = TTSEngine(voice='ru_female_soft')
    engine.speak(text, emotion='neutral')
    
    while engine.is_busy():
        time.sleep(0.1)
    
    engine.stop()
    return True

__all__ = ['synthesize_and_play']
=======
# Package initializer
>>>>>>> 6d0ea0cd1396a0d7b9b7fabfc564c9750f26d5aa
