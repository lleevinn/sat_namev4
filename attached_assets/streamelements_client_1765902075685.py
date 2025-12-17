import json
import websocket

# Вставьте ваш скопированный токен сюда
YOUR_JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJjaXRhZGVsIiwiZXhwIjoxNzgxNDUzNDYwLCJqdGkiOiJjYzM3ZjUwNS1lNGRkLTQxZjktOGIwZS1lNTNhZjUzM2M0ODIiLCJjaGFubmVsIjoiNjk0MTg0OTNjMjdmNzk4NGQ1Y2UwNmNkIiwicm9sZSI6Im93bmVyIiwiYXV0aFRva2VuIjoiMVdQckRUYUZUN21mc3RHSlNfZFpxV3NtNmlicFhYeGdDbmdjcThpeHlCbG9HTXpVIiwidXNlciI6IjY5NDE4NDkzYzI3Zjc5ODRkNWNlMDZjYyIsInVzZXJfaWQiOiIwYjhiZTJhZS1kNjIyLTRlNGEtODdmMy01NjJhYTcxMGM5YWYiLCJ1c2VyX3JvbGUiOiJjcmVhdG9yIiwicHJvdmlkZXIiOiJ0d2l0Y2giLCJwcm92aWRlcl9pZCI6IjE4NzU3MjUyNyIsImNoYW5uZWxfaWQiOiJlMjU4YzczZS04ZTgxLTQyNzktOGNjMS0wZWI2OTE2ZmIyMDMiLCJjcmVhdG9yX2lkIjoiNGQ4Zjk5YzktMGE3OC00YjlkLWJlNWEtZjVmNDY2ZGMyZjk4In0.UDj-xNNlOjOplW8gliL0-cb9S8_rnuCZaQCpLUvMq1o"

def on_message(ws, message):
    """Обрабатываем входящие сообщения от StreamElements."""
    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        # Иногда приходят служебные сообщения, их можно пропустить
        return

    # StreamElements отправляет события в поле 'type'
    event_type = data.get('type')
    listener = data.get('listener')

    # Событие чата
    if listener == 'chat-message':
        event_data = data.get('data', {})
        username = event_data.get('displayName', 'Аноним')
        user_message = event_data.get('message', '')
        print(f'[ЧАТ] {username}: {user_message}')
        # Тут можно передать сообщение в ваш ассистент для анализа

    # Событие доната (тип 'tip')
    elif event_type == 'tip':
        event_data = data.get('data', {})
        donor = event_data.get('username', 'Аноним')
        amount = event_data.get('amount', 0)
        currency = event_data.get('currency', 'USD')
        print(f'[ДОНАТ] {donor} - {amount} {currency}')
        # Передаем событие для озвучки ассистентом

    # Событие новой подписки (тип 'subscriber')
    elif event_type == 'subscriber':
        event_data = data.get('data', {})
        subscriber = event_data.get('username', 'Новый подписчик')
        print(f'[ПОДПИСКА] {subscriber}')
        # Передаем событие для озвучки

def on_error(ws, error):
    print(f"Ошибка WebSocket: {error}")

def on_close(ws, close_status_code, close_msg):
    print("Соединение с StreamElements закрыто")

def on_open(ws):
    print("Успешно подключились к StreamElements WebSocket!")
    # После открытия соединения нужно аутентифицироваться
    auth_message = {
        "method": "jwt",
        "token": YOUR_JWT_TOKEN
    }
    ws.send(json.dumps(auth_message))

if __name__ == "__main__":
    ws_url = "wss://realtime.streamelements.com/socket.io/?EIO=4&transport=websocket"
    ws = websocket.WebSocketApp(ws_url,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever()