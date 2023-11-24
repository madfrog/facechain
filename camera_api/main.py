# coding=utf-8

import os
import time
from flask import Flask, request, jsonify
import json
from app import Trainer, launch_pipeline_inpaint
import threading
from .task_recorder import TaskRecorder
from .oss import oss_download

from logging.config import dictConfig

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'DEBUG',
        'handlers': ['wsgi']
    }
})


app = Flask(__name__)

LORA_BASE_DIR = '/facechain/worker_data/qw/ly261666/cv_portrait_model'
LORA_FILE_NAME = 'pytorch_lora_weights.bin'
INFERENCE_BASE_DIR = '/facechain/inpaint_result'
# in seconds
LORA_TRAINING_TIMEOUT = 600
INPAINT_INFERENCE_TIMEOUT = 300

@app.route("/virtual-identity", methods=['POST'])
def train_virtual_identity():
    j_data = json.loads(request.get_data())
    print(f'j_data: {j_data}')
    uuid = ''
    images_urls = j_data['instance_image_urls']
    # lora name
    output_model_name = j_data['virtual_identity_id']

    # download from oss
    image_locations = oss_download(images_urls, "train_lora")
    instance_images = []
    for lo in image_locations:
        instance_images.append({
            "name": lo,
            "is_file": True
        })

    t = threading.Thread(target=start_lora_train_job, args=(uuid, instance_images, output_model_name,))
    t.start()
    print(f'start train thread success')

    # update task record
    recorder = TaskRecorder()
    recorder.set(output_model_name, int(time.time()))

    response = {
        "code": 0,
        "msg": "start successfully"
    }
    return jsonify(response)


def start_lora_train_job(uuid, instance_images, output_model_name) -> str:
    trainer = Trainer()
    message = trainer.run(uuid, instance_images, output_model_name)
    print(f'response from trainer: {message}')
    return message


@app.route("/virtual-identity/<virtual_identity_id>/process", methods=['GET'])
def get_lora_train_process(virtual_identity_id):
    lora_name = virtual_identity_id
    '''
    4 situations:
      1. The folder with 'lora_name' has not been created, process is running, 0
      2. The folder was created, 'pytorch_lora_weights.bin' has not been create, process is running, 0
      3. Timeout for creating 'pytorch_lora_weights.bin', currently timeout is set to be 10 mins, -1
      4. 'pytorch_lora_weights.bin' was created successfully, 1
    '''
    task_recorder = TaskRecorder()
    is_timeout = False
    if task_recorder.check_timeout(lora_name, LORA_TRAINING_TIMEOUT):
        is_timeout = True

    lora_dir = f'{LORA_BASE_DIR}/{lora_name}'
    lora_dir_exists = os.path.exists(lora_dir)
    if lora_dir_exists is not True:
        print(f'{lora_dir} has not been created')
        if is_timeout is not True:
            return jsonify({"code": "0", "message": "training task is running"})

    # if the folder was created, check file exists
    lora_file_with_path = f'{LORA_BASE_DIR}/{lora_name}/{LORA_FILE_NAME}'
    print(f'lora file path: {lora_file_with_path}')
    app.logger.debug(f'lora file path: {lora_file_with_path}')
    if os.path.exists(lora_file_with_path) is not True:
        print(f'{lora_file_with_path} has not been created')
        if is_timeout is not True:
            return jsonify({"code": "0", "message": "training task is running"})
    else:
        print(f'{lora_file_with_path} has been created')
        return jsonify({"code": "1", "message": "lora was created successfully"})
    return jsonify({"code": "-1", "message": "training task timeout"})


@app.route("/virtual-identity/images", methods=['POST'])
def inference_with_fixed_template():
    j_data = json.loads(request.get_data())
    print(f'inference with template params: {j_data}')
    task_id = j_data['task_id']
    num_faces = j_data['num_faces']
    user_models = j_data['user_models']
    template_image_url = j_data['template_image_url']
    uuid = 'qw'
    base_model_index = 0
    if len(user_models) != num_faces:
        print(f'lora number should be equal to face number')
        return jsonify({"code": "-1", "message": "lora number should be equal to face number"})
    if len(user_models) > 2 or num_faces > 2:
        print(f'lora or face number should not greater than 2')
        return jsonify({"code": "-1", "message": "lora or face number should not greater than 2"})
    user_model_A = user_models[0]
    if len(user_models) > 1:
        user_model_B = user_models[1]
    else:
        user_model_B = '不重绘该人物(Do not inpaint this character)'

    # download template image
    template_image = oss_download([template_image_url], "inpaint")[0]

    try:
        t = threading.Thread(target=launch_pipeline_inpaint, args=(uuid, base_model_index, user_model_A,
                                                                   user_model_B, num_faces, template_image, task_id,))
        t.start()

        # create result dir
        result_dir = f'{INFERENCE_BASE_DIR}/{task_id}'
        if os.path.exists(result_dir) is not True:
            os.makedirs(result_dir)

        # update task record
        recorder = TaskRecorder()
        recorder.set(task_id, int(time.time()))
        print(f'inference with template thread start...')
    except Exception as e:
        print(e)
        return jsonify({"code": "-1", "message": "inference task start failed"})
    return jsonify({"code": "0", "message": "inference task start successfully"})


@app.route("/virtual-identity/images", methods=['GET'])
def get_inpaint_result():
    task_id = request.args['task_id']
    result_dir = f'{INFERENCE_BASE_DIR}/{task_id}'

    is_timeout = False
    task_recorder = TaskRecorder()
    if task_recorder.check_timeout(task_id, INPAINT_INFERENCE_TIMEOUT):
        is_timeout = True

    # if the folder doesn't exist, the inference task may start failed
    if os.path.exists(result_dir) is not True:
        return jsonify({"code": "-1", "message": "inference task may failed"})
    if os.path.exists(f'{result_dir}/inpaint_{task_id}_*.png') is not True:
        if is_timeout is not True:
            return jsonify({"code": "0", "message": "inference task is running"})
    else:
        return jsonify({"code": "1", "message": "inference task is success"})
    return jsonify({"code": "-1", "message": "inference task timeout"})


