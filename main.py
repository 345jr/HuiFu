import os
import json
import uuid
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger 
from apscheduler.triggers.date import DateTrigger
from astrbot.api.event import filter, AstrMessageEvent, MessageChain, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.message.components import Plain


@register("todo_plugin", "lopop", "定时任务插件：创建待办事项并在指定时间提醒", "1.0.0")
class TodoPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.tasks_file = os.path.join(os.path.dirname(__file__), "todo_tasks.json")
        self.tasks = self.load_tasks()
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
        for task in self.tasks:
            self.schedule_task(task)

    def load_tasks(self):
        """从 JSON 文件中加载任务列表"""
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载任务失败: {e}")
                return []
        else:
            return []

    def save_tasks(self, tasks):
        """将任务列表写入 JSON 文件"""
        try:
            with open(self.tasks_file, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"保存任务失败: {e}")

    def add_task(self, msg_origin: str, time_str: str, content: str, recurring: bool):
        """添加任务,返回任务ID"""
        task_id = str(uuid.uuid4())
        task = {
            "id": task_id,
            "msg_origin": msg_origin,
            "time_str": time_str,  # 格式 "HH:MM"
            "content": content,
            "recurring": recurring,
        }
        self.tasks.append(task)
        self.save_tasks(self.tasks)
        self.schedule_task(task)
        return task_id

    def remove_task(self, task_id: str):
        """删除任务，同时取消调度"""
        try:
            self.scheduler.remove_job(task_id)
        except Exception as e:
            logger.error(f"移除调度任务失败: {e}")
        self.tasks = [t for t in self.tasks if t["id"] != task_id]
        self.save_tasks(self.tasks)

    def schedule_task(self, task: dict):
        """为任务添加调度，支持每日重复和一次性任务"""
        time_str = task["time_str"]
        try:
            hour, minute = map(int, time_str.split(":"))
        except Exception as e:
            logger.error(f"任务 {task['id']} 时间格式错误: {time_str}")
            return

        async def job_func():
            await self.execute_task(task)

            if task["recurring"]:
                # 每天在指定时间执行
                trigger = CronTrigger(hour=hour, minute=minute)
                self.scheduler.add_job(job_func, trigger=trigger, id=task["id"])
            else:
                # 计算下次执行时间（今天未到则今天，否则明天）
                run_date = self.compute_next_datetime(hour, minute)
                trigger = DateTrigger(run_date=run_date)
                self.scheduler.add_job(job_func, trigger=trigger, id=task["id"])

    def compute_next_datetime(self, hour: int, minute: int):
        """计算距离现在最近的指定时间点"""
        now = datetime.now()
        run_date = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_date <= now:
            run_date += timedelta(days=1)
        return run_date

    async def execute_task(self, task: dict):
        """任务到时时调用：使用 LLM 生成提醒文本并发送给用户，非重复任务执行后删除"""
        config = self.context.get_config()
        persona_config = config["persona"][0]
        prompt = persona_config["prompt"]

        llm_response = await self.context.get_using_provider().text_chat(
            prompt=task["content"],
            session_id=None,
            contexts=[],
            image_urls=[],
            func_tool=None,
            system_prompt=prompt,
        )
        message_chain = MessageChain().message(llm_response.completion_text)
        await self.context.send_message(task["msg_origin"], message_chain)

        # 如果是一次性任务，执行后自动删除
        if not task["recurring"]:
            self.remove_task(task["id"])

    @filter.command_group("todo")
    def todo(self):
        """待办任务管理命令组"""
        pass

    @todo.command("add")
    async def todo_add(
        self, event: AstrMessageEvent, time_str: str,recurring:bool=False, *, content: str ,
    ):
        """
        添加任务：
            time_str: 时间，格式 "HH:MM"（例如 "14:30")
            recurring: 是否每日重复任务 (True/False)默认为False
            content: 待办事项内容
        示例:
            /todo add 14:30 True 喝水
        """
        
        task_id = self.add_task(event.unified_msg_origin, time_str, content, recurring)
        yield event.plain_result(
            f"任务添加成功, 任务ID: {task_id}。时间: {time_str}, 重复: {recurring}"
        )
        
    @todo.command("list")
    async def todo_list(self, event: AstrMessageEvent):
        """
        查看当前用户的任务列表
        """
        user_origin = event.unified_msg_origin
        user_tasks = [t for t in self.tasks if t["msg_origin"] == user_origin]
        if not user_tasks:
            yield event.plain_result("您当前没有任务。")
        else:
            msg = "您的任务列表：\n"
            for t in user_tasks:
                msg += f"ID: {t['id']} 时间: {t['time_str']} 重复: {t['recurring']} 内容: {t['content']}\n"
            yield event.plain_result(msg)

    @todo.command("delete")
    async def todo_delete(self, event: AstrMessageEvent, task_id: str):
        """
        删除任务：
            task_id: 任务ID
        示例:
            /todo delete <任务ID>
        """
        task = next(
            (
                t
                for t in self.tasks
                if t["id"] == task_id and t["msg_origin"] == event.unified_msg_origin
            ),
            None,
        )
        if not task:
            yield event.plain_result("任务不存在或不属于您。")
        else:
            self.remove_task(task_id)
            yield event.plain_result("任务已删除。")
