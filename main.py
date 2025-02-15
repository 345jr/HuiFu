import asyncio
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
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
    async def todo_command(self, event: AstrMessageEvent, delay: int):
        """
        创建一个待办事项定时提醒。

        参数:
            delay (int): 延迟的秒数（等待多少秒后提醒）。
            content (str): 待办事项的内容。

        示例:
            /todo 10 吃饭
        """
        # 先回复用户，确认待办事项已经创建
        await event.send(f"待办事项已创建，将在 {delay} 秒后提醒: {event.get_message_str()}")
        # 异步调度定时任务
        asyncio.create_task(self.schedule_todo(delay, event.get_message_str(), event.unified_msg_origin))
        # 同时可以立即返回一个结果
        yield event.plain_result("定时任务已调度。")

    async def schedule_todo(self, delay: int, content: str, unified_msg_origin: str):
        # 等待指定的时间
        await asyncio.sleep(delay)
        # 调用 LLM API 来生成提醒文本
        func_tools_mgr = self.context.get_llm_tool_manager()
        llm_response = await self.context.get_using_provider().text_chat(
            prompt=f"请生成一段待办事项提醒文本，内容为：{content}",
            session_id=None,
            contexts=[],
            image_urls=[],
            func_tool=func_tools_mgr,
            system_prompt="你是一个智能助手，负责生成友好且实用的待办事项提醒。"
        )
        # 处理 LLM 的响应，简化示例：只考虑 assistant 角色的情况
        if llm_response.role == "assistant":
            result_text = llm_response.completion_text
        elif llm_response.role == "tool":
            result_text = f"调用函数: {llm_response.tools_call_name}, 参数: {llm_response.tools_call_args}"
        else:
            result_text = "无法生成提醒信息。"
        # 构造消息链，包含待办事项内容和 LLM 返回的提醒文本
        message_chain = [
            Plain(f"待办事项提醒: {content}\n提醒内容: {result_text}")
        ]
        # 通过 unified_msg_origin 将消息发送回原会话
        await self.context.send_message(unified_msg_origin, message_chain)