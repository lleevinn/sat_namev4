import pyttsx3

engine = pyttsx3.init()
voices = engine.getProperty('voices')

print(f"📢 Доступно {len(voices)} голосов:\n")

female_voices = []
for i, voice in enumerate(voices):
    voice_name = voice.name.lower()
    is_female = any(keyword in voice_name for keyword in 
                   ['female', 'женск', 'woman', 'дама', 'девушка', 'irina', 'anna', 'мария', 'natalia'])
    
    status = "👩 ЖЕНСКИЙ" if is_female else "👨 МУЖСКОЙ"
    
    print(f"{i+1}. {status}: {voice.name}")
    print(f"   ID: {voice.id}")
    
    if is_female:
        female_voices.append(voice.id)
    
    print()

if female_voices:
    print(f"\n✅ Найдено {len(female_voices)} женских голосов!")
    print(f"Рекомендую использовать: {female_voices[0]}")
else:
    print("\n⚠️ Женских голосов не найдено, используем первый доступный")
    print(f"Первый голос: {voices[0].id}")