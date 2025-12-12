from flask import Blueprint, Flask, render_template, request, jsonify, redirect, url_for
from supabase import create_client
import os
from dotenv import load_dotenv
import random
import uuid
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io

# 환경변수 로드
load_dotenv()

app = Flask(__name__)

# Supabase 클라이언트
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_ANON_KEY')

if not supabase_url or not supabase_key:
    raise Exception("SUPABASE_URL 또는 SUPABASE_ANON_KEY가 .env에 없습니다!")

supabase = create_client(supabase_url, supabase_key)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 워터마크 함수 (맨 위로 이동)
def add_watermark(file_storage, text="ORACLE-BOOTCAMP", angle=20):
    img = Image.open(file_storage.stream).convert("RGBA")
    width, height = img.size

    watermark_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark_layer)

    try:
        font = ImageFont.truetype("arial.ttf", int(width * 0.025))
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    txt_img = Image.new("RGBA", (text_w + 20, text_h + 20), (0, 0, 0, 0))
    txt_draw = ImageDraw.Draw(txt_img)
    txt_draw.text((10, 10), text, font=font, fill=(255, 255, 255, 80))

    rotated_txt = txt_img.rotate(angle, expand=True, resample=Image.BICUBIC)

    rot_w, rot_h = rotated_txt.size
    x_gap = int(rot_w * 0.8)
    y_gap = int(rot_h * 1.6)

    for x in range(-rot_w, width + rot_w, x_gap):
        for y in range(-rot_h, height + rot_h, y_gap):
            watermark_layer.alpha_composite(rotated_txt, (x, y))

    watermarked = Image.alpha_composite(img, watermark_layer)

    output = io.BytesIO()
    ext = (file_storage.filename.rsplit(".", 1)[-1] or "png").lower()
    fmt = "PNG" if ext == "png" else "JPEG"
    watermarked.convert("RGB").save(output, format=fmt, quality=90)
    output.seek(0)
    return output

@app.route('/')
def index():
    try:
        response = supabase.table('members').select('*').execute()
        members = response.data or []
        return render_template('index.html', members=members, member_count=len(members))
    except Exception as e:
        print(f"Index error: {e}")
        return render_template('index.html', members=[], member_count=0)

@app.route('/quiz')
def quiz():
    try:
        response = supabase.table('members').select('*').execute()
        members = response.data or []
        
        if len(members) < 2:
            return render_template('quiz.html', members=[], error="퀴즈를 시작하려면 최소 2명 이상의 멤버 등록 필요!")
        
        random.shuffle(members)
        quiz_members = members[:10]
        return render_template('quiz.html', members=quiz_members)
    except Exception as e:
        print(f"Quiz error: {e}")
        return render_template('quiz.html', members=[], error="퀴즈 데이터를 불러올 수 없습니다.")

@app.route('/upload')
def upload_page():
    return render_template('upload.html')

# ★ 수정된 API 라우트 (Supabase 저장 추가)
@app.route('/api/upload_member', methods=['POST'])
def upload_member():
    try:
        if 'photo' not in request.files or 'name' not in request.form:
            return jsonify({'success': False, 'error': '이름과 사진이 필요합니다.'}), 400

        name = request.form['name'].strip()
        photo_file = request.files['photo']
        
        if not photo_file.filename or not allowed_file(photo_file.filename):
            return jsonify({'success': False, 'error': '올바른 사진 파일을 선택해주세요.'}), 400

        # 파일명 안전 처리
        filename = secure_filename(photo_file.filename)
        name_slug = secure_filename(name.replace(' ', '_'))
        ext = os.path.splitext(filename)[1] or '.jpg'
        unique_filename = f"{name_slug}_{int(datetime.now().timestamp())}{ext}"

        # ★ stream seek 제거 - 워터마크 함수에서 처리
        watermarked_bytes = add_watermark(photo_file, text="ORACLE-BOOTCAMP")

        # static/uploads 디렉토리 생성
        upload_dir = 'static/uploads'
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, unique_filename)

        # 파일 저장
        with open(file_path, 'wb') as f:
            f.write(watermarked_bytes.read())

        # Supabase에 저장 ★ 실제 저장 로직 추가
        member_data = {
            'name': name,
            'image_url': f'/static/uploads/{unique_filename}',
            'bio': request.form.get('bio', '').strip()
        }
        
        supabase.table('members').insert(member_data).execute()

        return jsonify({
            'success': True,
            'message': f'{name} 멤버 등록 완료!',
            'member': member_data
        })

    except Exception as e:
        print(f"업로드 에러: {str(e)}")
        return jsonify({'success': False, 'error': f'업로드 실패: {str(e)}'}), 500

# 나머지 라우트들은 동일...
@app.route('/api/quiz_submit', methods=['POST'])
def quiz_submit():
    try:
        data = request.get_json()
        user_name = data.get('user_name', '익명')
        score = int(data.get('score', 0))
        total = int(data.get('total', 0))

        score_data = {
            'user_name': user_name,
            'score': score,
            'total_questions': total,
            'accuracy': round((score/total)*100, 1) if total > 0 else 0,
            'played_at': datetime.utcnow().isoformat()
        }

        supabase.table('scores').insert(score_data).execute()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Quiz submit error: {e}")
        return jsonify({'error': '점수 저장 실패'}), 500

@app.route('/leaderboard')
def leaderboard():
    try:
        response = (supabase.table('scores')
                   .select('user_name, score, total_questions, accuracy, played_at')
                   .order('accuracy', desc=True)
                   .order('played_at', desc=True)
                   .limit(50)
                   .execute())
        scores = response.data or []
        return render_template('leaderboard.html', scores=scores)
    except Exception as e:
        print(f"Leaderboard error: {e}")
        return render_template('leaderboard.html', scores=[])

@app.route('/api/members')
def get_members():
    try:
        response = supabase.table('members').select('*').execute()
        return jsonify(response.data or [])
    except:
        return jsonify([])

if __name__ == '__main__':
    print("🚀 Oracle Bootcamp 2기 얼굴 퀴즈 - Supabase 연결!")
    
    try:
        response = supabase.table('members').select('count', count='exact').execute()
        print(f"✅ Supabase 연결 성공! (멤버 수: {response.count})")
    except Exception as e:
        print(f"⚠️ 테이블 없음: {e}")
        print("💡 Supabase Dashboard에서 SQL 실행하세요!")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
