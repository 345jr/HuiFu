import asyncio
from astrbot.api.event import filter, AstrMessageEvent,MessageChain ,MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.message.components import Plain

@register("todo_plugin", "lopop", "定时任务插件：创建待办事项并在指定时间提醒", "1.0.0")
class TodoPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 可以在这里初始化任务列表或其他状态
        self.tasks = []

    @filter.command("todo")
    async def todo_command(self, event: AstrMessageEvent, delay: int ,content: str):
        """
        参数:
            delay (int): 延迟的秒数（等待多少秒后提醒）。
            content (str): 待办事项的内容。
        """
        yield event.plain_result(f"任务以设置,在{delay}秒后提醒:")
        msg_origin = event.unified_msg_origin
        message_chain =MessageChain().message(content)
        await self.context.send_message(event.unified_msg_origin, message_chain)