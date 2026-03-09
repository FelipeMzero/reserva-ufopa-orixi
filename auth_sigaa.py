"""
auth_sigaa.py — Módulo de autenticação UFOPA/SIGAA
Substitui a função realizar_login_sigaa do app.py

DIAGNÓSTICO DOS PROBLEMAS DO LOGIN ANTIGO:
  1. Não fazia GET antes do POST → sem cookies de sessão do servidor
  2. Headers básicos → SIGAA bloqueia como bot
  3. Detecção de falha por URL era frágil ("logon" na URL pode aparecer no sucesso)
  4. Sem Referer → servidores Java/Struts rejeitam POST sem Referer
  5. allow_redirects=True sem verificar destino final é ambíguo
"""

import re
import requests
from requests.exceptions import Timeout, ConnectionError, RequestException


# URLs do SIGAA UFOPA
_URL_LOGIN_PAGE = "https://sigaa.ufopa.edu.br/sigaa/verTelaLogin.do"
_URL_LOGIN_POST = "https://sigaa.ufopa.edu.br/sigaa/logar.do?dispatch=logOn"

# Headers que imitam um navegador real
_HEADERS_BASE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Textos que confirmam login INVÁLIDO no SIGAA
_TEXTOS_FALHA = [
    "Usuário e/ou senha inválidos",
    "usu\xe1rio e/ou senha inv\xe1lidos",   # versão com acento escapada
    "Login inv\xe1lido",
    "Login inválido",
    "Senha inválida",
    "verTelaLogin",          # voltou pra tela de login = falhou
    "login incorreto",
]

# Textos que confirmam login BEM-SUCEDIDO
_TEXTOS_SUCESSO = [
    "Sair do Sistema",
    "sair do sistema",
    "Bem-vindo",
    "portais/discente",
    "portais/docente",
    "portais/tecnico",
    "menu.do",
]


def _extrair_nome_amigavel(login: str) -> str:
    """'joao.da.silva' → 'Joao Silva'"""
    partes = [p for p in login.split('.') if len(p) > 1]
    return ' '.join(p.capitalize() for p in partes[:2]) or login.capitalize()


def realizar_login_sigaa(usuario: str, senha: str) -> str | None:
    """
    Autentica no SIGAA UFOPA.

    Retorna o nome amigável do usuário em caso de sucesso,
    ou None em caso de falha (credenciais erradas, SIGAA fora do ar, timeout).

    Fluxo correto:
      1. GET na página de login → obtém cookies de sessão do servidor Java
      2. POST com credenciais + Referer → servidor valida contra os cookies
      3. Análise da resposta final para determinar sucesso/falha
    """
    session = requests.Session()
    session.headers.update(_HEADERS_BASE)

    # ── PASSO 1: GET para obter os cookies de sessão ───────────────────────
    try:
        pagina_login = session.get(_URL_LOGIN_PAGE, timeout=12, allow_redirects=True)
    except Timeout:
        raise SIGAAIndisponivel("O SIGAA não respondeu (timeout na página de login).")
    except ConnectionError:
        raise SIGAAIndisponivel("Não foi possível conectar ao SIGAA. Verifique a rede.")
    except RequestException as e:
        raise SIGAAIndisponivel(f"Erro de rede ao acessar o SIGAA: {e}")

    # Extrai campos ocultos do formulário (tokens anti-CSRF, se houver)
    campos_ocultos = dict(
        re.findall(r'<input[^>]+type=["\']hidden["\'][^>]+name=["\']([^"\']+)["\'][^>]+value=["\']([^"\']*)["\']', pagina_login.text, re.I) +
        re.findall(r'<input[^>]+name=["\']([^"\']+)["\'][^>]+type=["\']hidden["\'][^>]+value=["\']([^"\']*)["\']', pagina_login.text, re.I)
    )

    # ── PASSO 2: POST com credenciais ─────────────────────────────────────
    payload = {
        **campos_ocultos,        # inclui tokens ocultos, se existirem
        "user.login": usuario.strip(),
        "user.senha": senha,
    }

    try:
        resposta = session.post(
            _URL_LOGIN_POST,
            data=payload,
            timeout=15,
            allow_redirects=True,
            headers={
                **_HEADERS_BASE,
                "Referer": _URL_LOGIN_PAGE,
                "Origin": "https://sigaa.ufopa.edu.br",
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
    except Timeout:
        raise SIGAAIndisponivel("O SIGAA não respondeu durante o login (timeout).")
    except ConnectionError:
        raise SIGAAIndisponivel("Conexão perdida durante o login.")
    except RequestException as e:
        raise SIGAAIndisponivel(f"Erro ao enviar credenciais: {e}")

    # ── PASSO 3: Análise da resposta ───────────────────────────────────────
    texto = resposta.text
    url_final = resposta.url

    # Verifica falha explícita primeiro
    for indicador in _TEXTOS_FALHA:
        if indicador.lower() in texto.lower() or indicador.lower() in url_final.lower():
            return None  # Credenciais inválidas

    # Verifica sucesso explícito
    for indicador in _TEXTOS_SUCESSO:
        if indicador.lower() in texto.lower() or indicador.lower() in url_final.lower():
            return _extrair_nome_amigavel(usuario)

    # Heurística de desempate: se redirecionou para fora da tela de login = sucesso
    if "verTelaLogin" not in url_final and resposta.status_code == 200:
        return _extrair_nome_amigavel(usuario)

    # Não conseguiu determinar → trata como falha por segurança
    return None


class SIGAAIndisponivel(Exception):
    """Lançada quando o SIGAA está inacessível (não é erro de credencial)."""
    pass