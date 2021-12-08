from apscheduler.schedulers.blocking import BlockingScheduler
from server.sync import sync_blocks

background = BlockingScheduler()
background.add_job(sync_blocks, "interval", seconds=5)
background.start()
