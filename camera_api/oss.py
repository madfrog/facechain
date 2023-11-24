# coding=utf-8

import oss2
from oss2.credentials import EnvironmentVariableCredentialsProvider
import os
import time
from typing import List

auth = oss2.ProviderAuth(EnvironmentVariableCredentialsProvider())
bucket = oss2.Bucket(auth, 'http://oss-cn-shenzhen.aliyuncs.com', 'voyagerke-test')


def oss_download(urls, keyword) -> List:
    base_dir = f'/tmp/sd/{keyword}'
    if os.path.exists(base_dir) is not True:
        os.makedirs(base_dir)
    local_time = time.localtime(time.time())
    folder_name = f'{local_time.tm_year.real}_{local_time.tm_mon.real}_{local_time.tm_mday.real}'
    if os.path.exists(f'{base_dir}/{folder_name}') is not True:
        os.makedirs(f'{base_dir}/{folder_name}')

    download_location = []
    for url in urls:
        print(f'dest: {base_dir}/{folder_name}/{url}')
        print(f'url: {url}')
        bucket.get_object_to_file(url, f'{base_dir}/{folder_name}/{url}')
        download_location.append(f'{base_dir}/{folder_name}/{url}')
    print(f'all urls download success: {urls}')

    return download_location
