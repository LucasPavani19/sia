from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventario.db'
app.config['SECRET_KEY'] = 'minha_chave_secreta'
db = SQLAlchemy(app)

# Configuração do Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ===================================
# Modelos: Categoria e Material
# ===================================

class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)
    # Relação para facilitar a consulta dos materiais desta categoria
    materiais = db.relationship('Material', backref='categoria', lazy=True)

class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(200), nullable=True)
    quantidade = db.Column(db.Integer, default=0)
    # O campo quantidade_minima foi removido
    quantidade_alerta_requisicao = db.Column(db.Integer, default=0)
    quantidade_alerta_estoque = db.Column(db.Integer, default=0)
    qr_code_file = db.Column(db.String(100), nullable=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=True)
    
    def __repr__(self):
        return f'<Material {self.nome}>'

# Modelo de Usuário
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)   # Para identificar o administrador
    approved = db.Column(db.Boolean, default=False)     # Novo usuário precisa de aprovação
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    # Apenas usuários aprovados são considerados ativos pelo Flask-Login
    @property
    def is_active(self):
        return self.approved

    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ===================================
# Configuração para armazenar os QR Codes
# ===================================
qr_folder = os.path.join('static', 'qr_codes')
if not os.path.exists(qr_folder):
    os.makedirs(qr_folder)

def gerar_qr_code(material):
    # Ajuste o endereço conforme necessário (exemplo para intranet)
    conteudo = f"http://192.168.0.100/editar/{material.id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(conteudo)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    nome_arquivo = f"qr_{material.id}.png"
    caminho_arquivo = os.path.join(qr_folder, nome_arquivo)
    img.save(caminho_arquivo)
    return nome_arquivo

def prepopulate_categories():
    categorias_padrao = [
        "Aparelhos domésticos",
        "Alvenaria",
        "Construção Civil",
        "Decoração",
        "Elétrica",
        "Escritório",
        "Fardamento",
        "Hidráulica",
        "Informática",
        "Jardinagem",
        "Limpeza",
        "Móveis",
        "Pintura",
        "Piscina",
        "Poda, jardinagem e grama",
        "Segurança"
    ]
    categorias_padrao = sorted(categorias_padrao)
    for nome in categorias_padrao:
        if not Categoria.query.filter_by(nome=nome).first():
            nova_categoria = Categoria(nome=nome)
            db.session.add(nova_categoria)
    db.session.commit()

# ===================================
# Rotas do Sistema
# ===================================

@app.route('/')
@login_required
def index():
    order = request.args.get('order', 'todos')
    if order == 'alfabetica':
        materiais = Material.query.order_by(Material.nome).all()
    elif order == 'categoria':
        materiais = Material.query.order_by(Material.categoria_id).all()
    elif order == 'ambos':
        materiais = Material.query.order_by(Material.categoria_id, Material.nome).all()
    else:
        materiais = Material.query.all()
    return render_template('index.html', materiais=materiais)

@app.route('/adicionar', methods=['GET', 'POST'])
@login_required
def adicionar():
    categorias = Categoria.query.order_by(Categoria.nome).all()
    if request.method == 'POST':
        nome = request.form['nome']
        descricao = request.form['descricao']
        quantidade = int(request.form['quantidade'])
        # Como removemos o campo quantidade_minima, usamos apenas os campos de alerta:
        quantidade_alerta_requisicao = int(request.form.get('quantidade_alerta_requisicao', 0))
        quantidade_alerta_estoque = int(request.form.get('quantidade_alerta_estoque', 0))
        categoria_id = request.form.get('categoria')
        if not categoria_id:
            categoria_id = None
        novo_material = Material(
            nome=nome,
            descricao=descricao,
            quantidade=quantidade,
            quantidade_alerta_requisicao=quantidade_alerta_requisicao,
            quantidade_alerta_estoque=quantidade_alerta_estoque,
            categoria_id=categoria_id
        )
        db.session.add(novo_material)
        db.session.commit()
        nome_qr = gerar_qr_code(novo_material)
        novo_material.qr_code_file = nome_qr
        db.session.commit()
        flash('Material adicionado com sucesso!', 'success')
        return redirect(url_for('index'))
    return render_template('adicionar.html', categorias=categorias)

