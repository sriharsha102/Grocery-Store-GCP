# backend/gateway.py
import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

import main as main_module
import token_service as token_module

root = FastAPI(title="Unified App")
root.mount("/api",   main_module.app)
root.mount("/token", token_module.app)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    root.mount("/static", StaticFiles(directory=STATIC_DIR, html=False), name="static")

@root.get("/{_path:path}")
def spa(_path: str):
    index_html = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_html):
        return FileResponse(index_html)
    # UI not built yet
    raise HTTPException(status_code=503, detail="Frontend not built. Run `npm run build` and copy to backend/static.")
