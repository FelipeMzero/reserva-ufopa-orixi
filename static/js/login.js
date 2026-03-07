document.addEventListener('DOMContentLoaded', () => {
    const formLogin = document.getElementById('formLogin');
    const btnEntrar = document.getElementById('btnEntrar');
    const inputSenha = document.getElementById('password');
    const alertaAviso = document.querySelector('.alert-aviso');

    // 1. Feedback Visual ao Enviar (Evita múltiplos cliques)
    if (formLogin) {
        formLogin.addEventListener('submit', () => {
            btnEntrar.disabled = true;
            btnEntrar.style.opacity = '0.7';
            btnEntrar.style.cursor = 'not-allowed';
            btnEntrar.innerHTML = '<span class="spinner"></span> AUTENTICANDO NO SIGAA...';
        });
    }

    // 2. Detecção de Caps Lock em Tempo Real
    if (inputSenha && alertaAviso) {
        inputSenha.addEventListener('keyup', (event) => {
            // Verifica se o Caps Lock está ativo no momento da digitação
            if (event.getModifierState('CapsLock')) {
                alertaAviso.style.display = 'block';
                alertaAviso.innerHTML = '⚠️ <strong>Atenção:</strong> O Caps Lock está ATIVADO!';
                alertaAviso.style.backgroundColor = '#fff3cd'; // Cor de alerta
                alertaAviso.style.color = '#856404';
            } else {
                // Retorna ao aviso padrão do sistema
                alertaAviso.innerHTML = '<small>Atenção: O sistema diferencia maiúsculas de minúsculas apenas na senha.</small>';
                alertaAviso.style.backgroundColor = ''; 
                alertaAviso.style.color = '';
            }
        });
    }
});