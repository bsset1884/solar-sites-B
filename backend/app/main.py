from fastapi import FastAPI

app = FastAPI(title="Solar sites")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}