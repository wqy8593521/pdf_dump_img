import os
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import math

def is_similar_size(regions):
    """
    检查所有区域是否大小相近
    """
    if len(regions) != 8:
        return False
        
    # 获取所有区域的宽度和高度
    sizes = [(r[2]-r[0], r[3]-r[1]) for r in regions]
    widths, heights = zip(*sizes)
    
    # 计算平均值
    avg_width = sum(widths) / len(widths)
    avg_height = sum(heights) / len(heights)
    
    # 检查每个区域的尺寸是否在平均值的±10%范围内
    for w, h in sizes:
        if abs(w - avg_width) / avg_width > 0.1 or abs(h - avg_height) / avg_height > 0.1:
            return False
    return True

def extract_subimages(image_path, output_dir, subimages_count=8):
    """
    提取图片中的子图
    
    Args:
        image_path: 输入图片路径
        output_dir: 输出目录
        subimages_count: 要分割的子图数量
    """
    # 读取图片
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"无法读取图片: {image_path}")
        return False
        
    # 转换为灰度图
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 二值化
    _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    
    # 查找轮廓
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 获取有效的子图区域
    regions = []
    for contour in contours:
        # 获取边界框
        x, y, w, h = cv2.boundingRect(contour)
        # 过滤掉太小的区域
        if w > 50 and h > 50:  # 可以根据实际情况调整阈值
            regions.append((x, y, x+w, y+h))
    
    # 按照从上到下，从左到右排序
    regions.sort(key=lambda r: (r[1], r[0]))
    
    # 检查是否有足够的子图
    if len(regions) < subimages_count:
        print(f"图片 {image_path.name} 没有足够的子图区域，需要 {subimages_count} 个，实际只有 {len(regions)} 个")
        return False
    
    # 创建输出目录
    output_subdir = Path(output_dir) / f"图{Path(image_path).stem}"
    output_subdir.mkdir(parents=True, exist_ok=True)
    
    # 提取并保存指定数量的子图
    for i, (x1, y1, x2, y2) in enumerate(regions[:subimages_count], 1):
        subimg = img[y1:y2, x1:x2]
        output_path = output_subdir / f"子图_{i}.jpg"
        cv2.imwrite(str(output_path), subimg)
    
    print(f"成功从 {image_path.name} 提取了 {subimages_count} 个子图")
    return True

def process_directory(input_dir, output_dir, subimages_count=8):
    """
    处理目录下的所有图片
    """
    input_path = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 获取所有图片文件
    image_files = list(input_path.glob("*.jpg")) + list(input_path.glob("*.jpeg")) + list(input_path.glob("*.png"))
    total_processed = 0
    total_success = 0
    print(image_files)
    
    for img_path in image_files:
        try:
            if extract_subimages(img_path, output_dir, subimages_count):
                total_success += 1
            total_processed += 1
        except Exception as e:
            print(f"处理 {img_path.name} 时发生错误: {str(e)}")
    
    print(f"\n处理完成: 共处理 {total_processed} 张图片，成功提取 {total_success} 张{subimages_count}子图")

def check_8_subimages(img):
    """检查图片是否可以分割为8个子图"""
    try:
        height, width = img.shape[:2]
        
        # 检查是否可以均匀分割为8个子图
        if height % 4 != 0 or width % 2 != 0:
            return False
            
        # 检查每个子图的最小尺寸
        sub_height = height // 4
        sub_width = width // 2
        if sub_height < 100 or sub_width < 100:  # 调整最小尺寸要求
            return False
            
        return True
    except Exception as e:
        print(f"检查8子图时发生错误: {str(e)}")
        return False

def remove_white_borders(img, threshold=250):
    """移除图片白边
    
    Args:
        img: OpenCV图片对象
        threshold: 白色阈值(0-255)
        
    Returns:
        裁剪后的图片
    """
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
        
    # 获取非白色区域的边界
    mask = gray < threshold
    coords = np.argwhere(mask)
    
    if len(coords) == 0:  # 如果图片全白
        return img
        
    y_min, x_min = coords.min(axis=0)
    y_max, x_max = coords.max(axis=0)
    
    # 裁剪图片
    return img[y_min:y_max+1, x_min:x_max+1]

def process_image(input_path, output_dir, subimages_count=8):
    """处理单个图片文件"""
    try:
        # 读取图片
        img = cv2.imread(input_path)
        if img is None:
            print(f"无法读取图片: {input_path}")
            return False
            
        # 获取图片尺寸
        height, width = img.shape[:2]
        
        # 根据子图数量计算行列数
        num_cols = int(math.sqrt(subimages_count))
        num_rows = (subimages_count + num_cols - 1) // num_cols
        
        # 检查是否可以均匀分割
        if height % num_rows != 0 or width % num_cols != 0:
            print(f"图片 {os.path.basename(input_path)} 不能均匀分割为 {subimages_count} 个子图")
            return False
        
        # 计算子图尺寸
        sub_width = width // num_cols
        sub_height = height // num_rows
        
        # 存储所有子图
        subimages = []
        
        # 提取子图
        count = 0
        for row in range(num_rows):
            for col in range(num_cols):
                if count >= subimages_count:
                    break
                    
                y1 = row * sub_height
                y2 = (row + 1) * sub_height
                x1 = col * sub_width
                x2 = (col + 1) * sub_width
                
                sub_img = img[y1:y2, x1:x2]
                # 移除白边
                sub_img = remove_white_borders(sub_img)
                subimages.append(sub_img)
                count += 1
        
        # 找出所有子图中的最大尺寸
        max_height = max(img.shape[0] for img in subimages)
        max_width = max(img.shape[1] for img in subimages)
        
        # 调整所有子图到相同尺寸并保存
        for i, sub_img in enumerate(subimages, 1):
            # 创建白色背景
            final_img = np.full((max_height, max_width, 3), 255, dtype=np.uint8)
            
            # 计算居中位置
            y_offset = (max_height - sub_img.shape[0]) // 2
            x_offset = (max_width - sub_img.shape[1]) // 2
            
            # 将子图放在中心位置
            final_img[
                y_offset:y_offset + sub_img.shape[0],
                x_offset:x_offset + sub_img.shape[1]
            ] = sub_img
            
            # 保存子图
            output_path = os.path.join(output_dir, f'subimg_{i}.jpg')
            cv2.imwrite(output_path, final_img)
        
        print(f"成功从 {os.path.basename(input_path)} 提取了{count}个子图")
        return True
        
    except Exception as e:
        print(f"处理图片时发生错误: {str(e)}")
        return False

if __name__ == "__main__":
    # 直接在这里指定输入和输出目录
    input_directory = "pdf_dump_img/output_folder/第2章 内蒙古胜利煤田34-6孔6、11号煤层"  # 这里放提取出的图片的目录
    output_directory = "final_subimages"  # 这里是分割后的子图的保存目录
    
    process_directory(input_directory, output_directory) 