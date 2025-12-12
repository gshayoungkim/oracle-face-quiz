from flask import Flask, render_template, request, jsonify, redirect, url_for
from supabase import create_client
import os
from dotenv import load_dotenv
import random
import uuid
from werkzeug.utils import secure_filename
from datetime import datetime

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

@app.route('/api/upload_member', methods=['POST'])
def upload_member():
    try:
        # 입력 검증
        name = request.form.get('name', '').strip()
        if not name:
            return jsonify({'error': '이름을 입력해주세요'}), 400
        
        file = request.files.get('photo')
        if not file or file.filename == '':
            return jsonify({'error': '사진을 선택해주세요'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'JPG, PNG, GIF만 가능합니다'}), 400
        
        bio = request.form.get('bio', '').strip()
        
        # 고유 파일명 생성
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"members/{uuid.uuid4().hex}{file_ext}"
        
        # Supabase Storage 업로드
        file.seek(0)
        supabase.storage.from_('face-images').upload(unique_filename, file.read())
        
        # Public URL 생성
        image_url = supabase.storage.from_('face-images').get_public_url(unique_filename)
        
        # DB 저장
        data = {
            'name': name,
            'image_url': image_url,
            'bio': bio or None
        }
        
        result = supabase.table('members').insert(data).execute()
        
        return jsonify({
            'success': True,
            'message': f'🎉 {name} 멤버 등록 완료!',
            'member': result.data[0]
        })
        
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'error': f'업로드 실패: {str(e)}'}), 500

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
            # 1) 문자열로 변환해서 넣기 (ISO8601)
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
    
    # 연결 테스트
    try:
        response = supabase.table('members').select('count', count='exact').execute()
        print(f"✅ Supabase 연결 성공! (멤버 수: {response.count})")
    except Exception as e:
        print(f"⚠️ 테이블 없음: {e}")
        print("💡 Supabase Dashboard에서 SQL 실행하세요!")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
