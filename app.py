from __future__ import annotations

import os

import uvicorn


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    # Run the FastAPI app defined in backend/app.py as `app`
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, workers=1)






