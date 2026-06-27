"""Run the media_intelligence HTTP bridge standalone:

    python -m media_intelligence.bridge            # serves POST /media/analyze on :8800
    HOST=0.0.0.0 PORT=9000 python -m media_intelligence.bridge
"""
from __future__ import annotations

import os

from .service import create_app


def main() -> None:
    app = create_app()
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8800")),
    )


if __name__ == "__main__":
    main()
