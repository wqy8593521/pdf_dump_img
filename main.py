from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from pathlib import Path
import os
import shutil
import threading
import webbrowser
import signal
import sys
import zipfile
import json
import urllib.parse
from werkzeug.utils import secure_filename

from extract_images import extract_images_from_pdf
from split_subimages import process_directory

app = Flask(__name__)

# 全局变量存储处理状态和结果
processing_status = {
    'is_processing': False,
    'progress': 0,
    'status': '等待开始...',
    'log': [],
    'extracted_images': [],  # 存储提取的图片路径
    'split_results': {},     # 存储分割结果
    'current_step': 'none',   # none, extracting, splitting, complete
    'current_pdf_name': '',   # 保存当前PDF名称用于后续处理
    'subimages_count': 8  # 默认子图数量
}

# 在文件开头添加
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def setup_working_directory():
    """设置工作目录为脚本所在目录"""
    # 获取脚本的绝对路径
    script_path = os.path.abspath(__file__)
    # 获取脚本所在目录
    script_dir = os.path.dirname(script_path)
    # 切换工作目录
    os.chdir(script_dir)
    print(f"工作目录已设置为: {os.getcwd()}")

def open_browser():
    """在新线程中打开浏览器"""
    webbrowser.open('http://127.0.0.1:8080/')

def signal_handler(sig, frame):
    """处理关闭信号"""
    print('\n正在关闭服务器...')
    # 清理临时文件
    cleanup_temp_files()
    sys.exit(0)

def cleanup_temp_files():
    """清理临时文件和目录"""
    try:
        # 清理上传目录
        upload_dir = Path('uploads')
        if upload_dir.exists():
            shutil.rmtree(str(upload_dir))
        
        # 清理临时文件
        output_dir = Path('output_images')
        if output_dir.exists():
            for item in output_dir.glob('temp_*'):
                if item.is_dir():
                    shutil.rmtree(str(item))
    except Exception as e:
        print(f"清理文件时发生错误: {str(e)}")

