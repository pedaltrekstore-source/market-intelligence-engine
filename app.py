import os, json, uuid, threading
from datetime import datetime
from flask import Flask, send_file, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///mie.db').replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'mie-secret-2024')

db = SQLAlchemy(app)

class Scan(db.Model):
    __tablename__ = 'scans'
    id           = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name         = db.Column(db.String(255), nullable=False)
    niche        = db.Column(db.String(255), nullable=False)
    country      = db.Column(db.String(10), default='BR')
    language     = db.Column(db.String(10), default='pt')
    status       = db.Column(db.String(20), default='pending')
    progress     = db.Column(db.Integer, default=0)
    message      = db.Column(db.String(500), default='')
    result_json  = db.Column(db.Text, default='{}')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'niche': self.niche,
            'country': self.country, 'language': self.language,
            'status': self.status, 'progress': self.progress,
            'message': self.message,
            'result': json.loads(self.result_json or '{}'),
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

with app.app_context():
    db.create_all()

def run_scan(scan_id):
    from scanner import Scanner
    with app.app_context():
        scan = db.session.get(Scan, scan_id)
        if not scan:
            return
        try:
            scan.status = 'running'
            scan.message = 'Iniciando varredura...'
            scan.progress = 5
            db.session.commit()

            s = Scanner(scan.niche, scan.country, scan.language)

            def update(progress, message):
                scan.progress = progress
                scan.message = message
                db.session.commit()

            result = s.run(update_cb=update)

            scan.result_json = json.dumps(result, ensure_ascii=False)
            scan.status = 'completed'
            scan.progress = 100
            scan.message = f'Concluído — {len(result.get("opportunities", []))} oportunidades encontradas'
            scan.completed_at = datetime.utcnow()
            db.session.commit()

        except Exception as e:
            scan.status = 'error'
            scan.message = f'Erro: {str(e)}'
            db.session.commit()

# Serve index.html from root folder (no templates/ needed)
@app.route('/')
def index():
    base = os.path.dirname(os.path.abspath(__file__))
    # Try templates/index.html first, then root index.html
    for path in [os.path.join(base, 'templates', 'index.html'),
                 os.path.join(base, 'index.html')]:
        if os.path.exists(path):
            return send_file(path)
    return 'index.html not found', 404

@app.route('/api/scans', methods=['GET'])
def list_scans():
    scans = Scan.query.order_by(Scan.created_at.desc()).limit(50).all()
    return jsonify([s.to_dict() for s in scans])

@app.route('/api/scans', methods=['POST'])
def create_scan():
    data = request.json
    if not data or not data.get('niche'):
        return jsonify({'error': 'Nicho é obrigatório'}), 400
    scan = Scan(
        name=data.get('name') or f"Varredura: {data['niche']}",
        niche=data['niche'],
        country=data.get('country', 'BR'),
        language=data.get('language', 'pt'),
    )
    db.session.add(scan)
    db.session.commit()
    t = threading.Thread(target=run_scan, args=(scan.id,), daemon=True)
    t.start()
    return jsonify(scan.to_dict()), 201

@app.route('/api/scans/<scan_id>', methods=['GET'])
def get_scan(scan_id):
    scan = db.session.get(Scan, scan_id)
    if not scan:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(scan.to_dict())

@app.route('/api/scans/<scan_id>', methods=['DELETE'])
def delete_scan(scan_id):
    scan = db.session.get(Scan, scan_id)
    if not scan:
        return jsonify({'error': 'Not found'}), 404
    db.session.delete(scan)
    db.session.commit()
    return jsonify({'ok': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
