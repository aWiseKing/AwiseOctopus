import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

class DAGExecutor:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.done = asyncio.Event()

    def my_job(self):
        print("Job executed!")
        # Can't set event here directly because it belongs to a different loop, but let's try
        self.done.set()

    async def execute(self):
        self.scheduler.add_job(self.my_job)
        self.scheduler.start()
        print('Scheduler started, waiting...')
        try:
            await asyncio.wait_for(self.done.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            print("Timeout! Jobs didn't run.")

if __name__ == "__main__":
    executor = DAGExecutor()
    asyncio.run(executor.execute())
