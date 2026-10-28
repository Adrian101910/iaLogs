from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    """Bound buffered bytes even when Content-Length is absent or dishonest."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        if headers.get(b"content-encoding", b"identity").lower() != b"identity":
            return await JSONResponse(status_code=415, content={"detail": "No se admite compresión del cuerpo"})(scope, receive, send)
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = -1
        if declared < 0:
            return await JSONResponse(status_code=400, content={"detail": "Content-Length no válido"})(scope, receive, send)
        if declared > self.max_bytes:
            return await JSONResponse(status_code=413, content={"detail": "Petición demasiado grande"})(scope, receive, send)
        body = bytearray()
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            body.extend(event.get("body", b""))
            if len(body) > self.max_bytes:
                return await JSONResponse(status_code=413, content={"detail": "Petición demasiado grande"})(scope, receive, send)
            if not event.get("more_body", False):
                break

        async def replay():
            nonlocal body
            if body is not None:
                data = bytes(body)
                body = None
                return {"type": "http.request", "body": data, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
