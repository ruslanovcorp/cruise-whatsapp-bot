import os
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import Depends, HTTPException, status
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import httpx
from sqlalchemy import text
from fastapi import Body
from db import engine

app = FastAPI()

ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
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
        response = await client.post(url, headers=headers, json=data)
        if response.status_code != 200:
            print("Meta error:", response.text)

    return {"status": "replied"}


###################################
########### FRONTEND ##############
###################################

##### SECURITY #######
security = HTTPBasic()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    
###### DELETE ##########
@app.delete("/delete-qa/{question}")
async def delete_qa(question: str, user: str = Depends(verify_admin)):
    async with engine.connect() as conn:
        await conn.execute(
            text("DELETE FROM knowledge_base WHERE question = :q"),
            {"q": question}
        )
        await conn.commit()
    return {"status": "deleted"}

###### UPDATE ##########
@app.put("/update-qa")
async def update_qa(
    question: str = Body(...),
    answer: str = Body(...),
    user: str = Depends(verify_admin)
):
    async with engine.connect() as conn:
        await conn.execute(
            text("""
                UPDATE knowledge_base
                SET answer = :answer
                WHERE question = :question
            """),
            {"question": question, "answer": answer}
        )
        await conn.commit()
    return {"status": "updated"}

###### FRONT ##########

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(user: str = Depends(verify_admin)):
    return """
    <html>
    <head>
        <title>Cruise Bot Admin</title>
        <style>
            body {
                font-family: Arial;
                background: #f4f6f9;
                max-width: 900px;
                margin: 40px auto;
            }
            h2 { color: #1a2b49; }
            .card {
                background: white;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            }
            input, textarea {
                width: 100%;
                padding: 10px;
                margin: 5px 0;
                border-radius: 5px;
                border: 1px solid #ccc;
            }
            button {
                padding: 8px 12px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
            }
            .save { background: #2d89ef; color: white; }
            .delete { background: #e81123; color: white; }
            .update { background: #107c10; color: white; }
        </style>
    </head>
    <body>

        <h2>🚢 Cruise Bot Admin Panel</h2>

        <div class="card">
            <h3>Add Question & Answer</h3>
            <input id="question" placeholder="Question keyword">
            <textarea id="answer" placeholder="Bot answer"></textarea>
            <button class="save" onclick="addQA()">Save</button>
        </div>

        <div class="card">
            <h3>Knowledge Base</h3>
            <div id="qa-list"></div>
        </div>

<script>
async function loadQA() {
    const res = await fetch('/qa-list');
    const data = await res.json();

    const container = document.getElementById('qa-list');
    container.innerHTML = "";

    data.forEach(item => {
        container.innerHTML += `
            <div style="margin-bottom:15px;">
                <input value="${item.question}" id="q-${item.question}">
                <textarea id="a-${item.question}">${item.answer}</textarea>
                <button class="update" onclick="updateQA('${item.question}')">Update</button>
                <button class="delete" onclick="deleteQA('${item.question}')">Delete</button>
                <hr>
            </div>
        `;
    });
}

async function addQA() {
    const question = document.getElementById('question').value;
    const answer = document.getElementById('answer').value;

    await fetch('/add-qa', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({question, answer})
    });

    loadQA();
}

async function deleteQA(question) {
    await fetch(`/delete-qa/${question}`, {method: 'DELETE'});
    loadQA();
}

async function updateQA(question) {
    const answer = document.getElementById(`a-${question}`).value;

    await fetch('/update-qa', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({question, answer})
    });

    loadQA();
}

loadQA();
</script>

    </body>
    </html>
    """