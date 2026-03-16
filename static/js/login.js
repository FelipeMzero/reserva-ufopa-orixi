/**
 * login.js — Sistema de Reservas UFOPA
 * Funcionalidades:
 *  - Mostrar/ocultar senha com animação no ícone
 *  - Detecção de Caps Lock em tempo real
 *  - Barra de força da senha animada
 *  - Validação visual dos campos (floating label + check)
 *  - Loading state no botão ao submeter
 *  - Shake no card em caso de erro
 */

document.addEventListener('DOMContentLoaded', () => {

    // ── Elementos ───────────────────────────────────────────
    const formLogin     = document.getElementById('formLogin');
    const btnEntrar     = document.getElementById('btnEntrar');
    const inputUser     = document.getElementById('user');
    const inputSenha    = document.getElementById('password');
    const btnEye        = document.getElementById('btnEye');
    const eyeOpen       = btnEye?.querySelector('.eye-open');
    const eyeClosed     = btnEye?.querySelector('.eye-closed');
    const capsWarning   = document.getElementById('capsWarning');
    const strengthWrap  = document.getElementById('strengthWrap');
    const strengthFill  = document.getElementById('strengthFill');
    const strengthLabel = document.getElementById('strengthLabel');
    const fwUser        = document.getElementById('fw-user');
    const fwPass        = document.getElementById('fw-pass');
    const checkUser     = document.getElementById('check-user');


    // ── 1. MOSTRAR / OCULTAR SENHA ──────────────────────────
    if (btnEye && inputSenha) {
        let senhaVisivel = false;

        btnEye.addEventListener('click', () => {
            senhaVisivel = !senhaVisivel;

            inputSenha.type = senhaVisivel ? 'text' : 'password';
            inputSenha.focus();

            // Troca ícone com micro-animação
            if (senhaVisivel) {
                eyeOpen.style.display   = 'none';
                eyeClosed.style.display = 'block';
            } else {
                eyeOpen.style.display   = 'block';
                eyeClosed.style.display = 'none';
            }

            // Animação de escala no ícone
            const icon = senhaVisivel ? eyeClosed : eyeOpen;
            icon.style.transform = 'scale(0.7)';
            requestAnimationFrame(() => {
                icon.style.transition = 'transform 0.2s cubic-bezier(0.34,1.56,0.64,1)';
                icon.style.transform  = 'scale(1)';
            });

            // Atualiza aria-label
            btnEye.setAttribute('aria-label', senhaVisivel ? 'Ocultar senha' : 'Mostrar senha');
            btnEye.title = senhaVisivel ? 'Ocultar senha' : 'Mostrar senha';
        });
    }


    // ── 2. DETECÇÃO DE CAPS LOCK ────────────────────────────
    if (inputSenha && capsWarning) {
        const checkCaps = (e) => {
            // getModifierState disponível em keydown/keyup/mousemove
            if (typeof e.getModifierState === 'function') {
                const capsOn = e.getModifierState('CapsLock');
                capsWarning.classList.toggle('visible', capsOn);
            }
        };

        inputSenha.addEventListener('keydown',    checkCaps);
        inputSenha.addEventListener('keyup',      checkCaps);
        inputSenha.addEventListener('focus',      checkCaps);
        document.addEventListener('mousemove',    checkCaps, { passive: true });

        // Esconde ao sair do campo
        inputSenha.addEventListener('blur', () => {
            capsWarning.classList.remove('visible');
        });
    }


    // ── 3. BARRA DE FORÇA DA SENHA ──────────────────────────
    // const strengthLevels = [
    //     { label: 'Fraca',   class: 'strength-level-1' },
    //     { label: 'Média',   class: 'strength-level-2' },
    //     { label: 'Boa',     class: 'strength-level-3' },
    //     { label: 'Forte',   class: 'strength-level-4' },
    // ];

    function calcularForca(senha) {
        if (!senha) return 0;
        let score = 0;
        if (senha.length >= 6)              score++;
        if (senha.length >= 10)             score++;
        if (/[A-Z]/.test(senha) && /[a-z]/.test(senha)) score++;
        if (/\d/.test(senha))               score++;
        if (/[^A-Za-z0-9]/.test(senha))    score++;
        return Math.min(Math.ceil(score * 4 / 5), 4);
    }

    if (inputSenha && strengthWrap) {
        inputSenha.addEventListener('input', () => {
            const val   = inputSenha.value;
            const nivel = calcularForca(val);

            // Remove classes antigas
            strengthWrap.classList.remove(
                'strength-level-1', 'strength-level-2',
                'strength-level-3', 'strength-level-4'
            );

            if (val.length === 0) {
                strengthWrap.classList.remove('visible');
                strengthLabel.textContent = '';
                return;
            }

            strengthWrap.classList.add('visible');
            if (nivel > 0) {
                const lvl = strengthLevels[nivel - 1];
                strengthWrap.classList.add(lvl.class);
                strengthLabel.textContent = lvl.label;
            }

            // Feedback visual no campo
            if (nivel >= 3) {
                fwPass?.classList.add('field-ok');
            } else {
                fwPass?.classList.remove('field-ok');
            }
        });
    }


    // ── 4. VALIDAÇÃO VISUAL DOS CAMPOS ─────────────────────
    if (inputUser && fwUser && checkUser) {
        inputUser.addEventListener('input', () => {
            const val = inputUser.value.trim();
            const valido = val.length >= 3 && val.includes('.');
            fwUser.classList.toggle('field-ok', valido);
        });

        inputUser.addEventListener('blur', () => {
            const val = inputUser.value.trim();
            if (val.length > 0 && !val.includes('.')) {
                // Shake sutil no campo
                animShake(fwUser);
            }
        });
    }


    // ── 5. LOADING STATE AO SUBMETER ───────────────────────
    if (formLogin && btnEntrar) {
        formLogin.addEventListener('submit', (e) => {
            const user = inputUser?.value.trim() || '';
            const pass = inputSenha?.value || '';

            if (!user || !pass) {
                e.preventDefault();
                animShake(document.querySelector('.login-card'));
                return;
            }

            // Ativa estado de loading
            btnEntrar.classList.add('loading');
            btnEntrar.disabled = true;
        });
    }


    // ── 6. SHAKE PARA ERROS ─────────────────────────────────
    function animShake(el) {
        if (!el) return;
        el.style.animation = 'none';
        el.offsetHeight; // reflow
        el.style.animation = 'shakeError 0.4s cubic-bezier(.36,.07,.19,.97) both';

        // Limpa a animação após executar
        el.addEventListener('animationend', () => {
            el.style.animation = '';
        }, { once: true });
    }

    // Injeta keyframe de shake dinamicamente
    const shakeStyle = document.createElement('style');
    shakeStyle.textContent = `
        @keyframes shakeError {
            0%, 100% { transform: translateX(0); }
            15%       { transform: translateX(-7px); }
            30%       { transform: translateX(6px); }
            45%       { transform: translateX(-5px); }
            60%       { transform: translateX(4px); }
            75%       { transform: translateX(-2px); }
            90%       { transform: translateX(1px); }
        }
    `;
    document.head.appendChild(shakeStyle);


    // ── 7. SHAKE AUTOMÁTICO SE HOUVER FLASH DE ERRO ────────
    const flashErro = document.querySelector('.flash-erro');
    if (flashErro) {
        setTimeout(() => {
            animShake(document.querySelector('.login-card'));
        }, 400);
    }


    // ── 8. EFEITO PARALLAX SUTIL NO CARD ───────────────────
    const card = document.querySelector('.login-card');
    if (card && window.matchMedia('(pointer: fine)').matches) {
        document.addEventListener('mousemove', (e) => {
            const cx = window.innerWidth  / 2;
            const cy = window.innerHeight / 2;
            const dx = (e.clientX - cx) / cx;
            const dy = (e.clientY - cy) / cy;
            const tiltX = dy * -5;
            const tiltY = dx *  5;

            card.style.transform = `perspective(900px) rotateX(${tiltX}deg) rotateY(${tiltY}deg) translateZ(2px)`;
        }, { passive: true });

        document.addEventListener('mouseleave', () => {
            card.style.transform = '';
            card.style.transition = 'transform 0.5s ease';
        });
    }


    // ── 9. FOCO AUTOMÁTICO COM CURSOR NO FINAL ──────────────
    if (inputUser) {
        inputUser.focus();
        const len = inputUser.value.length;
        inputUser.setSelectionRange(len, len);
    }

});