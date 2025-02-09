from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import qrcode
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventario.db'
app.config['SECRET_KEY'] = 'minha_chave_secreta'
db = SQLAlchemy(app)

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
    qr_code_file = db.Column(db.String(100), nullable=True)
    # Campo para associar o material a uma categoria (pode ser nulo)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=True)

    def __repr__(self):
        return f'<Material {self.nome}>'

# ===================================
# Configuração para armazenar os QR Codes
# ===================================
qr_folder = os.path.join('static', 'qr_codes')
if not os.path.exists(qr_folder):
    os.makedirs(qr_folder)

# ===================================
# Função para gerar o QR Code
# ===================================
def gerar_qr_code(material):
    conteudo = f"http://192.168.0.100/editar/{material.id}"
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=5
    )
    qr.add_data(conteudo)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    nome_arquivo = f"qr_{material.id}.png"
    caminho_arquivo = os.path.join(qr_folder, nome_arquivo)
    img.save(caminho_arquivo)
    
    return nome_arquivo

# ===================================
# Função para pré-popular categorias padrão
# ===================================
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
    # Ordena as categorias em ordem alfabética
    categorias_padrao = sorted(categorias_padrao)
    for nome in categorias_padrao:
        if not Categoria.query.filter_by(nome=nome).first():
            nova_categoria = Categoria(nome=nome)
            db.session.add(nova_categoria)
    db.session.commit()

# ===================================
# Definição das Rotas
# ===================================

@app.route('/')
def index():
    # Obtém o parâmetro de ordenação; se não for passado, usa "todos" (sem ordenação especial)
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
def adicionar():
    # Busca todas as categorias cadastradas, ordenadas alfabeticamente
    categorias = Categoria.query.order_by(Categoria.nome).all()
    if request.method == 'POST':
        nome = request.form['nome']
        descricao = request.form['descricao']
        quantidade = int(request.form['quantidade'])
        # Captura o id da categoria selecionada (se não for selecionada, fica None)
        categoria_id = request.form.get('categoria')
        if not categoria_id:
            categoria_id = None
        novo_material = Material(
            nome=nome,
            descricao=descricao,
            quantidade=quantidade,
            categoria_id=categoria_id
        )
        db.session.add(novo_material)
        db.session.commit()  # Gera o ID do material

        # Gera o QR Code para o novo material e atualiza o registro
        nome_qr = gerar_qr_code(novo_material)
        novo_material.qr_code_file = nome_qr
        db.session.commit()
        
        flash('Material adicionado com sucesso!', 'success')
        return redirect(url_for('index'))
    return render_template('adicionar.html', categorias=categorias)

@app.route('/remover/<int:id>', methods=['GET', 'POST'])
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
        # Atualiza a categoria
        categoria_id = request.form.get('categoria')
        if not categoria_id:
            material.categoria_id = None
        else:
            material.categoria_id = int(categoria_id)
        db.session.commit()
        flash('Material atualizado com sucesso!', 'success')
        return redirect(url_for('index'))
    return render_template('editar.html', material=material, categorias=categorias)

# Nova rota: Listar todas as categorias
@app.route('/categorias')
def categorias():
    categorias = Categoria.query.order_by(Categoria.nome).all()
    return render_template('categorias.html', categorias=categorias)

# Nova rota: Adicionar nova categoria (já existente)
@app.route('/categorias/adicionar', methods=['GET', 'POST'])
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

# Nova rota: Remover uma categoria sem excluir os itens associados
@app.route('/categorias/remover/<int:id>', methods=['GET', 'POST'])
def remover_categoria(id):
    categoria = Categoria.query.get_or_404(id)
    # Atualiza os materiais associados para que fiquem sem categoria
    materiais = Material.query.filter_by(categoria_id=categoria.id).all()
    for m in materiais:
        m.categoria_id = None
    db.session.delete(categoria)
    db.session.commit()
    flash('Categoria removida com sucesso! Os itens associados agora não possuem categoria.', 'success')
    return redirect(url_for('categorias'))

# ===================================
# Bloco Principal: Criação do Banco e Execução do App
# ===================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        prepopulate_categories()  # se estiver usando
    app.run(host='0.0.0.0', debug=True)
