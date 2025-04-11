# debug

from loguru import logger
from pyinstrument import Profiler
from fastapi.responses import HTMLResponse
from starlette_context import request_cycle_context
from starlette.requests import Request, HTTPConnection
from starlette.responses import Response
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette_context.plugins.base import Plugin

from common.context import (
    RequestIdPlugin,
    RequestProcessInfoPlugin,
    RequestStartTimestampPlugin,
)
from configs.config import local_configs
from common.decorators import singleton


async def context_middleware(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    @singleton()
    class ContextMiddleware:
        plugins: list[Plugin]

        def __init__(self, plugins: list[Plugin]) -> None:
            self.plugins = plugins

        async def set_context(
            self,
            request: Request | HTTPConnection,
        ) -> dict:
            return {plugin.key: await plugin.process_request(request) for plugin in self.plugins}

        async def enrich_response(self, response: Response) -> None:
            for i in self.plugins:
                await i.enrich_response(response)

        async def __call__(
            self,
            request: Request,
            call_next: RequestResponseEndpoint,
        ) -> Response:
            context = await self.set_context(request)
            with (
                request_cycle_context(context),
                logger.contextualize(
                    request_id=context.get(RequestIdPlugin.key),
                ),
            ):
                profile_secret = request.query_params.get("profile_secret", "")
                # 开启性能分析
                # profile_secret = local_configs.server.profiling.secret
                if (
                    profile_secret
                    and local_configs.server.profiling
                    and profile_secret == local_configs.server.profiling.secret
                ):
                    profiler = Profiler(
                        interval=local_configs.server.profiling.interval,
                        async_mode="enabled",
                    )
                    profiler.start()
                    response = await call_next(request)
                    profiler.stop()
                    return HTMLResponse(profiler.output_html())
                    # await self.enrich_response(response)
                    # request_start_timestamp = s_context.get(RequestStartTimestampPlugin.key)
                    # if request_start_timestamp:
                    #     process_time = (time.time() - float(request_start_timestamp)) * 1000  # ms
                    #     if process_time > 2000:
                    #         profiler.write_html(path=f"{BASE_DIR}/static/{context.get(RequestIdPlugin.key)}.html")
                    # return response
                response = await call_next(request)
                await self.enrich_response(response)
                return response

    _context_middleware = ContextMiddleware(
        plugins=[
            RequestStartTimestampPlugin(),
            RequestIdPlugin(),
            RequestProcessInfoPlugin(),
        ],
    )

    return await _context_middleware(request, call_next)


roster = [
    # >>>>> Middleware Func
    context_middleware,
    (GZipMiddleware, {"minimum_size": 1000}),
    # >>>>> Middleware Class
    (
        CORSMiddleware,
        {
            "allow_origins": local_configs.server.cors.allow_origins,
            "allow_credentials": local_configs.server.cors.allow_credentials,
            "allow_methods": local_configs.server.cors.allow_methods,
            "allow_headers": local_configs.server.cors.allow_headers,
            "expose_headers": local_configs.server.cors.expose_headers,
        },
    ),
    (
        TrustedHostMiddleware,
        {
            "allowed_hosts": local_configs.server.allow_hosts,
        },
    ),
]
