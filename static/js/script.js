/**
 * script.js — Sistema de Reservas UFOPA
 * Responsabilidades:
 *  - Filtro de mês na tabela
 *  - Controle do checkbox "Dia Todo"
 *  - Controle de visibilidade do campo "Repetir até"
 *  - Validação do formulário no frontend
 *  - Auto-dismiss de flash messages
 *  - Destaque da linha da reserva em execução
 */

document.addEventListener('DOMContentLoaded', () => {

    // ─────────────────────────────────────────
    // 1. FILTRO DE MÊS
    // ─────────────────────────────────────────
    const filtroMes = document.getElementById('filtroMes');
    const btnLimpar = document.getElementById('btnLimparFiltro');
    const corpoTabela = document.getElementById('corpoTabela');
    const msgVazio = document.getElementById('msgVazio');
    const tabelaResumo = document.getElementById('tabelaResumo');

    function aplicarFiltro() {
        const mesSelecionado = filtroMes ? filtroMes.value : '';
        const linhas = corpoTabela ? corpoTabela.querySelectorAll('tr.linha-reserva') : [];
        let visiveis = 0;

        linhas.forEach(linha => {
            const mesDaLinha = linha.dataset.mes || '';
            const mostrar = !mesSelecionado || mesDaLinha === mesSelecionado;
            linha.style.display = mostrar ? '' : 'none';
            if (mostrar) visiveis++;
        });

        if (msgVazio) {
            msgVazio.style.display = (visiveis === 0 && linhas.length > 0) ? '' : 'none';
        }

        atualizarResumo(linhas, mesSelecionado);
    }

    function atualizarResumo(linhas, mesSelecionado) {
        if (!tabelaResumo) return;

        let total = 0;
        let executando = 0;
        let agendadas = 0;

        linhas.forEach(linha => {
            if (mesSelecionado && linha.dataset.mes !== mesSelecionado) return;
            if (linha.style.display === 'none') return;
            total++;
            const status = linha.dataset.status || '';
            if (status === 'executando') executando++;
            if (status === 'agendada') agendadas++;
        });

        if (total === 0) {
            tabelaResumo.innerHTML = '';
            return;
        }

        tabelaResumo.innerHTML = `
            <span>📊 ${total} reserva${total !== 1 ? 's' : ''} exibida${total !== 1 ? 's' : ''}</span>
            ${agendadas ? `<span class="resumo-tag agendada">🗓 ${agendadas} agendada${agendadas !== 1 ? 's' : ''}</span>` : ''}
            ${executando ? `<span class="resumo-tag executando">▶ ${executando} em execução</span>` : ''}
        `;
    }

    if (filtroMes) {
        // Define mês atual como padrão
        const hoje = new Date();
        const anoMes = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}`;
        filtroMes.value = anoMes;

        filtroMes.addEventListener('change', aplicarFiltro);
        aplicarFiltro();
    }

    if (btnLimpar) {
        btnLimpar.addEventListener('click', () => {
            if (filtroMes) filtroMes.value = '';
            aplicarFiltro();
        });
    }


    // ─────────────────────────────────────────
    // 2. CHECKBOX "DIA TODO" (formulário de nova reserva)
    // ─────────────────────────────────────────
    const checkDiaTodo = document.getElementById('todo_o_dia');
    const inputInicio = document.getElementById('hora_inicio');
    const inputFim = document.getElementById('hora_fim');

    function aplicarDiaTodo() {
        if (!checkDiaTodo) return;
        const marcado = checkDiaTodo.checked;

        if (inputInicio) {
            inputInicio.disabled = marcado;
            if (marcado) inputInicio.value = '08:00';
        }
        if (inputFim) {
            inputFim.disabled = marcado;
            if (marcado) inputFim.value = '22:00';
        }
    }

    if (checkDiaTodo) {
        checkDiaTodo.addEventListener('change', aplicarDiaTodo);
        aplicarDiaTodo();
    }


    // ─────────────────────────────────────────
    // 3. VISIBILIDADE DO CAMPO "REPETIR ATÉ"
    // ─────────────────────────────────────────
    const selectRepeticao = document.getElementById('repeticao_tipo');
    const grupoDataFim = document.getElementById('grupoDataFim');
    const inputDataFim = document.getElementById('data_fim_repeticao');

    function toggleDataFim() {
        if (!selectRepeticao || !grupoDataFim) return;
        const repetir = selectRepeticao.value !== 'Nenhum';
        grupoDataFim.style.opacity = repetir ? '1' : '0.4';
        if (inputDataFim) {
            inputDataFim.disabled = !repetir;
            if (!repetir) inputDataFim.value = '';
        }
    }

    if (selectRepeticao) {
        selectRepeticao.addEventListener('change', toggleDataFim);
        toggleDataFim();
    }


    // ─────────────────────────────────────────
    // 4. VALIDAÇÃO DO FORMULÁRIO (nova reserva)
    // ─────────────────────────────────────────
    const formReserva = document.getElementById('formReserva');

    if (formReserva) {
        formReserva.addEventListener('submit', function (e) {
            const sala = document.getElementById('sala');
            const aula = document.getElementById('aula');
            const data = document.getElementById('data');
            const horaInicio = document.getElementById('hora_inicio');
            const horaFim = document.getElementById('hora_fim');
            const diaChecked = checkDiaTodo && checkDiaTodo.checked;

            // Campo obrigatório: sala
            if (!sala || !sala.value) {
                e.preventDefault();
                mostrarErroFrontend('Selecione um local ou recurso.');
                sala && sala.focus();
                return;
            }

            // Campo obrigatório: atividade
            if (!aula || !aula.value.trim()) {
                e.preventDefault();
                mostrarErroFrontend('Informe o nome da atividade.');
                aula && aula.focus();
                return;
            }

            // Campo obrigatório: data
            if (!data || !data.value) {
                e.preventDefault();
                mostrarErroFrontend('Selecione uma data.');
                data && data.focus();
                return;
            }

            // Valida horários (se não for dia todo)
            if (!diaChecked) {
                if (!horaInicio || !horaFim || !horaInicio.value || !horaFim.value) {
                    e.preventDefault();
                    mostrarErroFrontend('Informe os horários de início e fim.');
                    return;
                }

                if (horaInicio.value >= horaFim.value) {
                    e.preventDefault();
                    mostrarErroFrontend('A hora de início deve ser anterior à hora de fim.');
                    horaInicio.focus();
                    return;
                }
            }

            // Valida data de repetição
            if (selectRepeticao && selectRepeticao.value !== 'Nenhum') {
                if (inputDataFim && inputDataFim.value && data.value) {
                    if (inputDataFim.value < data.value) {
                        e.preventDefault();
                        mostrarErroFrontend('A data de fim da repetição deve ser igual ou posterior à data inicial.');
                        inputDataFim.focus();
                        return;
                    }
                }
            }
        });
    }

    function mostrarErroFrontend(msg) {
        // Remove alertas anteriores
        const existente = document.querySelector('.flash-frontend');
        if (existente) existente.remove();

        const container = document.querySelector('.flash-container') || criarFlashContainer();
        const div = document.createElement('div');
        div.className = 'flash flash-erro flash-frontend';
        div.innerHTML = `<span class="flash-icon">⚠️</span> ${msg} <button class="flash-close" onclick="this.parentElement.remove()">×</button>`;
        container.prepend(div);
        div.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        setTimeout(() => div.remove(), 6000);
    }

    function criarFlashContainer() {
        const div = document.createElement('div');
        div.className = 'flash-container';
        document.querySelector('main') && document.querySelector('main').before(div);
        return div;
    }


    // ─────────────────────────────────────────
    // 5. AUTO-DISMISS DE FLASH MESSAGES
    // ─────────────────────────────────────────
    document.querySelectorAll('.flash').forEach(flash => {
        setTimeout(() => {
            flash.style.transition = 'opacity .5s';
            flash.style.opacity = '0';
            setTimeout(() => flash.remove(), 500);
        }, 5000);
    });


    // ─────────────────────────────────────────
    // 6. DESTAQUE DE LINHA "EXECUTANDO"
    // ─────────────────────────────────────────
    document.querySelectorAll('tr.linha-reserva').forEach(linha => {
        if (linha.dataset.status === 'executando') {
            linha.classList.add('linha-executando');
        }
    });

});