from fastapi import FastAPI, Request
from pydantic import BaseModel
import uvicorn

app = FastAPI()

# Define the structure of incoming data
class RaidData(BaseModel):
    tweet_url: str
    message: str

@app.post("/raid")
async def receive_raid(data: RaidData):
    # For now, just print what we receive
    print(f"Received raid: {data.tweet_url} | Message: {data.message}")
    # Here, you can later add the browser automation code to post to Twitter
    return {"status": "ok", "tweet_received": data.tweet_url}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
