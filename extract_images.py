import fitz
import os
from pathlib import Path
import argparse
import glob

def extract_images_from_pdf(pdf_path, output_dir):
    """
    从PDF文件中提取所有图片并保存到指定目录
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录路径
        
    Returns:
        tuple: (图片数量, 提取的图片路径列表)
    """
    # 获取PDF文件名（不含扩展名）作为子目录名
    pdf_name = Path(pdf_path).stem
    
    # 打开PDF文件
    pdf_document = fitz.open(pdf_path)
    
    # 用于记录提取的图片数量和路径
    image_count = 0
    extracted_images = []
    
    # 遍历每一页
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        
        # 获取页面上的图片
        images = page.get_images()
        
        # 遍历该页的所有图片
        for img_index, img in enumerate(images):
            # 获取图片信息
            xref = img[0]
            base_image = pdf_document.extract_image(xref)
            
            if base_image:
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # 构建输出文件名
                image_filename = f"page{page_num + 1}_img{img_index + 1}.{image_ext}"
                image_path = Path(output_dir) / image_filename
                
                # 保存图片
                with open(image_path, "wb") as image_file:
                    image_file.write(image_bytes)
                    image_count += 1
                    extracted_images.append(image_filename)  # 只保存文件名
    
    pdf_document.close()
    return image_count, extracted_images

def process_pdf_directory(pdf_dir, output_dir):
    """
    处理指定目录下的所有PDF文件
    
    Args:
        pdf_dir: PDF文件所在目录
        output_dir: 输出目录路径
    """
    # 确保输出目录存在
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 获取所有PDF文件
    pdf_files = glob.glob(os.path.join(pdf_dir, "*.pdf"))
    
    if not pdf_files:
        print(f"在目录 {pdf_dir} 中没有找到PDF文件")
        return
    
    total_pdfs = len(pdf_files)
    total_images = 0
    
    # 处理每个PDF文件
    for index, pdf_path in enumerate(pdf_files, 1):
        try:
            images_count, pdf_name = extract_images_from_pdf(pdf_path, output_dir)
            total_images += images_count
            print(f"[{index}/{total_pdfs}] 处理 {pdf_name}.pdf: 提取了 {images_count} 张图片")
        except Exception as e:
            print(f"处理 {pdf_path} 时发生错误: {str(e)}")
    
    return total_pdfs, total_images

def main():
    parser = argparse.ArgumentParser(description='从PDF文件中提取图片')
    parser.add_argument('pdf_path', help='PDF文件或目录路径')
    parser.add_argument('--output', '-o', default='output_images',
                      help='输出目录路径 (默认: output_images)')
    
    args = parser.parse_args()
    pdf_path = args.pdf_path
    
    try:
        if os.path.isdir(pdf_path):
            # 处理整个目录
            total_pdfs, total_images = process_pdf_directory(pdf_path, args.output)
            print(f"\n总计处理了 {total_pdfs} 个PDF文件，提取了 {total_images} 张图片")
            print(f"所有图片已保存到目录: {args.output}")
        else:
            # 处理单个PDF文件
            num_images, pdf_name = extract_images_from_pdf(pdf_path, args.output)
            print(f"成功从 {pdf_name}.pdf 中提取了 {num_images} 张图片到目录: {args.output}")
    except Exception as e:
        print(f"发生错误: {str(e)}")

if __name__ == "__main__":
    main() 