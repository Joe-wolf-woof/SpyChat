import asyncio
import json
import os
import random
import websockets

connected_clients = []

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

game_state = {
    "theme": "",
    "targetForA": "",  # BがAに設定したワード
    "targetForB": "",  # AがBに設定したワード
    "turn": "A",
    "guessesA": 2,     # Aの残り解読チャンス
    "guessesB": 2      # Bの残り解読チャンス
}

async def handler(websocket):
    if len(connected_clients) >= 2:
        await websocket.close(code=4000, reason="ルームが満員です")
        return

    connected_clients.append(websocket)
    player_id = "A" if len(connected_clients) == 1 else "B"
    
    if player_id == "A":
        game_state["theme"] = random.choice(THEME_LIST)
        game_state["targetForA"] = ""
        game_state["targetForB"] = ""
        game_state["turn"] = "A"
        game_state["guessesA"] = 2
        game_state["guessesB"] = 2

    await websocket.send(json.dumps({
        "type": "ASSIGN_ROLE",
        "role": player_id,
        "theme": game_state["theme"]
    }))

    try:
        async for message in websocket:
            data = json.loads(message)
            action = data.get("action")

            if action == "SET_TARGET":
                player = data.get("player")
                word = data.get("word")
                if player == "A":
                    game_state["targetForB"] = word
                else:
                    game_state["targetForA"] = word

                if game_state["targetForA"] and game_state["targetForB"]:
                    start_msg = json.dumps({
                        "type": "GAME_START",
                        "theme": game_state["theme"],
                        "targetForA": game_state["targetForA"],
                        "targetForB": game_state["targetForB"]
                    })
                    for client in connected_clients:
                        await client.send(start_msg)

            elif action == "SEND_MESSAGE":
                sender = data.get("sender")
                text = data.get("text")
                
                game_state["turn"] = "B" if sender == "A" else "A"

                response = json.dumps({
                    "type": "NEW_MESSAGE",
                    "sender": sender,
                    "text": text,
                    "nextTurn": game_state["turn"]
                })
                for client in connected_clients:
                    await client.send(response)

            elif action == "GUESS_WORD":
                sender = data.get("sender")
                guessed_word = data.get("word", "").strip()
                
                target_word = game_state["targetForB"] if sender == "A" else game_state["targetForA"]
                is_correct = (guessed_word == target_word)

                # 残り回数を減らす
                if sender == "A":
                    game_state["guessesA"] -= 1
                    remaining = game_state["guessesA"]
                else:
                    game_state["guessesB"] -= 1
                    remaining = game_state["guessesB"]

                winner = None
                is_game_over = False

                if is_correct:
                    winner = sender
                    is_game_over = True
                elif remaining <= 0:
                    # チャンスを使い切って不正解なら、相手の勝利（自滅敗北）
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
                for client in connected_clients:
                    await client.send(response)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
            if len(connected_clients) == 0:
                game_state["theme"] = ""
                game_state["targetForA"] = ""
                game_state["targetForB"] = ""

async def main():
    port = int(os.environ.get("PORT", 8765))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"🚀 スパイチャットサーバー起動中 (Port: {port})")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())