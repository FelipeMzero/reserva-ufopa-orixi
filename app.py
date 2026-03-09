import uuid
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash
import csv
import os
import calendar
from datetime import datetime, timedelta

from auth_sigaa import realizar_login_sigaa, SIGAAIndisponivel

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'troque-esta-chave-em-producao')
CSV_FILE = 'reservas.csv'
FIELDNAMES = ['id', 'usuario', 'sala', 'aula', 'data', 'hora_inicio', 'hora_fim']

# ─── BANCO DE DADOS ───────────────────────────────────────

def inicializar_csv():
    if not os.path.exists(CSV_FILE) or os.stat(CSV_FILE).st_size == 0:
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(FIELDNAMES)

def carregar_reservas():
    reservas = []
    if not os.path.exists(CSV_FILE):
        return reservas
    with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if not row or not row.get('data', '').strip():
                continue
            row_limpa = {str(k).strip(): str(v).strip() for k, v in row.items() if k and v is not None}
            if 'id' not in row_limpa or not row_limpa['id']:
                row_limpa['id'] = str(uuid.uuid4())
            reservas.append(row_limpa)
    return reservas

def salvar_lista_reservas(lista):
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction='ignore')
        writer.writeheader()
        for res in lista:
            writer.writerow({k: res.get(k, '') for k in FIELDNAMES})

# ─── STATUS E CONFLITOS ───────────────────────────────────

def calcular_status(res, agora):
    data_hoje = agora.strftime('%Y-%m-%d')
    hora_atual = agora.strftime('%H:%M')
    d = res['data']
    if d < data_hoje: return 'Realizada'
    if d > data_hoje: return 'Agendada'
    if hora_atual < res['hora_inicio']: return 'Agendada'
    if res['hora_inicio'] <= hora_atual <= res['hora_fim']: return 'Executando'
    return 'Realizada'

def obter_reservas_processadas():
    lista = carregar_reservas()
    agora = datetime.now()
    for res in lista:
        res['status'] = calcular_status(res, agora)
    lista.sort(key=lambda x: (x['data'], x['hora_inicio']))
    return lista

def detectar_conflito(lista, sala, data, inicio, fim, excluir_id=None):
    for r in lista:
        if excluir_id and r.get('id') == excluir_id:
            continue
        if r['sala'] == sala and r['data'] == data:
            if inicio < r['hora_fim'] and fim > r['hora_inicio']:
                return r
    return None

# ─── REPETIÇÃO ────────────────────────────────────────────

def gerar_datas_repeticao(data_inicial_str, repeticao_tipo, data_fim_str):
    datas = [data_inicial_str]
    if not repeticao_tipo or repeticao_tipo.lower() in ['nenhum', ''] or not data_fim_str:
        return datas
    data_atual = datetime.strptime(data_inicial_str, '%Y-%m-%d')
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d')
    for _ in range(365):
        tipo = repeticao_tipo.lower()
        if tipo == 'diariamente':
            data_atual += timedelta(days=1)
        elif tipo == 'semanalmente':
            data_atual += timedelta(weeks=1)
        elif tipo == 'mensalmente':
            mes = data_atual.month % 12 + 1
            ano = data_atual.year + (1 if data_atual.month == 12 else 0)
            dia = min(data_atual.day, calendar.monthrange(ano, mes)[1])
            data_atual = data_atual.replace(year=ano, month=mes, day=dia)
        elif tipo == 'anualmente':
            ano = data_atual.year + 1
            dia = data_atual.day
            if data_atual.month == 2 and dia == 29 and not calendar.isleap(ano):
                dia = 28
            data_atual = data_atual.replace(year=ano, day=dia)
        else:
            break
        if data_atual > data_fim:
            break
        datas.append(data_atual.strftime('%Y-%m-%d'))
    return datas

# ─── ROTAS ────────────────────────────────────────────────

@app.route('/')
def login():
    if 'user_nome' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/auth', methods=['POST'])
def auth():
    user = request.form.get('user', '').strip()
    password = request.form.get('password', '').strip()

    if not user or not password:
        flash('Preencha o usuário e a senha.', 'erro')
        return redirect(url_for('login'))

    try:
        nome_usuario = realizar_login_sigaa(user, password)
    except SIGAAIndisponivel as e:
        flash(f'O portal SIGAA está temporariamente indisponível. Tente novamente em instantes. ({e})', 'erro')
        return redirect(url_for('login'))
    except Exception as e:
        flash(f'Erro inesperado: {e}', 'erro')
        return redirect(url_for('login'))

    if nome_usuario:
        session['user_nome'] = nome_usuario
        session['user_login'] = user
        return redirect(url_for('dashboard'))

    flash('Usuário ou senha inválidos. Use as credenciais do SIGAA.', 'erro')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_nome' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', nome=session['user_nome'], reservas=obter_reservas_processadas())

