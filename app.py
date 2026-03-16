import uuid
import json
import csv
import os
import calendar
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify

from auth_sigaa import realizar_login_sigaa, SIGAAIndisponivel

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'troque-esta-chave-em-producao')

CSV_FILE   = 'reservas.csv'
FIELDNAMES = ['id', 'usuario', 'sala', 'aula', 'data', 'hora_inicio', 'hora_fim', 'ts_criacao']

DATA_DIR       = os.path.join(os.path.dirname(__file__), 'data')
LOCAIS_FILE    = os.path.join(DATA_DIR, 'locais.json')
OPERADORES_FILE= os.path.join(DATA_DIR, 'operadores.json')
ADMINS_FILE    = os.path.join(DATA_DIR, 'admins.json')

# ─── HELPERS DE PAPEL ─────────────────────────────────────

def _carregar_json(path): # type: ignore
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def _salvar_json(path, data): # type: ignore
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def obter_papel(login: str) -> str: # type: ignore
    """Retorna 'admin', 'operador' ou 'visitante'."""
    try:
        admins = _carregar_json(ADMINS_FILE).get('admins', [])
        if any(a['login'] == login and a.get('ativo', True) for a in admins):
            return 'admin'
        ops = _carregar_json(OPERADORES_FILE).get('operadores', [])
        if any(o['login'] == login and o.get('ativo', True) for o in ops):
            return 'operador'
    except Exception:
        pass
    return 'visitante'

def carregar_locais_ativos(): # type: ignore
    try:
        data = _carregar_json(LOCAIS_FILE)
        return [l for l in data.get('locais', []) if l.get('ativo', True)]
    except Exception:
        return []

def locais_por_categoria(): # type: ignore
    cats = {}
    for l in carregar_locais_ativos():
        cat = l.get('categoria', 'Outros')
        cats.setdefault(cat, []).append(l)
    return cats

# ─── BANCO DE DADOS CSV ───────────────────────────────────

def inicializar_csv(): # type: ignore
    if not os.path.exists(CSV_FILE) or os.stat(CSV_FILE).st_size == 0:
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(FIELDNAMES)

def carregar_reservas(): # type: ignore
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
            if 'ts_criacao' not in row_limpa:
                row_limpa['ts_criacao'] = ''
            reservas.append(row_limpa)
    return reservas

def salvar_lista_reservas(lista): # type: ignore
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction='ignore')
        writer.writeheader()
        for res in lista:
            writer.writerow({k: res.get(k, '') for k in FIELDNAMES})

# ─── STATUS E CONFLITOS ───────────────────────────────────

def calcular_status(res, agora): # type: ignore
    data_hoje  = agora.strftime('%Y-%m-%d')
    hora_atual = agora.strftime('%H:%M')
    d = res['data']
    if d < data_hoje: return 'Realizada'
    if d > data_hoje: return 'Agendada'
    if hora_atual < res['hora_inicio']: return 'Agendada'
    if res['hora_inicio'] <= hora_atual <= res['hora_fim']: return 'Executando'
    return 'Realizada'

def obter_reservas_processadas(): # type: ignore
    lista = carregar_reservas()
    agora = datetime.now()
    for res in lista:
        res['status'] = calcular_status(res, agora)
    lista.sort(key=lambda x: (x['data'], x['hora_inicio']))
    return lista

def detectar_conflito(lista, sala, data, inicio, fim, excluir_id=None): # type: ignore
    for r in lista:
        if excluir_id and r.get('id') == excluir_id:
            continue
        if r['sala'] == sala and r['data'] == data:
            if inicio < r['hora_fim'] and fim > r['hora_inicio']:
                return r
    return None

# ─── REPETIÇÃO ────────────────────────────────────────────

def gerar_datas_repeticao(data_inicial_str, repeticao_tipo, data_fim_str): # type: ignore
    datas = [data_inicial_str]
    if not repeticao_tipo or repeticao_tipo.lower() in ['nenhum', ''] or not data_fim_str:
        return datas
    data_atual = datetime.strptime(data_inicial_str, '%Y-%m-%d')
    data_fim   = datetime.strptime(data_fim_str, '%Y-%m-%d')
    for _ in range(365):
        tipo = repeticao_tipo.lower()
        if   tipo == 'diariamente':  data_atual += timedelta(days=1)
        elif tipo == 'semanalmente': data_atual += timedelta(weeks=1)
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

# ─── DECORADORES ──────────────────────────────────────────
 
def requer_login(f): # type: ignore
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_nome' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapped

