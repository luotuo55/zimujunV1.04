from __future__ import print_function
from volcenginesdkarkruntime import Ark
from flask import Flask, request, render_template, send_from_directory, jsonify
from dotenv import load_dotenv
import os
import requests
import json
import logging
import time
from werkzeug.exceptions import RequestEntityTooLarge
from moviepy.editor import VideoFileClip
import traceback
import re

# 加载环境变量
load_dotenv()

# API配置
ACCESS_KEY = os.getenv('ACCESS_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
DOUBAO_MODEL_ID = os.getenv('DOUBAO_MODEL_ID')

# 初始化 Ark 客户端
ark_client = None

# 全局变量，用于存储令牌
appid = os.getenv('APPID')
token = os.getenv('TOKEN')
cluster = os.getenv('CLUSTER')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SUBTITLE_FOLDER'] = 'subtitles'
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

# 确保上传和字幕目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SUBTITLE_FOLDER'], exist_ok=True)

# 更新版本号
VERSION = "V1.04"

def init_api_keys():
    """初始化API密钥"""
    global ark_client
    # 设置环境变量
    os.environ['VOLC_ACCESSKEY'] = ACCESS_KEY
    os.environ['VOLC_SECRETKEY'] = SECRET_KEY
    
    # 初始化客户端
    ark_client = Ark(ak=ACCESS_KEY, sk=SECRET_KEY)

def is_token_valid():
    """检查令牌是否有效"""
    return token is not None

def upload_audio(file_path):
    """上传音频文件到服务器"""
    server_url = os.getenv('UPLOAD_SERVER_URL')
    api_key = os.getenv('UPLOAD_API_KEY')
    
    print("\n=== 上传音频文件 ===")
    print(f"上传URL: {server_url}")
    print(f"文件路径: {file_path}")
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        headers = {
            'X-Admin-Key': api_key,
            'Origin': 'http://localhost:5000'
        }
        
        print("\n请求信息:")
        print(f"Headers: {headers}")
        
        try:
            response = requests.post(server_url, files=files, headers=headers)
            
            print("\n服务器响应:")
            print(f"状态码: {response.status_code}")
            print(f"响应头: {dict(response.headers)}")
            print(f"响应内容: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n解析的JSON结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
                
                if result.get('code') == 200:
                    filename = result['data'].get('filename')
                    if filename:
                        file_url = f"http://www.52ai.fun/audio/voice/{filename}"
                        print(f"\n上传成功! 文件URL: {file_url}")
                        return file_url
                    else:
                        print("\n错误: 响应中没有文件名")
                        return None
                else:
                    print(f"\n错误: 上传失败 - {result.get('message')}")
                    return None
            else:
                print(f"\n错误: 请求失败 - {response.text}")
                return None
                
        except Exception as e:
            print(f"\n错误: 上传过程异常 - {str(e)}")
            print(f"详细错误: {traceback.format_exc()}")
            return None

def submit_task(audio_url):
    """提交语音识别任务"""
    service_url = "https://openspeech.bytedance.com/api/v1/auc/submit"
    
    request_data = {
        "app": {
            "appid": appid,
            "token": token,
            "cluster": cluster
        },
        "user": {
            "uid": "388808087185088_demo"
        },
        "audio": {
            "url": audio_url,  # 确保这是完整的URL
            "format": "mp3"
        },
        "additions": {
            "with_speaker_info": "False"
        }
    }
    
    headers = {
        'Authorization': f'Bearer; {token}',
        'Content-Type': 'application/json'
    }
    
    print("提交请求:", json.dumps(request_data))
    response = requests.post(service_url, json=request_data, headers=headers)
    print("响应内容:", response.text)
    
    if response.status_code == 200:
        result = response.json()
        if result.get('resp', {}).get('code') == 1000:
            return result['resp']['id']
    logging.error(f"提交任务失败: {response.text}")
    return None

def query_task(task_id):
    """查询任务状态"""
    service_url = "https://openspeech.bytedance.com/api/v1/auc/query"
    
    request_data = {
        "appid": appid,
        "token": token,
        "id": task_id,
        "cluster": cluster
    }
    
    headers = {
        'Authorization': f'Bearer; {token}',  # 注意这里加了分号
        'Content-Type': 'application/json'
    }
    
    print("查询请求:", json.dumps(request_data))  # 添加日志
    response = requests.post(service_url, json=request_data, headers=headers)
    print("响应内容:", response.text)  # 添加日志
    
    if response.status_code == 200:
        return response.json()
    logging.error(f"查询任务失败: {response.text}")
    return None

def process_with_doubao(text):
    """使用豆包API优化文本，但保持原始格式"""
    try:
        prompt = f"""
请优化以下文本，要求：
1. 保持简洁明了
2. 每句不超过15字
3. 确保语意完整
4. 修正明显错误
5. 不要改变原意

原文：{text}
"""
        # ... 豆包API调用代码 ...
        return processed_text
    except Exception as e:
        print(f"豆包API处理失败: {e}")
        return text

def convert_to_srt(response_data):
    """将语音识别结果转换为SRT格式字幕"""
    try:
        utterances = response_data.get('resp', {}).get('utterances', [])
        if not utterances:
            print("没有找到语音分段数据")
            return ""
            
        srt_content = []
        for i, utterance in enumerate(utterances, 1):
            start_time = int(utterance.get('start_time', 0))
            end_time = int(utterance.get('end_time', 0))
            text = utterance.get('text', '').strip()
            
            if text:
                # 使用原始时间戳
                start_formatted = format_time(start_time)
                end_formatted = format_time(end_time)
                
                # 格式化为要求的格式
                srt_entry = f"{i}\n{start_formatted} --> {end_formatted}\n{text}\n\n"
                srt_content.append(srt_entry)
        
        return "".join(srt_content)
            
    except Exception as e:
        print(f"转换SRT格式失败: {e}")
        print(f"错误详情: {traceback.format_exc()}")
        return ""

def format_time(milliseconds):
    """将毫秒转换为SRT时间格式"""
    seconds = milliseconds / 1000
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    millisecs = int((seconds % 1) * 1000)
    seconds = int(seconds)
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millisecs:03d}"

def convert_video_to_mp3(video_path):
    """将视频文件转换为MP3"""
    try:
        # 创建VideoFileClip对象
        video = VideoFileClip(video_path)
        
        # 生成输出文件路径
        output_path = os.path.splitext(video_path)[0] + '.mp3'
        
        # 提取音频并保存为MP3
        video.audio.write_audiofile(output_path)
        
        # 关闭视频文件
        video.close()
        
        return output_path
    except Exception as e:
        print(f"转换失败: {str(e)}")
        return None

@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(error):
    return jsonify({"error": "上传的文件过大，请选择一个较小的文件。"}), 413

@app.route('/')
def index():
    """首页"""
    return render_template('index.html', version=VERSION)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "没有文件上传"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "没有选择文件"}), 400

    if file:
        try:
            # 获取文件扩展名
            ext = os.path.splitext(file.filename)[1].lower()
            
            # 保存视频文件
            video_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(video_path)
            
            # 如果是视频文件，先转换为MP3
            video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'}
            if ext in video_extensions:
                mp3_path = convert_video_to_mp3(video_path)
                if not mp3_path:
                    return jsonify({"error": "视频转换MP3失败"}), 500
                audio_path = mp3_path
            else:
                audio_path = video_path

            # 上传音频文件
            audio_url = upload_audio(audio_path)
            if not audio_url:
                return jsonify({"error": "音频文件上传失败"}), 500

            # 提交任务
            task_id = submit_task(audio_url)
            if not task_id:
                return jsonify({"error": "提交任务失败"}), 500

            return jsonify({
                "status": "processing",
                "task_id": task_id,
                "message": "任务已提交，正在处理中"
            }), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['SUBTITLE_FOLDER'], filename)

