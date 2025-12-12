# test_watermark.py
from PIL import Image, ImageDraw, ImageFont
from werkzeug.datastructures import FileStorage
import io
import os

INPUT_PATH = "test_input"  # 확장자 없이 이름만 써도 되고,
# 또는 "test_input.jpg", "test_input.png" 처럼 통째로 지정해도 됨

def add_watermark(file_storage, text="ORACLE-BOOTCAMP", angle=20):
    img = Image.open(file_storage.stream).convert("RGBA")
    width, height = img.size

    watermark_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark_layer)

    # ★ 원래처럼 try-except 유지 (가장 안전)
    try:
        font = ImageFont.truetype("arial.ttf", int(width * 0.025))
    except:
        font = ImageFont.load_default()

    # 텍스트 크기 계산 (폰트 로딩 후)
    bbox = draw.textbbox((0, 0), text, font=font)
    # ... 나머지 동일

    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # 회전된 텍스트 이미지 생성 (한 번만)
    txt_img = Image.new("RGBA", (text_w + 20, text_h + 20), (0, 0, 0, 0))
    txt_draw = ImageDraw.Draw(txt_img)
    txt_draw.text((10, 10), text, font=font, fill=(255, 255, 255, 80))

    # 텍스트 회전 (20도, 반시계방향)
    rotated_txt = txt_img.rotate(angle, expand=True, resample=Image.BICUBIC)

    # 스트라이프 간격 (회전 후 크기 고려)
    rot_w, rot_h = rotated_txt.size
    x_gap = int(rot_w * 0.8)  # 가로: 20% 줄임
    y_gap = int(rot_h * 1.6)  # 세로: 36% 줄임

    # 반복 합성
    for x in range(-rot_w, width + rot_w, x_gap):
        for y in range(-rot_h, height + rot_h, y_gap):
            pos = (x, y)
            watermark_layer.alpha_composite(rotated_txt, pos)

    # 최종 합성
    watermarked = Image.alpha_composite(img, watermark_layer)

    output = io.BytesIO()
    ext = (file_storage.filename.rsplit(".", 1)[-1] or "png").lower()
    fmt = "PNG" if ext == "png" else "JPEG"
    watermarked.convert("RGB").save(output, format=fmt, quality=90)
    output.seek(0)
    return output


if __name__ == "__main__":
    # 1) jpg 또는 png 자동 탐색
    candidate_paths = []
    if "." in INPUT_PATH:
        candidate_paths = [INPUT_PATH]
    else:
        candidate_paths = [INPUT_PATH + ".jpg", INPUT_PATH + ".png"]

    src_path = None
    for p in candidate_paths:
        if os.path.exists(p):
            src_path = p
            break

    if not src_path:
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {candidate_paths}")

    with open(src_path, "rb") as f:
        fs = FileStorage(stream=io.BytesIO(f.read()), filename=os.path.basename(src_path))

    wm_bytes = add_watermark(fs, text="ORACLE-BOOTCAMP")

    # 3) 원본과 같은 확장자로 저장
    base, ext = os.path.splitext(src_path)
    out_path = base + "_watermarked" + ext

    with open(out_path, "wb") as out:
        out.write(wm_bytes.read())

    print(f"완료: {out_path} 파일에서 워터마크를 확인해보세요.")
