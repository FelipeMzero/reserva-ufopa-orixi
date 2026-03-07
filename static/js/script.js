/**
 * Script de Gestão de Reservas - UFOPA Oriximiná
 */

document.addEventListener('DOMContentLoaded', () => {
    
    // 1. Validação de Datas (Evitar reservas no passado)
    const inputData = document.getElementById('data');
    if (inputData) {
        const hoje = new Date().toISOString().split('T')[0];
        inputData.setAttribute('min', hoje);
    }

    // 2. Validação de Horários (Início deve ser antes do Fim)
    const formReserva = document.getElementById('formReserva');
    if (formReserva) {
        formReserva.addEventListener('submit', (e) => {
            const horaInicio = document.getElementById('hora_inicio').value;
            const horaFim = document.getElementById('hora_fim').value;

            if (horaInicio >= horaFim) {
                e.preventDefault();
                alert('Atenção: A hora de início deve ser anterior à hora de término.');
            }
        });
    }

    // 3. Feedback Visual nas Tabelas
    // Adiciona um efeito de destaque ao passar o mouse nas linhas da tabela
    const rows = document.querySelectorAll('tbody tr');
    rows.forEach(row => {
        row.addEventListener('mouseenter', () => {
            row.style.backgroundColor = 'rgba(255, 215, 0, 0.05)'; // Leve dourado UFOPA
        });
        row.addEventListener('mouseleave', () => {
            row.style.backgroundColor = '';
        });
    });

    // 4. Manipulação de Exclusão (Reforço do confirm)
    // Embora já tenhamos o onclick no HTML, centralizar aqui ajuda na manutenção
    const btnDeletes = document.querySelectorAll('.btn-delete');
    btnDeletes.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const confirmacao = confirm("Tem certeza que deseja excluir esta reserva permanentemente?");
            if (!confirmacao) {
                e.preventDefault();
            }
        });
    });

});

/**
 * Função opcional para formatar as badges de sala dinamicamente via JS
 */
function formatarBadges() {
    const badges = document.querySelectorAll('.badge');
    badges.forEach(badge => {
        if (badge.textContent.includes('Laboratório')) {
            badge.style.borderLeft = '4px solid #004a1a'; // Verde UFOPA
        } else if (badge.textContent.includes('Auditório')) {
            badge.style.borderLeft = '4px solid #FFD700'; // Dourado UFOPA
        }
    });
}

formatarBadges();