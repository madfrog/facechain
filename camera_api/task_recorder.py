# coding=utf8

import threading
import json
import time


class TaskRecorder(object):
    __instance = None
    __instance_flag = False
    __instance_lock = threading.Lock()
    print(f'init task recorder1111')

    def __new__(cls, *args, **kwargs):
        if cls.__instance == None:
            with cls.__instance_lock:
                if cls.__instance == None:
                    cls.__instance = object.__new__(cls)
        return cls.__instance

    def __init__(self):
        if self.__instance_flag is not True:
            print(f'init task recorder')
            self.__recorder = {}
            self.__instance_flag = True

    def set(self, key: str, val: int):
        self.__recorder[key] = val

    def get(self, key: str) -> int:
        if key in self.__recorder.keys():
            return self.__recorder[key]
        return 0

    def remove(self, key: str):
        del self.__recorder[key]

    def check_timeout(self, key: str, timeout: int) -> bool:
        if key not in self.__recorder.keys():
            return True
        current = int(time.time())
        if abs(current - self.get(key)) > timeout:
            return True
        return False

    def persist(self):
        with open("./task_records.txt", 'w') as f:
            records = json.dumps(self.__recorder)
            f.write(records)
            print(f'Task recorder update successfully: {records}')
