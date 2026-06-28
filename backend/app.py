from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uvicorn

app = FastAPI()

# Allow your HTML file to call this API (even from file:// or localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/itr2/submit")
async def submit_itr2(request: Request):
    data = await request.json()

    # Just print it to terminal for now — you'll see the full payload
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ITR-2 Submission received:")
    print(f"  PAN    : {data.get('personalInfo', {}).get('pan', 'N/A')}")
    print(f"  Name   : {data.get('personalInfo', {}).get('firstName', '')} {data.get('personalInfo', {}).get('lastName', '')}")
    print(f"  Keys   : {list(data.keys())}")

    #Save JSON to a file, handle creation of file
    import os
    os.makedirs("/home/shivam/Documents/Projects/itr-file/submissions", exist_ok=True)

    print(data)
    with open(f'/home/shivam/Documents/Projects/itr-file/submissions/itr2_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json', 'w') as f:
        f.write(str(data))
    

    return {
        "status": "success",
        "message": "ITR-2 received successfully",
        "ack_number": f"ACK{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "received_at": datetime.now().isoformat(),
    }


@app.post("/auth/login")
async def login(request: Request):
    # Mock login — accepts anything, returns a fake token
    form = await request.form()
    return {
        "access_token": "mock_jwt_token_123",
        "token_type": "bearer",
        "user": {"name": form.get("username", "User")}
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)