@app.route('/reservar', methods=['POST'])
def reservar():
    if 'user_nome' not in session:
        return redirect(url_for('login'))

    sala = request.form.get('sala', '').strip()
    aula = request.form.get('aula', '').strip()
    data_inicio = request.form.get('data', '').strip()

    if not sala or not aula or not data_inicio:
        flash('Preencha todos os campos obrigatórios.', 'erro')
        return redirect(url_for('dashboard'))

    if request.form.get('todo_o_dia'):
        inicio, fim = '08:00', '22:00'
    else:
        inicio = request.form.get('hora_inicio', '').strip()
        fim = request.form.get('hora_fim', '').strip()

    if not inicio or not fim or inicio >= fim:
        flash('Informe horários válidos (início antes do fim).', 'erro')
        return redirect(url_for('dashboard'))

    repeticao_tipo = request.form.get('repeticao_tipo', 'Nenhum')
    data_fim_rep = request.form.get('data_fim_repeticao', '').strip() or data_inicio
    datas = gerar_datas_repeticao(data_inicio, repeticao_tipo, data_fim_rep)
    lista = carregar_reservas()
    novas = []

    for data_alvo in datas:
        conflito = detectar_conflito(lista, sala, data_alvo, inicio, fim)
        if conflito:
            flash(
                f"Conflito em {data_alvo}: '{conflito.get('aula','?')}' ocupa {sala} "
                f"das {conflito.get('hora_inicio')} às {conflito.get('hora_fim')}.",
                'erro'
            )
            return redirect(url_for('dashboard'))
        novas.append({'id': str(uuid.uuid4()), 'usuario': session['user_nome'],
                      'sala': sala, 'aula': aula, 'data': data_alvo,
                      'hora_inicio': inicio, 'hora_fim': fim})

    lista.extend(novas)
    salvar_lista_reservas(lista)
    flash(f"{len(novas)} reserva{'s' if len(novas)>1 else ''} criada{'s' if len(novas)>1 else ''}!", 'sucesso')
    return redirect(url_for('dashboard'))

@app.route('/editar/<string:res_id>', methods=['GET', 'POST'])
def editar(res_id):
    if 'user_nome' not in session:
        return redirect(url_for('login'))
    lista = carregar_reservas()
    reserva = next((r for r in lista if r.get('id') == res_id), None)
    if not reserva:
        flash('Reserva não encontrada.', 'erro')
        return redirect(url_for('dashboard'))
    if reserva['usuario'] != session['user_nome']:
        flash('Sem permissão para editar esta reserva.', 'erro')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        nova_data = request.form.get('data', '').strip()
        nova_sala = request.form.get('sala', '').strip()
        novo_aula = request.form.get('aula', '').strip()
        if request.form.get('todo_o_dia'):
            novo_inicio, novo_fim = '08:00', '22:00'
        else:
            novo_inicio = request.form.get('hora_inicio', '').strip()
            novo_fim = request.form.get('hora_fim', '').strip()

        if novo_inicio >= novo_fim:
            flash('Hora de início deve ser anterior à hora de fim.', 'erro')
            return redirect(url_for('editar', res_id=res_id))

        conflito = detectar_conflito(lista, nova_sala, nova_data, novo_inicio, novo_fim, excluir_id=res_id)
        if conflito:
            flash(f"Conflito: '{conflito.get('aula','?')}' já ocupa {nova_sala} "
                  f"das {conflito.get('hora_inicio')} às {conflito.get('hora_fim')}.", 'erro')
            return redirect(url_for('editar', res_id=res_id))

        for r in lista:
            if r.get('id') == res_id:
                r.update({'sala': nova_sala, 'aula': novo_aula, 'data': nova_data,
                           'hora_inicio': novo_inicio, 'hora_fim': novo_fim})
                break
        salvar_lista_reservas(lista)
        flash('Reserva atualizada!', 'sucesso')
        return redirect(url_for('dashboard'))

    return render_template('editar.html', reserva=reserva, res_id=res_id, nome=session['user_nome'])

@app.route('/excluir/<string:res_id>')
def excluir(res_id):
    if 'user_nome' not in session:
        return redirect(url_for('login'))
    lista = carregar_reservas()
    reserva = next((r for r in lista if r.get('id') == res_id), None)
    if not reserva or reserva['usuario'] != session['user_nome']:
        flash('Operação não permitida.', 'erro')
        return redirect(url_for('dashboard'))
    salvar_lista_reservas([r for r in lista if r.get('id') != res_id])
    flash('Reserva excluída.', 'sucesso')
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    inicializar_csv()
    app.run(host='0.0.0.0', port=5000, debug=True)