def requer_operador(f): # type: ignore
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_nome' not in session:
            return redirect(url_for('login'))
        if session.get('papel') not in ('operador', 'admin'):
            flash('Acesso restrito a operadores.', 'erro')
            return redirect(url_for('quadro'))
        return f(*args, **kwargs)
    return wrapped

def requer_admin(f): # type: ignore
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_nome' not in session:
            return redirect(url_for('login'))
        if session.get('papel') != 'admin':
            flash('Acesso restrito a administradores.', 'erro')
            return redirect(url_for('quadro'))
        return f(*args, **kwargs)
    return wrapped

# ─── ROTAS PÚBLICAS ───────────────────────────────────────

@app.route('/')
def login(): # type: ignore
    if 'user_nome' in session:
        papel = session.get('papel')
        if papel == 'admin':
            return redirect(url_for('admin'))
        if papel == 'operador':
            return redirect(url_for('dashboard'))
        return redirect(url_for('quadro'))
    return render_template('login.html')

@app.route('/auth', methods=['POST'])
def auth(): # type: ignore
    user     = request.form.get('user', '').strip()
    password = request.form.get('password', '').strip()

    if not user or not password:
        flash('Preencha o usuário e a senha.', 'erro')
        return redirect(url_for('login'))

    try:
        nome_usuario = realizar_login_sigaa(user, password)
    except SIGAAIndisponivel as e:
        flash(f'O portal SIGAA está temporariamente indisponível. ({e})', 'erro')
        return redirect(url_for('login'))
    except Exception as e:
        flash(f'Erro inesperado: {e}', 'erro')
        return redirect(url_for('login'))

    if not nome_usuario:
        flash('Usuário ou senha inválidos. Use as credenciais do SIGAA.', 'erro')
        return redirect(url_for('login'))

    papel = obter_papel(user)
    session['user_nome']  = nome_usuario
    session['user_login'] = user
    session['papel']      = papel

    if papel == 'admin':
        return redirect(url_for('admin'))
    if papel == 'operador':
        return redirect(url_for('dashboard'))
    return redirect(url_for('quadro'))

@app.route('/quadro')
def quadro(): # type: ignore
    """Página pública — apenas visualização do quadro de ocupação."""
    nome  = session.get('user_nome')
    papel = session.get('papel', 'visitante')
    return render_template('quadro.html',
                           nome=nome,
                           papel=papel,
                           reservas=obter_reservas_processadas())

# ─── ROTAS DE OPERADOR ────────────────────────────────────

@app.route('/dashboard')
@requer_operador
def dashboard(): # type: ignore
    reservas = obter_reservas_processadas()
    agora    = datetime.now()
    hoje_str = agora.strftime('%Y-%m-%d')
    stats = {
        'total':      len(reservas),
        'hoje':       sum(1 for r in reservas if r['data'] == hoje_str),
        'agendadas':  sum(1 for r in reservas if r['status'] == 'Agendada'),
        'minhas':     sum(1 for r in reservas if r['usuario'] == session['user_nome']),
    }
    return render_template('index.html',
                           nome=session['user_nome'],
                           papel=session['papel'],
                           reservas=reservas,
                           stats=stats,
                           locais_por_cat=locais_por_categoria(),
                           hoje=hoje_str)

@app.route('/reservar', methods=['POST'])
@requer_operador
def reservar():# type: ignore
    sala        = request.form.get('sala', '').strip()
    aula        = request.form.get('aula', '').strip()
    data_inicio = request.form.get('data', '').strip()

    if not sala or not aula or not data_inicio:
        flash('Preencha todos os campos obrigatórios.', 'erro')
        return redirect(url_for('dashboard'))

    if request.form.get('todo_o_dia'):
        inicio, fim = '08:00', '22:00'
    else:
        inicio = request.form.get('hora_inicio', '').strip()
        fim    = request.form.get('hora_fim', '').strip()

    if not inicio or not fim or inicio >= fim:
        flash('Informe horários válidos (início antes do fim).', 'erro')
        return redirect(url_for('dashboard'))

    repeticao_tipo = request.form.get('repeticao_tipo', 'Nenhum')
    data_fim_rep   = request.form.get('data_fim_repeticao', '').strip() or data_inicio
    datas  = gerar_datas_repeticao(data_inicio, repeticao_tipo, data_fim_rep)
    lista  = carregar_reservas()
    novas  = []
    ts_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

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
                      'hora_inicio': inicio, 'hora_fim': fim, 'ts_criacao': ts_now})

    lista.extend(novas)
    salvar_lista_reservas(lista)
    flash(f"{len(novas)} reserva{'s' if len(novas)>1 else ''} criada{'s' if len(novas)>1 else ''}!", 'sucesso')
    return redirect(url_for('dashboard'))

