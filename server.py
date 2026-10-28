import asyncio
import json
import os
import websockets

# 接続中のクライアントリスト
connected_clients = []

# ゲームの状態管理
game_state = {
    "theme": "プログラミング・IT技術",
    "targetForA": "",  # BがAに設定したワード
    "targetForB": "",  # AがBに設定したワード
    "turn": "A"
}

async def handler(websocket):
    if len(connected_clients) >= 2:
        await websocket.close(code=4000, reason="ルームが満員です")
        return

    connected_clients.append(websocket)
    player_id = "A" if len(connected_clients) == 1 else "B"
    
    # 役割の割り当て通知
    await websocket.send(json.dumps({
        "type": "ASSIGN_ROLE",
        "role": player_id,
        "theme": game_state["theme"]
    }))

    try:
        async for message in websocket:
            data = json.loads(message)
            action = data.get("action")

            # NGワード設定
            if action == "SET_TARGET":
                player = data.get("player")
                word = data.get("word")
                if player == "A":
                    game_state["targetForB"] = word  # AがBのターゲットを設定
                else:
                    game_state["targetForA"] = word  # BがAのターゲットを設定

                # 両者の設定が完了したらゲーム開始
                if game_state["targetForA"] and game_state["targetForB"]:
                    start_msg = json.dumps({
                        "type": "GAME_START",
                        "theme": game_state["theme"],
                        "targetForA": game_state["targetForA"],
                        "targetForB": game_state["targetForB"]
                    })
                    for client in connected_clients:
                        await client.send(start_msg)

            # チャットメッセージ受信
            elif action == "SEND_MESSAGE":
                sender = data.get("sender")
                text = data.get("text")
                
                # 勝敗判定（相手が仕掛けたターゲットを踏んだか）
                hit_target = game_state["targetForA"] if sender == "A" else game_state["targetForB"]
                is_win = hit_target in text

                # ターン交代
                game_state["turn"] = "B" if sender == "A" else "A"

                response = json.dumps({
                    "type": "NEW_MESSAGE",
                    "sender": sender,
                    "text": text,
                    "isWin": is_win,
                    "winner": sender if is_win else None,
                    "nextTurn": game_state["turn"]
                })
                for client in connected_clients:
                    await client.send(response)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

async def main():
    # クラウド環境（Render等）から割り当てられるPORT番号を取得（ローカル時は8765）
    port = int(os.environ.get("PORT", 8765))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"🚀 スパイチャットサーバー起動中 (Port: {port})")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())