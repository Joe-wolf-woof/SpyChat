import asyncio
import json
import os
import random
import websockets

# 待機中のプレイヤーリスト
waiting_players = []

# アクティブな対戦ルームの管理
# 例: { "room_id": { "clients": [wsA, wsB], "theme": "...", "targetA": "...", "targetB": "...", ... } }
active_rooms = {}
room_counter = 0

THEME_LIST = [
    "プログラミング・IT技術",
    "学校・学生生活",
    "食べ物・グルメ",
    "アニメ・ゲーム",
    "ビジネス・オフィス",
    "日常のライフハック",
    "旅行・お出かけ",
    "動物・生き物",
    "スポーツ・筋トレ",
    "映画・ドラマ"
]

async def handler(websocket):
    global room_counter
    
    # プレイヤーを待機リストに追加
    waiting_players.append(websocket)
    
    # 接続時点では待機中であることを通知
    await websocket.send(json.dumps({
        "type": "WAITING_LOBBY",
        "message": "対戦相手を待っています..."
    }))

    # 待機者が2人以上になったら、ペアを作ってゲームルームを開始
    if len(waiting_players) >= 2:
        playerA = waiting_players.pop(0)
        playerB = waiting_players.pop(0)
        
        room_counter += 1
        room_id = f"room_{room_counter}"
        
        theme = random.choice(THEME_LIST)
        
        active_rooms[room_id] = {
            "clients": [playerA, playerB],
            "theme": theme,
            "targetForA": "",  # BがAに設定したワード
            "targetForB": "",  # AがBに設定したワード
            "turn": "A",
            "guessesA": 2,
            "guessesB": 2
        }
        
        # それぞれに役割（AとB）とテーマを通知
        await playerA.send(json.dumps({
            "type": "ASSIGN_ROLE",
            "role": "A",
            "theme": theme,
            "roomId": room_id
        }))
        await playerB.send(json.dumps({
            "type": "ASSIGN_ROLE",
            "role": "B",
            "theme": theme,
            "roomId": room_id
        }))

    try:
        async for message in websocket:
            data = json.loads(message)
            action = data.get("action")
            
            # どのルームからのメッセージか特定
            current_room = None
            for r_id, room in active_rooms.items():
                if websocket in room["clients"]:
                    current_room = room
                    break
            
            if not current_room:
                continue

            if action == "SET_TARGET":
                player = data.get("player")
                word = data.get("word")
                if player == "A":
                    current_room["targetForB"] = word
                else:
                    current_room["targetForA"] = word

                if current_room["targetForA"] and current_room["targetForB"]:
                    start_msg = json.dumps({
                        "type": "GAME_START",
                        "theme": current_room["theme"],
                        "targetForA": current_room["targetForA"],
                        "targetForB": current_room["targetForB"]
                    })
                    for client in current_room["clients"]:
                        await client.send(start_msg)

            elif action == "SEND_MESSAGE":
                sender = data.get("sender")
                text = data.get("text")
                
                current_room["turn"] = "B" if sender == "A" else "A"

                response = json.dumps({
                    "type": "NEW_MESSAGE",
                    "sender": sender,
                    "text": text,
                    "nextTurn": current_room["turn"]
                })
                for client in current_room["clients"]:
                    await client.send(response)

            elif action == "GUESS_WORD":
                sender = data.get("sender")
                guessed_word = data.get("word", "").strip()
                
                target_word = current_room["targetForB"] if sender == "A" else current_room["targetForA"]
                is_correct = (guessed_word == target_word)

                if sender == "A":
                    current_room["guessesA"] -= 1
                    remaining = current_room["guessesA"]
                else:
                    current_room["guessesB"] -= 1
                    remaining = current_room["guessesB"]

                winner = None
                is_game_over = False

                if is_correct:
                    winner = sender
                    is_game_over = True
                elif remaining <= 0:
                    winner = "B" if sender == "A" else "A"
                    is_game_over = True

                response = json.dumps({
                    "type": "GUESS_RESULT",
                    "sender": sender,
                    "guessedWord": guessed_word,
                    "isCorrect": is_correct,
                    "remainingGuesses": remaining,
                    "isGameOver": is_game_over,
                    "winner": winner,
                    "targetWord": target_word if is_game_over else None
                })
                for client in current_room["clients"]:
                    await client.send(clientws := client and response) # 送信処理

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # 切断時のクリーンアップ
        if websocket in waiting_players:
            waiting_players.remove(websocket)
            
        for r_id, room in list(active_rooms.items()):
            if websocket in room["clients"]:
                # 対戦相手に切断を通知
                for client in room["clients"]:
                    if client != websocket:
                        try:
                            await client.send(json.dumps({
                                "type": "OPPONENT_DISCONNECTED"
                            }))
                        except:
                            pass
                del active_rooms[r_id]
                break

async def main():
    port = int(os.environ.get("PORT", 8765))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"🚀 スパイチャットサーバー起動中 (Port: {port})")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())