@app.route('/editar/<string:res_id>', methods=['GET', 'POST'])
@requer_operador
def editar(res_id):# type: ignore
    lista   = carregar_reservas()
    reserva = next((r for r in lista if r.get('id') == res_id), None)
    if not reserva:
        flash('Reserva não encontrada.', 'erro')
        return redirect(url_for('dashboard'))

    # Admin pode editar qualquer reserva; operador só a sua
    if session['papel'] != 'admin' and reserva['usuario'] != session['user_nome']:
        flash('Sem permissão para editar esta reserva.', 'erro')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        nova_data  = request.form.get('data', '').strip()
        nova_sala  = request.form.get('sala', '').strip()
        novo_aula  = request.form.get('aula', '').strip()
        if request.form.get('todo_o_dia'):
            novo_inicio, novo_fim = '08:00', '22:00'
        else:
            novo_inicio = request.form.get('hora_inicio', '').strip()
            novo_fim    = request.form.get('hora_fim', '').strip()

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
        destino = url_for('admin') if session['papel'] == 'admin' else url_for('dashboard')
        return redirect(destino)

    return render_template('editar.html',
                           reserva=reserva,
                           res_id=res_id,
                           nome=session['user_nome'],
                           papel=session['papel'],
                           locais_por_cat=locais_por_categoria())

@app.route('/excluir/<string:res_id>')
@requer_operador
def excluir(res_id):# type: ignore
    lista   = carregar_reservas()
    reserva = next((r for r in lista if r.get('id') == res_id), None)
    if not reserva:
        flash('Reserva não encontrada.', 'erro')
        return redirect(url_for('dashboard'))
    if session['papel'] != 'admin' and reserva['usuario'] != session['user_nome']:
        flash('Operação não permitida.', 'erro')
        return redirect(url_for('dashboard'))

    salvar_lista_reservas([r for r in lista if r.get('id') != res_id])
    flash('Reserva excluída.', 'sucesso')
    destino = url_for('admin') if session['papel'] == 'admin' else url_for('dashboard')
    return redirect(destino)

# ─── ROTAS DE ADMIN ───────────────────────────────────────

@app.route('/admin')
@requer_admin
def admin():# type: ignore
    reservas = obter_reservas_processadas()
    agora    = datetime.now()
    hoje_str = agora.strftime('%Y-%m-%d')

    # Estatísticas para os gráficos
    por_sala   = {}
    por_status = {'Agendada': 0, 'Executando': 0, 'Realizada': 0}
    por_mes    = {}
    por_usuario= {}

    for r in reservas:
        por_sala[r['sala']]   = por_sala.get(r['sala'], 0) + 1
        st = r.get('status', 'Agendada')
        por_status[st]        = por_status.get(st, 0) + 1
        mes = r['data'][:7]
        por_mes[mes]          = por_mes.get(mes, 0) + 1
        por_usuario[r['usuario']] = por_usuario.get(r['usuario'], 0) + 1

    stats = {
        'total':      len(reservas),
        'hoje':       sum(1 for r in reservas if r['data'] == hoje_str),
        'agendadas':  por_status.get('Agendada', 0),
        'realizadas': por_status.get('Realizada', 0),
    }

    locais_data  = _carregar_json(LOCAIS_FILE)
    ops_data     = _carregar_json(OPERADORES_FILE)
    admins_data  = _carregar_json(ADMINS_FILE)

    return render_template('admin.html',
                           nome=session['user_nome'],
                           papel=session['papel'],
                           reservas=reservas,
                           stats=stats,
                           por_sala=por_sala,
                           por_status=por_status,
                           por_mes=dict(sorted(por_mes.items())),
                           por_usuario=por_usuario,
                           locais=locais_data.get('locais', []),
                           operadores=ops_data.get('operadores', []),
                           admins=admins_data.get('admins', []),
                           hoje=hoje_str)

# ── Admin: gerenciar locais ──

@app.route('/admin/locais/adicionar', methods=['POST'])
@requer_admin
def admin_local_adicionar():# type: ignore
    data = _carregar_json(LOCAIS_FILE)
    novo = {
        'id':         request.form.get('id', '').strip().lower().replace(' ', '-'),
        'nome':       request.form.get('nome', '').strip(),
        'categoria':  request.form.get('categoria', '').strip(),
        'capacidade': int(request.form.get('capacidade', 0) or 0),
        'descricao':  request.form.get('descricao', '').strip(),
        'ativo':      True
    }
    if not novo['nome']:
        flash('Nome do local é obrigatório.', 'erro')
        return redirect(url_for('admin') + '#locais')
    if not novo['id']:
        novo['id'] = str(uuid.uuid4())[:8]
    data['locais'].append(novo)
    _salvar_json(LOCAIS_FILE, data)
    flash(f"Local '{novo['nome']}' adicionado.", 'sucesso')
    return redirect(url_for('admin') + '#locais')

