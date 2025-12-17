# fix_iris_brain.py
import os
import sys

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.iris_brain import IrisBrain
    print("✅ IrisBrain импортирован")
    
    # Проверяем Groq
    from groq import Groq
    
    api_key = os.getenv('GROQ_API_KEY', 'test')
    try:
        # Новая версия Groq
        client = Groq(api_key=api_key)
        print("✅ Groq клиент создан (новая версия)")
    except Exception as e:
        print(f"❌ Ошибка Groq: {e}")
        
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

print("\n📋 Установи правильную версию Groq:")
print("pip install groq==0.3.0")