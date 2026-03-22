import gradio as gr
from pypdf import PdfReader, PdfWriter
from pydub import AudioSegment
from pydub.silence import split_on_silence
import os

# ==========================================
# 1. PDF 분할 (PDF Swordmaster)
# ==========================================
def parse_page_string(page_string, total_pages):
    pages = set()
    if not page_string: return []
    for part in page_string.split(','):
        part = part.strip()
        if '-' in part:
            start, end = map(int, part.split('-'))
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))
    return sorted([p for p in pages if 1 <= p <= total_pages])

def process_pdf(pdf_file, page_string):
    if pdf_file is None: return None, "PDF 파일을 업로드해주세요."
    try:
        reader = PdfReader(pdf_file.name)
        total_pages = len(reader.pages)
        target_pages = parse_page_string(page_string, total_pages)
        if not target_pages: return None, f"유효하지 않은 입력입니다. (총 {total_pages}페이지)"
            
        writer = PdfWriter()
        for p in target_pages: writer.add_page(reader.pages[p - 1])
            
        output_path = "extracted_output.pdf"
        with open(output_path, "wb") as f: writer.write(f)
        return output_path, f"성공적으로 추출되었습니다! (페이지: {target_pages})"
    except Exception as e:
        return None, f"오류 발생: {str(e)}"

# ==========================================
# 2. 오디오 분할 (Audio Swordmaster)
# ==========================================
def parse_time_to_ms(time_str):
    if not time_str or str(time_str).strip() in ["", "0"]: return 0
    time_str = str(time_str).strip()
    try:
        if ':' in time_str:
            parts = time_str.split(':')
            if len(parts) == 2: return int((int(parts[0]) * 60 + float(parts[1])) * 1000)
            elif len(parts) == 3: return int((int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])) * 1000)
        else: return int(float(time_str) * 1000)
    except Exception: raise ValueError(f"잘못된 시간 형식: {time_str}")
    return 0

def process_audio(audio_file, start_time_str, end_time_str, remove_silence):
    if audio_file is None: return None, "오디오 파일을 업로드해주세요."
    try:
        audio = AudioSegment.from_file(audio_file)
        start_ms = parse_time_to_ms(start_time_str)
        end_ms = len(audio) if not end_time_str or str(end_time_str).strip() in ["", "0"] else parse_time_to_ms(end_time_str)
        
        if start_ms >= end_ms and end_ms != len(audio): return None, "시작이 종료보다 클 수 없습니다."
        audio = audio[start_ms:end_ms]
            
        if remove_silence:
            chunks = split_on_silence(audio, min_silence_len=500, silence_thresh=-40)
            if chunks: audio = sum(chunks)
                
        output_path = "processed_audio.mp3"
        audio.export(output_path, format="mp3")
        return output_path, "성공적으로 처리되었습니다!"
    except Exception as e:
        return None, f"오류 발생: {str(e)}"

# ==========================================
# 3. 신규: PDF 병합 및 해제 (File Fusion)
# ==========================================
def process_fusion(pdf_files, password):
    if not pdf_files: return None, "합칠 PDF 파일들을 업로드해주세요."
    try:
        writer = PdfWriter()
        for pdf in pdf_files:
            reader = PdfReader(pdf.name)
            # 암호가 걸려있고, 사용자가 암호를 입력했다면 해제 시도
            if reader.is_encrypted:
                if password:
                    reader.decrypt(password)
                else:
                    return None, f"잠긴 파일이 포함되어 있습니다. 비밀번호를 입력해주세요."
            
            # 파일의 모든 페이지를 병합본에 추가
            for page in reader.pages:
                writer.add_page(page)
                
        output_path = "fusion_output.pdf"
        with open(output_path, "wb") as f:
            writer.write(f)
            
        return output_path, f"총 {len(pdf_files)}개의 파일이 성공적으로 병합(해제)되었습니다!"
    except Exception as e:
        return None, f"오류 발생: {str(e)}"

# ==========================================
# 4. Web UI 구성
# ==========================================
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# File Swordmaster")
    gr.Markdown("파일을 정밀하게 자르거나(Swordmaster), 여러 개를 하나로 합치고 잠금을 해제(Fusion)해 보세요!")
    
    with gr.Tab("PDF 분할"):
        with gr.Row():
            with gr.Column():
                pdf_input = gr.File(label="PDF 업로드", file_types=[".pdf"])
                pdf_pages = gr.Textbox(label="추출 페이지 (예: 1, 3, 5-10)")
                pdf_btn = gr.Button("자르기", variant="primary")
            with gr.Column():
                pdf_out_file = gr.File(label="결과물")
                pdf_out_msg = gr.Textbox(label="상태")
        pdf_btn.click(process_pdf, inputs=[pdf_input, pdf_pages], outputs=[pdf_out_file, pdf_out_msg])
        
    with gr.Tab("오디오 분할"):
        with gr.Row():
            with gr.Column():
                audio_input = gr.Audio(label="오디오 업로드", type="filepath")
                audio_start = gr.Textbox(label="시작 시간 (초 또는 분:초)", value="0")
                audio_end = gr.Textbox(label="종료 시간 (0이면 끝까지)", value="0")
                audio_sil = gr.Checkbox(label="무음 구간 제거", value=False)
                audio_btn = gr.Button("자르기", variant="primary")
            with gr.Column():
                audio_out_file = gr.File(label="결과물")
                audio_out_msg = gr.Textbox(label="상태")
        audio_btn.click(process_audio, inputs=[audio_input, audio_start, audio_end, audio_sil], outputs=[audio_out_file, audio_out_msg])

    with gr.Tab("PDF 병합"):
        gr.Markdown("여러 PDF를 순서대로 하나로 합치거나, 암호가 걸린 PDF의 비밀번호를 입력해 잠금을 해제한 복사본을 만듭니다.")
        with gr.Row():
            with gr.Column():
                # 여러 개의 파일을 올릴 수 있도록 file_count="multiple" 설정
                fusion_input = gr.File(label="여러 PDF 파일 업로드 (순서대로 병합됨)", file_types=[".pdf"], file_count="multiple")
                fusion_pw = gr.Textbox(label="비밀번호 (잠긴 파일이 있을 경우 입력)", type="password")
                fusion_btn = gr.Button("합치기 / 잠금해제", variant="primary")
            with gr.Column():
                fusion_out_file = gr.File(label="결과물")
                fusion_out_msg = gr.Textbox(label="상태")
        fusion_btn.click(process_fusion, inputs=[fusion_input, fusion_pw], outputs=[fusion_out_file, fusion_out_msg])

demo.launch()
