import streamlit as st
import pandas as pd
import pytesseract
import cv2
import numpy as np
import re
from pdf2image import convert_from_bytes
from PIL import Image
import io

# 1. 이미지 전처리 (흑백 및 대비 최적화)
def preprocess_pil_image(pil_img):
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    return gray

# 2. 텍스트 정규식 추출
def extract_info_from_text(text):
    data = {"날짜": "", "사업자 이름": "", "사업자 등록번호": "", "결제항목": "", "결제금액": ""}
    lines = text.split('\n')
    lines = [line.strip() for line in lines if line.strip()]

    date_pattern = re.compile(r'(20\d{2}[-./년]\s*\d{1,2}[-./월]\s*\d{1,2}일?)')
    biz_num_pattern = re.compile(r'(\d{3}\s*-\s*\d{2}\s*-\s*\d{5})')
    amount_pattern = re.compile(r'(합\s*계|결\s*제\s*금\s*액|받\s*을\s*금\s*액|승\s*인\s*금\s*액|총\s*액)[\s:;]*([\d,]+)\s*원?')

    for i, line in enumerate(lines):
        if "상호" in line or "가맹점명" in line:
            biz_name = line.replace("상호", "").replace("가맹점명", "").replace(":", "").strip()
            if biz_name: data["사업자 이름"] = biz_name
        
        if not data["사업자 이름"] and i < 3 and re.search(r'[가-힣]', line):
            data["사업자 이름"] = line

        if not data["날짜"]:
            date_match = date_pattern.search(line)
            if date_match: data["날짜"] = date_match.group(1)

        if not data["사업자 등록번호"]:
            biz_num_match = biz_num_pattern.search(line)
            if biz_num_match: data["사업자 등록번호"] = biz_num_match.group(1)

        amount_match = amount_pattern.search(line)
        if amount_match:
            data["결제금액"] = amount_match.group(2)

    data["결제항목"] = "일반결제 (OCR수동확인)"
    return data

# 3. 웹사이트 UI 및 메인 로직 구성
st.set_page_config(page_title="영수증 자동 인식기", page_icon="🧾", layout="centered")
st.title("🧾 무료 로컬 영수증 자동 인식기")
st.markdown("API 비용 없이 100% 무료로 동작합니다. 파일을 드래그 앤 드롭 하거나, **박스 안을 클릭한 뒤 Ctrl+V**로 캡처 이미지를 붙여넣으세요.")

# Streamlit은 파일 업로더에서 직접 Ctrl+V 붙여넣기를 지원합니다!
uploaded_files = st.file_uploader("📂 영수증 파일 업로드 (PDF, 이미지 여러 장 가능)", type=['pdf', 'png', 'jpg', 'jpeg'], accept_multiple_files=True)

if st.button("정보 추출 시작", type="primary"):
    if not uploaded_files:
        st.warning("파일을 업로드하거나 이미지를 붙여넣어 주세요.")
    else:
        with st.spinner("영수증을 분석 중입니다... 잠시만 기다려주세요 ⏳"):
            all_extracted_data = []

            for file in uploaded_files:
                file_name = file.name
                ext = file_name.split('.')[-1].lower()
                extracted_texts = []

                if ext == 'pdf':
                    try:
                        # Streamlit 특성에 맞게 메모리에서 직접 PDF 변환
                        pages = convert_from_bytes(file.read())
                        for page in pages:
                            processed_img = preprocess_pil_image(page)
                            text = pytesseract.image_to_string(processed_img, lang='kor+eng')
                            extracted_texts.append(text)
                    except Exception as e:
                        st.error(f"PDF 변환 에러 ({file_name}): {e}")
                else:
                    try:
                        img = Image.open(file)
                        processed_img = preprocess_pil_image(img)
                        text = pytesseract.image_to_string(processed_img, lang='kor+eng')
                        extracted_texts.append(text)
                    except Exception as e:
                        st.error(f"이미지 변환 에러 ({file_name}): {e}")

                for text in extracted_texts:
                    if text.strip():
                        info = extract_info_from_text(text)
                        info["파일이름"] = file_name
                        all_extracted_data.append(info)

            if not all_extracted_data:
                st.error("추출된 텍스트가 없습니다. 이미지가 선명한지 다시 확인해주세요.")
            else:
                df = pd.DataFrame(all_extracted_data)
                df = df[["파일이름", "날짜", "사업자 이름", "사업자 등록번호", "결제항목", "결제금액"]]
                
                st.success(f"🎉 성공적으로 {len(all_extracted_data)}개의 데이터 추출을 완료했습니다!")
                st.dataframe(df) # 화면에 추출 결과 표 보여주기

                # 엑셀 파일 생성 (메모리에서 바로 생성하여 다운로드 속도 최적화)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='영수증추출')
                excel_data = output.getvalue()

                st.download_button(
                    label="⬇️ 추출된 엑셀 파일 다운로드",
                    data=excel_data,
                    file_name="영수증_무료추출결과.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
