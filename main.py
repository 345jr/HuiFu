import asyncio
import json
from astrbot.api.event import filter, AstrMessageEvent, MessageChain, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.message.components import Plain


@register("todo_plugin", "lopop", "定时任务插件：创建待办事项并在指定时间提醒", "1.0.0")
class TodoPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.tasks = []

    @filter.command("todo")
    async def todo_command(self, event: AstrMessageEvent, delay: int, content: str):
        """
        参数:
            delay (int): 延迟的秒数（等待多少秒后提醒）。
            content (str): 待办事项的内容。
        """
        yield event.plain_result(f"任务以设置,在{delay}秒后提醒:")
        msg_origin = event.unified_msg_origin

        llm_response = await self.context.get_using_provider().text_chat(
            prompt=content,
            session_id=None,  # 此已经被废弃
            contexts=[],  # 也可以用上面获得的用户当前的对话记录 context
            image_urls=[],  # 图片链接，支持路径和网络链接
            func_tool=None,
            system_prompt="",  # 系统提示，可以不传
        )

        await asyncio.sleep(delay)
        message_chain = MessageChain().message(llm_response.completion_text)
        await self.context.send_message(msg_origin, message_chain)