@app.route('/status/<task_id>', methods=['GET'])
def check_status(task_id):
    """检查任务状态"""
    try:
        result = query_task(task_id)
        if not result:
            return jsonify({
                "version": VERSION,
                "status": "pending",
                "message": "任务处理中..."
            })
            
        status = result.get('resp', {}).get('code')
        
        # 语音识别进行中
        if status != 1000:
            return jsonify({
                "version": VERSION,
                "status": "recognizing",
                "message": "正在进行语音识别..."
            }), 200
            
        # 语音识别完成，开始文本优化
        text = result.get('resp', {}).get('text', '')
        if not text:
            return jsonify({
                "version": VERSION,
                "status": "failed",
                "error": "语音识别结果为空"
            }), 500
            
        # 返回正在进行文本优化的状态
        return jsonify({
            "version": VERSION,
            "status": "optimizing",
            "message": "正在进行文本优化..."
        }), 200

    except Exception as e:
        return jsonify({
            "version": VERSION,
            "status": "error",
            "message": str(e)
        })

@app.route('/optimize/<task_id>', methods=['GET'])
def optimize_text(task_id):
    """文本优化和生成字幕"""
    try:
        # 1. 获取原始识别结果
        result = query_task(task_id)
        if not result or result.get('resp', {}).get('code') != 1000:
            return jsonify({"version": VERSION, "status": "failed", "error": "任务未完成"}), 400

        # 2. 先生成带时间戳的SRT
        srt_content = convert_to_srt(result)
        if not srt_content:
            return jsonify({"version": VERSION, "status": "failed", "error": "生成字幕失败"}), 500

        # 3. 保存字幕文件
        subtitle_file = os.path.join(app.config['SUBTITLE_FOLDER'], f"{task_id}.srt")
        with open(subtitle_file, 'w', encoding='utf-8') as f:
            f.write(srt_content)

        return jsonify({
            "version": VERSION,
            "status": "completed",
            "subtitle_file": f"/download/{task_id}.srt"
        }), 200

    except Exception as e:
        print(f"处理失败: {e}")
        print(traceback.format_exc())
        return jsonify({
            "version": VERSION,
            "status": "failed",
            "error": str(e)
        }), 500

if __name__ == '__main__':
    init_api_keys()
    app.run(
        host='0.0.0.0', 
        port=5000, 
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )