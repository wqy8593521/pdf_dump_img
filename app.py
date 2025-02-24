import streamlit as st
import os
from pathlib import Path
import tempfile
from extract_images import extract_images_from_pdf
from split_subimages import process_image

def main():
    st.set_page_config(page_title="PDF图片提取工具", layout="wide")
    st.title("PDF图片提取工具")
    
    # 侧边栏配置
    with st.sidebar:
        st.header("配置")
        subimages_count = st.number_input(
            "子图数量",
            min_value=1,
            max_value=100,
            value=8,
            help="设置每张图片要分割的子图数量"
        )
    
    # 文件上传
    uploaded_file = st.file_uploader("选择PDF文件", type=['pdf'])
    
    if uploaded_file:
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 保存上传的PDF
            pdf_path = Path(temp_dir) / "input.pdf"
            with open(pdf_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            
            # 创建输出目录
            output_dir = Path(temp_dir) / "output"
            output_dir.mkdir(exist_ok=True)
            
            # 处理进度条
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 第一步：提取图片
            status_text.text("正在从PDF提取图片...")
            progress_bar.progress(20)
            
            num_images, image_files = extract_images_from_pdf(str(pdf_path), str(output_dir))
            
            if num_images > 0:
                status_text.text(f"已提取 {num_images} 张图片")
                progress_bar.progress(50)
                
                # 显示提取的图片
                st.subheader("提取的图片")
                cols = st.columns(3)
                for idx, img_name in enumerate(image_files):
                    img_path = output_dir / img_name
                    if img_path.exists():
                        cols[idx % 3].image(str(img_path), caption=img_name)
                
                # 第二步：分割子图
                status_text.text("正在处理提取出的图片...")
                progress_bar.progress(75)
                
                # 创建分割结果目录
                split_dir = Path(temp_dir) / "split"
                split_dir.mkdir(exist_ok=True)
                
                # 处理每个提取的图片
                st.subheader("分割结果")
                for img_name in image_files:
                    img_path = output_dir / img_name
                    if img_path.exists():
                        output_subdir = split_dir / f"split_{img_name.rsplit('.', 1)[0]}"
                        output_subdir.mkdir(exist_ok=True)
                        
                        success = process_image(str(img_path), str(output_subdir), subimages_count)
                        
                        if success:
                            # 显示分割结果
                            st.write(f"原图: {img_name}")
                            subcols = st.columns(4)
                            for idx, subimg in enumerate(sorted(output_subdir.glob('*.jpg'))):
                                subcols[idx % 4].image(str(subimg), caption=f"子图_{idx+1}")
                
                # 完成
                progress_bar.progress(100)
                status_text.text("处理完成！")
                
                # 打包下载
                with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_zip:
                    import zipfile
                    with zipfile.ZipFile(tmp_zip.name, 'w') as zipf:
                        for root, _, files in os.walk(split_dir):
                            for file in files:
                                file_path = Path(root) / file
                                arcname = file_path.relative_to(split_dir)
                                zipf.write(file_path, arcname)
                    
                    with open(tmp_zip.name, 'rb') as f:
                        st.download_button(
                            label="下载所有结果",
                            data=f.read(),
                            file_name="split_results.zip",
                            mime="application/zip"
                        )
            else:
                st.error("未从PDF中提取到图片")

if __name__ == "__main__":
    main() 