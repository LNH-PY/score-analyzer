import os
import json
import sqlite3
import base64
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
CORS(app)

DB_PATH = os.environ.get('DB_PATH', 'data/scores.db')

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            score TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS wrong_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            image_data TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
        );
    ''')
    conn.commit()
    conn.close()

# 前端页面
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# 获取所有考试数据
@app.route('/api/exams', methods=['GET'])
def get_exams():
    conn = get_db()
    exams = conn.execute('SELECT * FROM exams ORDER BY sort_order').fetchall()
    result = []
    for exam in exams:
        subjects = conn.execute(
            'SELECT * FROM subjects WHERE exam_id = ? ORDER BY sort_order',
            (exam['id'],)
        ).fetchall()
        subs = []
        for sub in subjects:
            images = conn.execute(
                'SELECT * FROM wrong_images WHERE subject_id = ? ORDER BY sort_order',
                (sub['id'],)
            ).fetchall()
            subs.append({
                'id': sub['id'],
                'label': sub['label'],
                'score': sub['score'],
                'wrongImages': [img['image_data'] for img in images]
            })
        result.append({
            'id': exam['id'],
            'name': exam['name'],
            'subjects': subs
        })
    conn.close()
    return jsonify(result)

# 保存所有考试数据（全量覆盖）
@app.route('/api/exams', methods=['POST'])
def save_exams():
    data = request.json
    if not data or not isinstance(data, list):
        return jsonify({'error': '无效的数据格式'}), 400

    conn = get_db()
    # 清空旧数据
    conn.execute('DELETE FROM wrong_images')
    conn.execute('DELETE FROM subjects')
    conn.execute('DELETE FROM exams')

    for ei, exam in enumerate(data):
        cursor = conn.execute(
            'INSERT INTO exams (name, sort_order) VALUES (?, ?)',
            (exam['name'], ei)
        )
        exam_id = cursor.lastrowid

        for si, sub in enumerate(exam.get('subjects', [])):
            cursor = conn.execute(
                'INSERT INTO subjects (exam_id, label, score, sort_order) VALUES (?, ?, ?, ?)',
                (exam_id, sub['label'], sub.get('score', ''), si)
            )
            sub_id = cursor.lastrowid

            for ii, img_data in enumerate(sub.get('wrongImages', [])):
                conn.execute(
                    'INSERT INTO wrong_images (subject_id, image_data, sort_order) VALUES (?, ?, ?)',
                    (sub_id, img_data, ii)
                )

    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': '数据已保存'})

# 清空所有数据
@app.route('/api/exams', methods=['DELETE'])
def clear_exams():
    conn = get_db()
    conn.execute('DELETE FROM wrong_images')
    conn.execute('DELETE FROM subjects')
    conn.execute('DELETE FROM exams')
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