def process_pdf(pdf_path, output_dir, subimages_count=8):
    """处理PDF文件的后台任务"""
    global processing_status
    processing_status['subimages_count'] = subimages_count  # 保存子图数量设置
    temp_dir = None
    
    try:
        pdf_name = Path(pdf_path).stem
        # 保存当前PDF名称用于后续处理
        processing_status['current_pdf_name'] = pdf_name
        
        output_base_dir = Path(output_dir)
        output_base_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用安全的目录名 - 只保留字母数字和下划线
        safe_name = "".join(x if x.isalnum() else '_' for x in pdf_name)
        temp_dir = output_base_dir / f"temp_{safe_name}"
        temp_dir.mkdir(exist_ok=True)
        
        # 第一步：提取图片
        processing_status['current_step'] = 'extracting'
        processing_status['status'] = "正在从PDF提取图片..."
        processing_status['progress'] = 20
        processing_status['log'].append(f"开始处理PDF: {pdf_name}")
        
        num_images, image_files = extract_images_from_pdf(pdf_path, str(temp_dir))
        
        # 收集提取的图片信息
        extracted_images = []
        for img_name in image_files:
            img_path = temp_dir / img_name
            if img_path.exists():  # 确保文件存在
                # 使用os.path.join来确保正确的路径分隔符
                relative_path = os.path.join(f"temp_{safe_name}", img_name)
                extracted_images.append({
                    'path': relative_path,
                    'name': img_name
                })
        
        processing_status['extracted_images'] = extracted_images
        processing_status['log'].append(f"已提取 {num_images} 张图片")
        processing_status['progress'] = 50
        
        # 第二步：分割子图
        processing_status['current_step'] = 'splitting'
        processing_status['status'] = "正在处理提取出的图片..."
        processing_status['log'].append("开始分割子图...")
        
        final_output = output_base_dir / safe_name
        if final_output.exists():
            shutil.rmtree(str(final_output))
        final_output.mkdir(parents=True)
        
        # 处理每个提取出的图片
        split_results = {}
        total_split = 0
        
        for img_info in extracted_images:
            img_path = temp_dir / img_info['name']
            if img_path.exists():
                output_subdir = final_output / f"split_{img_info['name'].rsplit('.', 1)[0]}"
                output_subdir.mkdir(exist_ok=True)
                
                try:
                    # 处理单个图片，传入子图数量参数
                    from split_subimages import process_image
                    success = process_image(str(img_path), str(output_subdir), subimages_count)
                    
                    if success:
                        # 收集分割结果
                        subimages = []
                        for subimg in output_subdir.glob('*.jpg'):
                            relative_path = os.path.join(
                                safe_name,
                                f"split_{img_info['name'].rsplit('.', 1)[0]}",
                                subimg.name
                            )
                            subimages.append(relative_path)
                        
                        if subimages:
                            split_results[img_info['name']] = subimages
                            total_split += len(subimages)
                            processing_status['log'].append(
                                f"成功从 {img_info['name']} 提取了 {len(subimages)} 个子图"
                            )
                    else:
                        processing_status['log'].append(f"跳过 {img_info['name']} - 不符合分割要求")
                        
                except Exception as e:
                    processing_status['log'].append(f"处理 {img_info['name']} 时发生错误: {str(e)}")
                    print(f"处理 {img_info['name']} 时发生错误: {str(e)}")  # 控制台日志
        
        processing_status['split_results'] = split_results
        processing_status['log'].append(f"分割完成: 共提取 {total_split} 个子图")
        
        processing_status['progress'] = 100
        processing_status['status'] = "处理完成！"
        processing_status['log'].append("所有处理已完成！")
        processing_status['current_step'] = 'complete'
        
    except Exception as e:
        processing_status['log'].append(f"错误: {str(e)}")
        print(f"处理错误: {str(e)}")
    finally:
        processing_status['is_processing'] = False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传"""
    try:
        if 'pdf' not in request.files:
            return jsonify({'error': '没有文件被上传'}), 400
            
        file = request.files['pdf']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
            
        # 获取子图数量参数
        subimages_count = request.form.get('subimages_count', '8')
        try:
            subimages_count = int(subimages_count)
            if subimages_count <= 0:
                raise ValueError("子图数量必须大于0")
        except ValueError as e:
            return jsonify({'error': f'子图数量无效: {str(e)}'}), 400
            
        if file and allowed_file(file.filename):
            # 确保上传目录存在
            upload_dir = Path('uploads')
            upload_dir.mkdir(exist_ok=True)
            
            # 保存文件
            filename = secure_filename(file.filename)
            filepath = upload_dir / filename
            file.save(str(filepath))
            
            # 重置处理状态
            processing_status['is_processing'] = True
            processing_status['progress'] = 0
            processing_status['status'] = '等待开始...'
            processing_status['log'] = []
            processing_status['extracted_images'] = []
            processing_status['split_results'] = {}
            
            # 启动处理线程
            processing_thread = threading.Thread(
                target=process_pdf,
                args=(str(filepath), 'output_images', subimages_count)
            )
            processing_thread.daemon = True  # 设置为守护线程
            processing_thread.start()
            
            return jsonify({'message': '文件上传成功，开始处理'})
        else:
            return jsonify({'error': '不支持的文件类型'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def status():
    return jsonify(processing_status)

@app.route('/output/<path:filename>')
def download(filename):
    """处理图片文件请求"""
    try:
        # 解码URL编码的路径并替换斜杠
        decoded_path = urllib.parse.unquote(filename).replace('/', os.sep)
        # 构建完整的文件路径
        file_path = Path('output_images') / decoded_path
        
        print(f"尝试访问文件: {file_path}")  # 调试日志
        
        if not file_path.exists():
            print(f"文件不存在: {file_path}")
            return "File not found", 404
            
        # 获取文件所在目录和文件名
        directory = str(file_path.parent.absolute())
        basename = file_path.name
        
        print(f"发送文件: {directory} / {basename}")  # 调试日志
        
        # 使用send_from_directory发送文件
        return send_from_directory(
            directory,
            basename,
            as_attachment=False,
            mimetype='image/jpeg'
        )
    except Exception as e:
        print(f"提供文件时出错 {filename}: {str(e)}")
        return str(e), 404

@app.route('/download_zip/<mode>')
def download_zip(mode):
    """下载打包文件
    mode: 
        - chapter: 按章节打包(保持目录结构)
        - flat: 所有图片打包在同一目录
    """
    try:
        # 检查是否有处理结果
        if not processing_status.get('split_results'):
            return jsonify({'error': '没有可下载的文件'}), 404
            
        # 获取当前PDF名称
        pdf_name = processing_status.get('current_pdf_name', '')
        if not pdf_name:
            return jsonify({'error': '找不到PDF文件名'}), 404
            
        # 使用安全的文件名
        safe_name = "".join(x if x.isalnum() else '_' for x in pdf_name)
        output_base_dir = Path('output_images')
        final_output = output_base_dir / safe_name
        
        if not final_output.exists():
            return jsonify({'error': '处理结果不存在'}), 404
            
        # 创建临时ZIP文件
        zip_filename = f"{safe_name}_results_{mode}.zip"
        zip_path = output_base_dir / zip_filename
        
        # 确保输出目录存在
        output_base_dir.mkdir(exist_ok=True)
        
        # 创建ZIP文件
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            if mode == 'chapter':
                # 按章节打包，保持目录结构
                for root, _, files in os.walk(final_output):
                    for file in files:
                        file_path = Path(root) / file
                        # 使用相对路径作为ZIP中的路径
                        arcname = file_path.relative_to(final_output)
                        zipf.write(file_path, arcname)
            else:
                # 所有图片打包在同一目录
                for root, _, files in os.walk(final_output):
                    for file in files:
                        file_path = Path(root) / file
                        # 使用目录名和文件名组合作为新文件名
                        arcname = f"{Path(root).name}_{file}"
                        zipf.write(file_path, arcname)
        
        # 发送文件
        try:
            return send_file(
                zip_path,
                as_attachment=True,
                download_name=zip_filename,
                mimetype='application/zip'
            )
        finally:
            # 发送后删除临时ZIP文件
            try:
                if zip_path.exists():
                    zip_path.unlink()
            except Exception as e:
                print(f"删除临时ZIP文件时出错: {e}")
                
    except Exception as e:
        print(f"创建ZIP文件时出错: {e}")
        return jsonify({'error': str(e)}), 500

# 添加调试路由
@app.route('/debug/files')
def debug_files():
    """列出output_images目录中的所有文件"""
    try:
        output_dir = Path('output_images')
        files = []
        for file_path in output_dir.rglob('*'):
            if file_path.is_file():
                files.append(str(file_path.relative_to(output_dir)))
        return jsonify({
            'files': files,
            'status': processing_status
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 添加调试路由来检查分割结果
@app.route('/debug/split_results')
def debug_split_results():
    """查看分割结果的调试信息"""
    try:
        output_dir = Path('output_images')
        split_files = []
        
        # 收集所有分割后的图片文件
        for file_path in output_dir.rglob('split_*/*.jpg'):
            split_files.append(str(file_path.relative_to(output_dir)))
        
        return jsonify({
            'processing_status': processing_status,
            'split_files': split_files,
            'split_results': processing_status.get('split_results', {})
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 添加CORS支持
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

def main():
    """主函数"""
    # 设置工作目录
    setup_working_directory()
    
    # 创建必要的目录
    for dir_path in ['uploads', 'output_images']:
        path = Path(dir_path)
        path.mkdir(exist_ok=True)
        # 确保目录有正确的权限
        path.chmod(0o755)
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动浏览器
    threading.Timer(1.5, open_browser).start()
    
    # 启动服务器，允许外部访问
    app.run(
        host='0.0.0.0',  # 允许外部访问
        port=8080,       # 修改为8080端口
        debug=False,
        threaded=True    # 启用多线程支持
    )

if __name__ == '__main__':
    main() 