import requests
from flask import Flask, render_template, request, redirect, url_for, session
import csv
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'chave_deveras_secreta'
CSV_FILE = 'reservas.csv'

# --- FUNÇÕES DE BANCO DE DADOS (CSV) ---

def inicializar_csv():
    """Garante a existência do arquivo com o cabeçalho correto"""
    if not os.path.exists(CSV_FILE) or os.stat(CSV_FILE).st_size == 0:
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['usuario', 'sala', 'aula', 'data', 'hora_inicio', 'hora_fim'])

def carregar_reservas():
    """Lê todas as reservas do CSV limpando espaços em branco"""
    reservas = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_limpa = {k.strip(): v.strip() for k, v in row.items()}
                reservas.append(row_limpa)
    return reservas

def salvar_lista_reservas(lista):
    """Sobrescreve o CSV com a lista fornecida"""
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['usuario', 'sala', 'aula', 'data', 'hora_inicio', 'hora_fim'])
        for res in lista:
            writer.writerow([res['usuario'], res['sala'], res['aula'], res['data'], res['hora_inicio'], res['hora_fim']])

# --- LÓGICA DE FILTRO E STATUS ---

def obter_reservas_processadas():
    """Filtra reservas passadas e define status (Agendada, Executando, Realizada)"""
    lista_completa = carregar_reservas()
    agora = datetime.now()
    data_hoje = agora.strftime('%Y-%m-%d')
    hora_atual = agora.strftime('%H:%M')
    
    processadas = []
    for res in lista_completa:
        # FILTRO: Mostrar apenas do dia atual em diante
        if res['data'] >= data_hoje:
            # LÓGICA DE STATUS
            if res['data'] > data_hoje:
                res['status'] = 'Agendada'
            else: # É hoje
                if hora_atual < res['hora_inicio']:
                    res['status'] = 'Agendada'
                elif res['hora_inicio'] <= hora_atual <= res['hora_fim']:
                    res['status'] = 'Executando'
                else:
                    res['status'] = 'Realizada'
            
            processadas.append(res)
            
    # Ordenar por data e depois por hora de início
    processadas.sort(key=lambda x: (x['data'], x['hora_inicio']))
    return processadas

# --- AUTENTICAÇÃO ---

def realizar_login_sigaa(usuario, senha):
    url_login = "https://sigaa.ufopa.edu.br/sigaa/logar.do?dispatch=logOn"
    payload = {'user.login': usuario, 'user.senha': senha}
    try:
        with requests.Session() as s:
            response = s.post(url_login, data=payload, timeout=10)
            if "Usuário e/ou senha inválidos" in response.text:
                return None
            # Retorna o primeiro nome capitalizado
            return usuario.split('.')[0].capitalize()
    except:
        return None

# --- ROTAS ---

@app.route('/')
def login():
    if 'user_nome' in session: 
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/auth', methods=['POST'])
def auth():
    user = request.form.get('user')
    password = request.form.get('password')
    nome_usuario = realizar_login_sigaa(user, password)
    if nome_usuario:
        session['user_nome'] = nome_usuario
        return redirect(url_for('dashboard'))
    return "Erro: Login inválido. <a href='/'>Voltar</a>"

@app.route('/dashboard')
def dashboard():
    if 'user_nome' not in session: 
        return redirect(url_for('login'))
    return render_template('index.html', nome=session['user_nome'], reservas=obter_reservas_processadas())

@app.route('/reservar', methods=['POST'])
def reservar():
    if 'user_nome' not in session: 
        return redirect(url_for('login'))
    
    sala = request.form.get('sala')
    data = request.form.get('data')
    inicio = request.form.get('hora_inicio')
    fim = request.form.get('hora_fim')
    
    # Validação contra conflitos (Considerando todas as reservas no banco)
    lista = carregar_reservas()
    for r in lista:
        if r['sala'] == sala and r['data'] == data:
            if (inicio < r['hora_fim']) and (fim > r['hora_inicio']):
                return "<h2>Conflito!</h2><p>Horário já ocupado por outro professor.</p><a href='/dashboard'>Voltar</a>"

    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([session['user_nome'], sala, request.form.get('aula'), data, inicio, fim])
    return redirect(url_for('dashboard'))

@app.route('/editar/<int:index>', methods=['GET', 'POST'])
def editar(index):
    if 'user_nome' not in session: 
        return redirect(url_for('login'))
    
    visiveis = obter_reservas_processadas()
    completa = carregar_reservas()
    
    if index >= len(visiveis) or visiveis[index]['usuario'] != session['user_nome']:
        return "Erro: Negado. Você só pode editar suas próprias reservas. <a href='/dashboard'>Voltar</a>"

    res_alvo = visiveis[index]

    if request.method == 'POST':
        nova_data = request.form.get('data')
        novo_inicio = request.form.get('hora_inicio')
        novo_fim = request.form.get('hora_fim')
        nova_sala = request.form.get('sala')

        # Validação contra CONFLITOS (ignorando a própria reserva sendo alterada)
        for r in completa:
            # Identificação única da reserva original para pular a checagem dela mesma
            if r['usuario'] == res_alvo['usuario'] and r['data'] == res_alvo['data'] and r['hora_inicio'] == res_alvo['hora_inicio']:
                continue
            if r['sala'] == nova_sala and r['data'] == nova_data:
                if (novo_inicio < r['hora_fim']) and (novo_fim > r['hora_inicio']):
                    return "<h2>Erro na Edição!</h2><p>O novo horário entra em conflito com outra reserva ativa.</p><a href='/dashboard'>Voltar</a>"

        # Atualização na lista completa
        for r in completa:
            if r['usuario'] == res_alvo['usuario'] and r['data'] == res_alvo['data'] and r['hora_inicio'] == res_alvo['hora_inicio']:
                r.update({
                    'sala': nova_sala, 
                    'aula': request.form.get('aula'), 
                    'data': nova_data, 
                    'hora_inicio': novo_inicio, 
                    'hora_fim': novo_fim
                })
                break
        
        salvar_lista_reservas(completa)
        return redirect(url_for('dashboard'))

    return render_template('editar.html', reserva=res_alvo, index=index, nome=session['user_nome'])

@app.route('/excluir/<int:index>')
def excluir(index):
    if 'user_nome' not in session: 
        return redirect(url_for('login'))
    
    visiveis = obter_reservas_processadas()
    if index < len(visiveis):
        res = visiveis[index]
        if res['usuario'] == session['user_nome']:
            completa = carregar_reservas()
            # Remove o item da lista completa comparando os campos identificadores
            nova = [r for r in completa if not (
                r['usuario'] == res['usuario'] and 
                r['data'] == res['data'] and 
                r['hora_inicio'] == res['hora_inicio']
            )]
            salvar_lista_reservas(nova)
            
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    inicializar_csv()
    app.run(host='0.0.0.0', port=5000, debug=True)