@app.route('/admin/locais/toggle/<string:local_id>')
@requer_admin
def admin_local_toggle(local_id):# type: ignore
    data = _carregar_json(LOCAIS_FILE)
    for l in data['locais']:
        if l['id'] == local_id:
            l['ativo'] = not l.get('ativo', True)
            break
    _salvar_json(LOCAIS_FILE, data)
    flash('Status do local atualizado.', 'sucesso')
    return redirect(url_for('admin') + '#locais')

@app.route('/admin/locais/excluir/<string:local_id>')
@requer_admin
def admin_local_excluir(local_id):# type: ignore
    data = _carregar_json(LOCAIS_FILE)
    data['locais'] = [l for l in data['locais'] if l['id'] != local_id]
    _salvar_json(LOCAIS_FILE, data)
    flash('Local removido.', 'sucesso')
    return redirect(url_for('admin') + '#locais')

# ── Admin: gerenciar operadores ──

@app.route('/admin/operadores/adicionar', methods=['POST'])
@requer_admin
def admin_op_adicionar():# type: ignore
    login = request.form.get('login', '').strip().lower()
    if not login:
        flash('Login é obrigatório.', 'erro')
        return redirect(url_for('admin') + '#usuarios')
    data = _carregar_json(OPERADORES_FILE)
    if any(o['login'] == login for o in data['operadores']):
        flash('Operador já cadastrado.', 'erro')
        return redirect(url_for('admin') + '#usuarios')
    data['operadores'].append({'login': login, 'nome': request.form.get('nome','').strip(), 'ativo': True})
    _salvar_json(OPERADORES_FILE, data)
    flash(f"Operador '{login}' adicionado.", 'sucesso')
    return redirect(url_for('admin') + '#usuarios')

@app.route('/admin/operadores/toggle/<string:login>')
@requer_admin
def admin_op_toggle(login):# type: ignore
    data = _carregar_json(OPERADORES_FILE)
    for o in data['operadores']:
        if o['login'] == login:
            o['ativo'] = not o.get('ativo', True)
            break
    _salvar_json(OPERADORES_FILE, data)
    flash('Status do operador atualizado.', 'sucesso')
    return redirect(url_for('admin') + '#usuarios')

@app.route('/admin/operadores/excluir/<string:login>')
@requer_admin
def admin_op_excluir(login):# type: ignore
    data = _carregar_json(OPERADORES_FILE)
    data['operadores'] = [o for o in data['operadores'] if o['login'] != login]
    _salvar_json(OPERADORES_FILE, data)
    flash('Operador removido.', 'sucesso')
    return redirect(url_for('admin') + '#usuarios')

# ── Admin: exportar CSV ──

@app.route('/admin/exportar')
@requer_admin
def admin_exportar():# type: ignore
    from flask import Response
    busca = request.args.get('q', '').strip().lower()
    lista = obter_reservas_processadas()
    if busca:
        lista = [r for r in lista if busca in r.get('usuario','').lower()
                 or busca in r.get('aula','').lower()
                 or busca in r.get('sala','').lower()]

    import io
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=FIELDNAMES + ['status'])
    writer.writeheader()
    for r in lista:
        writer.writerow({k: r.get(k,'') for k in FIELDNAMES + ['status']})
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=reservas_ufopa.csv'}
    )

# ── API para calendário ──

@app.route('/api/reservas')
def api_reservas():# type: ignore
    lista = obter_reservas_processadas()
    eventos = []
    for r in lista:
        eventos.append({
            'id':    r['id'],
            'title': r['aula'],
            'start': f"{r['data']}T{r['hora_inicio']}",
            'end':   f"{r['data']}T{r['hora_fim']}",
            'extendedProps': {
                'sala':     r['sala'],
                'usuario':  r['usuario'],
                'status':   r.get('status',''),
                'owner':    r['usuario'] == session.get('user_nome')
            }
        })
    return jsonify(eventos)

# ─── LOGOUT ───────────────────────────────────────────────

@app.route('/logout')
def logout(): # type: ignore
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    inicializar_csv()
    app.run(host='0.0.0.0', port=5000, debug=True)
