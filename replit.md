# Ирис - AI Stream Companion

## Описание
Ирис — это продвинутый AI-ассистент и со-ведущая для стримов. Она умеет:
- Реагировать на события в CS2 (убийства, смерти, clutch, ace, бомба)
- Читать чат и отвечать зрителям через StreamElements
- Благодарить за донаты и подписки
- Управлять громкостью приложений голосом
- Вести живой разговор со стримером
- Отслеживать достижения и статистику стрима

## Архитектура

```
src/
├── tts_engine.py         # OpenAI TTS для естественного голоса
├── voice_recognition.py  # Whisper API для распознавания голоса
├── cs2_gsi.py           # CS2 Game State Integration сервер
├── streamelements_client.py  # StreamElements WebSocket клиент
├── iris_brain.py        # GPT-4o для генерации ответов
├── windows_audio.py     # Управление громкостью приложений
├── achievements.py      # Система достижений и статистики
└── __init__.py

main.py                  # Главный файл запуска
```

## Настройка

### Необходимые секреты:
- `OPENAI_API_KEY` - ключ OpenAI API
- `STREAMELEMENTS_JWT_TOKEN` - JWT токен StreamElements (опционально)

### CS2 Game State Integration:
1. При запуске создаётся файл `gamestate_integration_iris.cfg`
2. Скопируйте его в `<Steam>/steamapps/common/Counter-Strike Global Offensive/game/csgo/cfg/`
3. Перезапустите CS2

## Функции

### Голосовое управление
- Скажите "Ирис" для активации
- Команды: "сделай музыку тише", "выключи дискорд", "громкость на 50%"

### CS2 интеграция
- Комментарии при убийствах, смертях, clutch ситуациях
- Реакции на бомбу, раунды, MVP
- Адаптивный юмор и эмоции

### StreamElements
- Чтение чата и ответы зрителям
- Благодарности за донаты с упоминанием суммы
- Приветствие новых подписчиков и рейдов

### Достижения
- 20+ достижений для отслеживания
- Автоматические поздравления
- Сохранение статистики

## Запуск
```bash
python main.py
```

## Технологии
- Python 3.11
- Flask (HTTP сервер для CS2 GSI)
- OpenAI API (GPT-4o, Whisper, TTS)
- WebSocket (StreamElements)
- pygame (воспроизведение аудио)
