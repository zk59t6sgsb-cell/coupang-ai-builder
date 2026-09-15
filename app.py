import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
import io
import textwrap

# 1. 스트림릿 페이지 설정
st.set_page_config(page_title="쿠팡 상세페이지 & 마진 분석기", layout="centered")

st.title("🛍️ 초간단 상세페이지 & 마진 분석 생성기")
st.markdown("제미나이가 후킹 세일즈 카피를 쓰고, 회계학적 마진율을 계산하여 쿠팡 규격(가로 860px)의 긴 이미지로 만들어줍니다.")

# 2. 사이드바 - API 키 및 안내
with st.sidebar:
    st.header("⚙️ 환경 설정")
    api_key = st.text_input("Gemini API Key를 입력하세요", type="password")
    st.info("💡 팁: 코드와 같은 폴더에 'font.ttf' 이름으로 한글 폰트(나눔고딕 등)를 꼭 넣어주세요!")

# 3. 사용자 입력창
col1, col2 = st.columns(2)
with col1:
    product_image = st.file_uploader("제품 사진 업로드 (JPG, PNG)", type=["jpg", "jpeg", "png"])
    product_name = st.text_input("제품 이름")
    features = st.text_area("특징 3가지 (줄바꿈으로 구분)", placeholder="1. 강력한 흡입력\n2. 깃털처럼 가벼운 무게\n3. 대용량 배터리")

with col2:
    price = st.number_input("판매가격 (원)", min_value=0, step=1000)
    cost = st.number_input("원가 (원)", min_value=0, step=1000)

# 4. 동작 실행
if st.button("상세페이지 생성", type="primary"):
    if not api_key:
        st.error("좌측 사이드바에서 Gemini API Key를 입력해주세요.")
        st.stop()
    if not product_image or not product_name or not features or price == 0:
        st.error("모든 텍스트 정보와 가격을 입력하고 사진을 업로드해주세요.")
        st.stop()

    with st.spinner("마진 계산 및 제미나이 카피 작성 중..."):
        
        # --- [1] 회계학적 마진 계산 로직 ---
        commission_rate = 0.11 # 쿠팡 수수료 약 11%
        commission_fee = int(price * commission_rate)
        net_receipt = price - commission_fee # 실수령액 = 판매가 - 수수료
        margin = net_receipt - cost          # 마진 = 실수령액 - 원가
        margin_rate = (margin / price) * 100 if price > 0 else 0

        # --- [2] Gemini API 호출 ---
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        당신은 쿠팡에서 월 매출 1억을 내는 탑셀러의 전문 카피라이터입니다.
        아래 제품 정보를 바탕으로 상세페이지에 들어갈 텍스트를 작성해주세요.

        제품명: {product_name}
        특징: {features}

        다음 양식에 맞춰서 간결하고 후킹하게 작성해주세요:
        [후킹 헤드라인] (가장 매력적인 1줄)
        [핵심 특징 요약] (3줄 이내)
        [구매자 Q&A] (가장 많이 묻는 가상의 질문과 명쾌한 답변 2개)
        """
        
        try:
            response = model.generate_content(prompt)
            copy_text = response.text
        except Exception as e:
            st.error(f"Gemini API 호출 중 오류가 발생했습니다: {e}")
            st.stop()

        # --- [3] Pillow 이미지 캔버스 생성 ---
        try:
            # 폰트 로드 (font.ttf 필수)
            try:
                body_font = ImageFont.truetype("font.ttf", 26)
                bold_font = ImageFont.truetype("font.ttf", 30)
            except IOError:
                st.warning("⚠️ `font.ttf` 파일을 찾을 수 없어 기본 폰트를 사용합니다. (한글이 깨질 수 있습니다)")
                body_font = ImageFont.load_default()
                bold_font = ImageFont.load_default()

            # 원본 이미지 로드 및 리사이징 (쿠팡 규격 가로 860px)
            img = Image.open(product_image)
            target_width = 860
            width_ratio = (target_width / float(img.size[0]))
            target_height = int((float(img.size[1]) * float(width_ratio)))
            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

            # 한글 텍스트 자동 줄바꿈 함수 (Pillow는 자동 줄바꿈을 지원하지 않으므로 직접 구현)
            def get_wrapped_text(text, width=42):
                lines = []
                for paragraph in text.split('\n'):
                    if paragraph.strip() == "":
                        lines.append("")
                        continue
                    wrapped = textwrap.wrap(paragraph, width=width)
                    lines.extend(wrapped)
                return lines

            # 제미나이 텍스트 라인 변환
            copy_lines = get_wrapped_text(copy_text)
            
            # 마진 분석표 텍스트 생성
            margin_text = (
                "[ 📊 회계학적 마진 분석표 ]\n"
                f"- 판매가: {price:,} 원\n"
                f"- 원가: {cost:,} 원\n"
                f"- 쿠팡 수수료(11%): -{commission_fee:,} 원\n"
                f"----------------------------------------\n"
                f"▶ 실수령액: {net_receipt:,} 원\n"
                f"▶ 최종 이익(마진): {margin:,} 원\n"
                f"▶ 마진율: {margin_rate:.1f} %"
            )
            margin_lines = margin_text.split('\n')

            # 전체 캔버스 높이 동적 계산
            line_height = 40
            text_area_height = (len(copy_lines) + len(margin_lines) + 8) * line_height
            canvas_height = target_height + text_area_height + 50

            # 흰색 배경의 새 캔버스 생성 및 사진 붙여넣기
            canvas = Image.new('RGB', (target_width, canvas_height), 'white')
            canvas.paste(img, (0, 0))
            draw = ImageDraw.Draw(canvas)
            
            current_y = target_height + 40
            
            # 카피라이팅 텍스트 그리기
            for line in copy_lines:
                # 헤드라인이나 Q&A 제목 등은 조금 더 굵게(색상 다르게) 처리하는 효과
                if "[" in line and "]" in line:
                    draw.text((40, current_y), line, font=bold_font, fill='#E52528') # 쿠팡 레드
                else:
                    draw.text((40, current_y), line, font=body_font, fill='black')
                current_y += line_height
                
            current_y += 60 # 섹션 간 여백

            # 마진 분석 박스 그리기 (파란색 테두리 박스)
            box_start_y = current_y - 20
            box_end_y = current_y + (len(margin_lines) * line_height) + 20
            draw.rectangle([30, box_start_y, target_width-30, box_end_y], outline="#0052FF", width=3, fill="#F0F8FF")
            
            for line in margin_lines:
                # 합계 부분 강조
                if "▶" in line:
                    draw.text((50, current_y), line, font=bold_font, fill='#0052FF')
                else:
                    draw.text((50, current_y), line, font=body_font, fill='#333333')
                current_y += line_height

            # 최종 이미지를 바이트 배열로 변환
            img_byte_arr = io.BytesIO()
            canvas.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()

            st.success("🎉 상세페이지 캔버스 생성이 완료되었습니다!")
            
            # --- [4] 화면 출력 및 다운로드 ---
            st.image(canvas, caption="완성된 상세페이지 뷰어", use_container_width=True)
            
            st.download_button(
                label="📥 상세페이지 이미지 다운로드 (.png)",
                data=img_byte_arr,
                file_name=f"상품명_{product_name}_상세페이지.png",
                mime="image/png"
            )

        except Exception as e:
            st.error(f"이미지 생성 중 오류가 발생했습니다: {e}")
