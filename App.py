import threading
import time

import schedule

import App
import Bot
import Service

if __name__ == '__main__':
    t = threading.Thread(target=App.my_job)
    t.start()
    Bot.run()


def my_job():
    print('Start Job')
    schedule.every(1).hours.do(Service.sync_price)
    while True:
        schedule.run_pending()
        time.sleep(2)
