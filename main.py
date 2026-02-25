from fastapi import FastAPI, Request
import httpx
from sqlalchemy import text
from fastapi import Body
from db import engine

app = FastAPI()

ACCESS_TOKEN = "EAAc6MUxveJ0BQ0KR0NpRjde0IrcBLpCJzF5Gy5ZA5LwAmRn6VbzY41mU7gt4lQ8ZBxHM9acaSmLghRspcMTcyeIZChmOemZBfX4ZCvxNGwpKDrixVZCNRCTk1SrZBJH6YsjFWBcv3gEDMpmJTtHiUbPE5IXOETiSVXsUWKUOUCt0g2RVLfIZC8yb4yUb2GnHdJ5j3yN2VptzqCZCwQbPIWROsDwnHYyZAkRV6TBZB8EkKdk1jEk383YwDZACvCArnT9BIZBEGJGvJkrX9RgtHwrbqZCt8fZAPCx"
PHONE_NUMBER_ID = "1048865108303356"

@app.get("/")
async def health():
    return {"status": "AI Cruise Bot Running"}

#### Testing is our database connected #######
@app.get("/test-db")
async def test_db():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        return {"database": "connected"}
    

###################################
##  QUESTIONS AND ANSWERS #########
###################################
### ADDING ###
@app.post("/add-qa")
async def add_qa(
    question: str = Body(...),
    answer: str = Body(...)
):
    async with engine.connect() as conn:
        await conn.execute(
            text("""
                INSERT INTO knowledge_base (question, answer)
                VALUES (:question, :answer)
            """),
            {"question": question, "answer": answer}
        )
        await conn.commit()

    return {"status": "saved"}

### GETTING ###
@app.get("/qa-list")
async def list_qa():
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT question, answer FROM knowledge_base")
        )
        rows = result.fetchall()

    return [{"question": r[0], "answer": r[1]} for r in rows]

###################################
## FINDING QUESTIONS AND ANSWERS ##
###################################

@app.post("/ask")
async def ask_question(question: str = Body(...)):
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT question, answer
                FROM knowledge_base
                WHERE question ILIKE :query
                LIMIT 1
            """),
            {"query": f"%{question}%"}
        )

        row = result.fetchone()

    if row:
        return {"answer": row[1]}
    else:
        return {"answer": "I will forward your question to a human agent."}
    
###################################
######## SEARCH FROM DB ##########
###################################
async def find_answer(user_text: str):
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT answer
                FROM knowledge_base
                WHERE question ILIKE :query
                LIMIT 1
            """),
            {"query": f"%{user_text}%"}
        )

        row = result.fetchone()

    if row:
        return row[0]
    else:
        return "Thank you! Our cruise manager will contact you shortly."


###################################
######## FUCKING WEBHOOK ##########
###################################

VERIFY_TOKEN = "my_verify_token_123"

@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)

    return {"error": "Verification failed"}


@app.post("/webhook")
async def receive_message(request: Request):
    body = await request.json()

    try:
        message = body["entry"][0]["changes"][0]["value"]["messages"][0]
        text = message["text"]["body"]
        from_number = message["from"]

        print("Message:", text)

    except Exception:
        return {"status": "no message"}
    
    # Ищем ответ в БД
    reply_text = await find_answer(text)

    # Отправка ответа обратно
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "messaging_product": "whatsapp",
        "to": from_number,
        "text": {"body": reply_text}
    }

    async with httpx.AsyncClient() as client:
        await client.post(url, headers=headers, json=data)

    return {"status": "replied"}