@app.route('/remover/<int:id>', methods=['GET', 'POST'])
@login_required
def remover(id):
    material = Material.query.get_or_404(id)
    if material.qr_code_file:
        caminho_qr = os.path.join(qr_folder, material.qr_code_file)
        if os.path.exists(caminho_qr):
            os.remove(caminho_qr)
    db.session.delete(material)
    db.session.commit()
    flash('Material removido com sucesso!', 'success')
    return redirect(url_for('index'))

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    material = Material.query.get_or_404(id)
    categorias = Categoria.query.order_by(Categoria.nome).all()
    if request.method == 'POST':
        material.nome = request.form['nome']
        material.descricao = request.form['descricao']
        if 'zerar' in request.form:
            material.quantidade = 0
        else:
            material.quantidade = int(request.form['quantidade'])
        # Atualiza os campos de alerta
        material.quantidade_alerta_requisicao = int(request.form.get('quantidade_alerta_requisicao', material.quantidade_alerta_requisicao))
        material.quantidade_alerta_estoque = int(request.form.get('quantidade_alerta_estoque', material.quantidade_alerta_estoque))
        categoria_id = request.form.get('categoria')
        if not categoria_id:
            material.categoria_id = None
        else:
            material.categoria_id = int(categoria_id)
        db.session.commit()
        flash('Material atualizado com sucesso!', 'success')
        return redirect(url_for('index'))
    return render_template('editar.html', material=material, categorias=categorias)

@app.route('/categorias')
@login_required
def categorias():
    categorias = Categoria.query.order_by(Categoria.nome).all()
    return render_template('categorias.html', categorias=categorias)

@app.route('/categorias/adicionar', methods=['GET', 'POST'])
@login_required
def adicionar_categoria():
    if request.method == 'POST':
        nome = request.form['nome'].strip()
        if nome:
            if Categoria.query.filter_by(nome=nome).first():
                flash('Categoria já existe!', 'warning')
            else:
                nova_categoria = Categoria(nome=nome)
                db.session.add(nova_categoria)
                db.session.commit()
                flash('Categoria adicionada com sucesso!', 'success')
                return redirect(url_for('categorias'))
        else:
            flash('O nome da categoria não pode ser vazio!', 'danger')
    return render_template('adicionar_categoria.html')

@app.route('/categorias/remover/<int:id>', methods=['GET', 'POST'])
@login_required
def remover_categoria(id):
    categoria = Categoria.query.get_or_404(id)
    materiais = Material.query.filter_by(categoria_id=categoria.id).all()
    for m in materiais:
        m.categoria_id = None
    db.session.delete(categoria)
    db.session.commit()
    flash('Categoria removida com sucesso! Os itens associados agora não possuem categoria.', 'success')
    return redirect(url_for('categorias'))

# ===================================
# Rotas de Autenticação
# ===================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if not user.approved:
                flash('Seu registro está aguardando autorização do administrador.', 'warning')
                return redirect(url_for('login'))
            login_user(user)
            flash('Login efetuado com sucesso!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Nome de usuário ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu da sessão.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('As senhas não coincidem.', 'danger')
            return render_template('register.html')
        if User.query.filter_by(username=username).first():
            flash('Nome de usuário já existe.', 'warning')
            return render_template('register.html')
        new_user = User(username=username)
        new_user.set_password(password)
        new_user.approved = False  # Novo usuário precisa de aprovação do admin
        db.session.add(new_user)
        db.session.commit()
        flash('Registro realizado com sucesso! Aguarde autorização do administrador.', 'info')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/admin/pending')
@login_required
def admin_pending():
    if not current_user.is_admin:
        flash('Você não tem permissão para acessar essa página.', 'danger')
        return redirect(url_for('index'))
    pending_users = User.query.filter_by(approved=False).all()
    return render_template('admin_pending.html', pending_users=pending_users)

@app.route('/admin/approve/<int:user_id>', methods=['POST'])
@login_required
def admin_approve(user_id):
    if not current_user.is_admin:
        flash('Você não tem permissão para realizar essa ação.', 'danger')
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    user.approved = True
    db.session.commit()
    flash(f'O usuário {user.username} foi aprovado.', 'success')
    return redirect(url_for('admin_pending'))

@app.route('/admin/reject/<int:user_id>', methods=['POST'])
@login_required
def admin_reject(user_id):
    if not current_user.is_admin:
        flash('Você não tem permissão para realizar essa ação.', 'danger')
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f'O usuário {user.username} foi rejeitado e removido.', 'info')
    return redirect(url_for('admin_pending'))

# ===================================
# Bloco Principal: Criação do Banco e Execução do App
# ===================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        prepopulate_categories()
        # Criar usuário admin se não existir
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', is_admin=True, approved=True)
            admin.set_password('senha123')
            db.session.add(admin)
            db.session.commit()
    app.run(host='0.0.0.0', debug=True)
