from helpers.api import ApiHandler, Input, Output, Request, Response
from helpers.task_scheduler import TaskScheduler


class Stop(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        ctxid = str(input.get("context") or input.get("ctxid") or "").strip()
        if not ctxid:
            return Response(
                '{"error": "context is required"}',
                status=400,
                mimetype="application/json",
            )

        try:
            context = self.use_context(ctxid, create_if_not_exists=False)
        except Exception:
            return Response(
                '{"error": "Chat context not found"}',
                status=404,
                mimetype="application/json",
            )

        was_running = context.is_running()
        scheduler_cancelled = TaskScheduler.get().cancel_tasks_by_context(
            ctxid,
            terminate_thread=True,
        )

        if was_running:
            context.kill_process()

        context.paused = False
        context.log.log(
            type="info",
            content="Task stopped by user." if was_running else "No running task to stop.",
        )

        from helpers.state_monitor_integration import mark_dirty_all

        mark_dirty_all(reason="api.stop.Stop")

        return {
            "ok": True,
            "context": context.id,
            "was_running": was_running,
            "running": context.is_running(),
            "scheduler_cancelled": scheduler_cancelled,
            "message": "Task stopped." if was_running else "No running task to stop.",
        }
